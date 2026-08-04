#!/usr/bin/env bash
# VeriSkill 后端适配层
#
# 这里是整套脚本里唯一知道"具体用哪个 CLI"的地方。verify.sh 和
# oracle_run.sh 都只调用 backend_run，不关心背后是 claude 还是 codex。
#
# 各家 CLI 的参数名会随版本变，一旦某个后端跑不通，只改这个文件里
# 对应的那个函数就行，别去改调用方。改完用 `./verify.sh --selftest`
# 验一下再开始跑正式轮次。
#
# 环境变量：
#   VERISKILL_BACKEND   claude | codex | custom | stub   （默认 claude）
#   VERISKILL_MODEL     传给后端的模型名（留空则用后端自己的默认值）
#   VERISKILL_TIMEOUT   单次调用超时秒数（默认 300）
#   VERISKILL_AGENT_CMD custom 后端的命令模板，见下方 backend_custom
#
# backend_run <工作目录> <提示词文件> <模式>
#   模式 readonly：只读取文件，不允许写盘、不允许联网、不允许跑命令
#   模式 exec    ：允许在工作目录里执行命令（Oracle 校验需要）
# 成功时把后端的原始输出打到 stdout，返回 0；
# 调用失败（命令不存在、超时、非零退出）返回非 0，诊断信息打到 stderr。

set -euo pipefail

BACKEND="${VERISKILL_BACKEND:-claude}"
MODEL="${VERISKILL_MODEL:-}"
# 默认 600：实测长轨迹（~10KB）+ 判据执行，300s 会掐掉一成左右的判决
TIMEOUT_SECS="${VERISKILL_TIMEOUT:-600}"

# ---------- 超时工具：macOS 上 coreutils 装的是 gtimeout ----------
_timeout_cmd() {
  if command -v timeout >/dev/null 2>&1; then echo "timeout"
  elif command -v gtimeout >/dev/null 2>&1; then echo "gtimeout"
  else echo ""; fi
}

_run_with_timeout() {
  local t; t="$(_timeout_cmd)"
  if [ -n "$t" ]; then "$t" "$TIMEOUT_SECS" "$@"; else "$@"; fi
}

# ---------- claude ----------
# 无头模式：-p 读提示词并直接返回结果。提示词走 stdin，避免超长参数和引号转义。
backend_claude() {
  local dir="$1" prompt="$2" mode="$3"
  local args=(-p --output-format text)
  [ -n "$MODEL" ] && args+=(--model "$MODEL")
  if [ "$mode" = "readonly" ]; then
    args+=(--allowedTools "Read,Grep,Glob")
  else
    args+=(--allowedTools "Read,Grep,Glob,Bash")
  fi
  ( cd "$dir" && _run_with_timeout claude "${args[@]}" < "$prompt" )
}

# ---------- codex ----------
# 非交互模式：codex exec。--sandbox 控制读写权限，--cd 指定工作目录。
backend_codex() {
  local dir="$1" prompt="$2" mode="$3"
  local args=(exec --skip-git-repo-check --cd "$dir")
  [ -n "$MODEL" ] && args+=(-m "$MODEL")
  if [ "$mode" = "readonly" ]; then
    args+=(--sandbox read-only)
  else
    args+=(--sandbox workspace-write)
  fi
  _run_with_timeout codex "${args[@]}" "$(cat "$prompt")"
}

# ---------- custom ----------
# 用模板接任意后端。模板里的 {dir} 和 {prompt} 会被替换成实际路径，例如：
#   export VERISKILL_AGENT_CMD='my-agent --workdir {dir} --prompt-file {prompt}'
backend_custom() {
  local dir="$1" prompt="$2" mode="$3"
  if [ -z "${VERISKILL_AGENT_CMD:-}" ]; then
    echo "backend=custom 需要设置 VERISKILL_AGENT_CMD" >&2; return 90
  fi
  local cmd="${VERISKILL_AGENT_CMD//\{dir\}/$dir}"
  cmd="${cmd//\{prompt\}/$prompt}"
  cmd="${cmd//\{mode\}/$mode}"
  _run_with_timeout bash -c "$cmd"
}

# ---------- stub ----------
# 不调用任何模型，返回一个固定的合法 JSON。用来验证脚本骨架、目录隔离、
# JSON 解析和编排流程本身，不花钱。跑通了再换真后端。
backend_stub() {
  local dir="$1" prompt="$2" mode="$3"
  if grep -q '"oracle_pass"' "$prompt" 2>/dev/null; then
    echo '{"oracle_pass": true, "evidence": "stub 后端：未做真实验证"}'
  elif grep -q '"result"' "$prompt" 2>/dev/null; then
    echo '{"result": "stub-answer-42", "evidence": "stub 后端：未真实执行"}'
  else
    echo '{"verdict":"pass","rules_hit":[],"rubric_scores":{},
           "normalized_score":0.8,"reason":"stub 后端：未做真实判决"}'
  fi
}

_backend_dispatch() {
  local dir="$1" prompt="$2" mode="$3"
  case "$BACKEND" in
    claude) backend_claude "$dir" "$prompt" "$mode" ;;
    codex)  backend_codex  "$dir" "$prompt" "$mode" ;;
    custom) backend_custom "$dir" "$prompt" "$mode" ;;
    stub)   backend_stub   "$dir" "$prompt" "$mode" ;;
    *) echo "未知后端：${BACKEND}（可选 claude|codex|custom|stub）" >&2; return 91 ;;
  esac
}

# 供应商并发限制很紧（MaaS 实测只容 1 路）：编排器与子 agent 同时在线时
# 子调用会撞 429，claude CLI 只吐一句 "Execution error"（stderr 为空）。
# 这里统一重试：输出为空或形如 Execution error 时退避重试。
backend_run() {
  local dir="$1" prompt="$2" mode="${3:-readonly}"
  local tries="${VERISKILL_BACKEND_RETRIES:-4}" wait="${VERISKILL_BACKEND_BACKOFF:-25}"
  local i out rc
  for (( i=1; i<=tries; i++ )); do
    out="$(_backend_dispatch "$dir" "$prompt" "$mode")"; rc=$?
    if [ $rc -eq 0 ] && [ -n "${out//[[:space:]]/}" ] \
       && ! printf '%s' "$out" | head -c 200 | grep -qiE '^[[:space:]]*(Execution error|Failed to authenticate|API Error)'; then
      printf '%s' "$out"; return 0
    fi
    if [ $i -lt $tries ]; then
      echo "[backend] 第 $i 次失败(rc=$rc, out='$(printf '%s' "$out" | head -c 40)')，${wait}s 后重试" >&2
      sleep "$wait"; wait=$(( wait * 2 ))
    fi
  done
  printf '%s' "$out"; return ${rc:-1}
}

# 检查后端是否可用，不消耗模型调用
backend_preflight() {
  case "$BACKEND" in
    claude) command -v claude >/dev/null || { echo "找不到 claude 命令" >&2; return 92; } ;;
    codex)  command -v codex  >/dev/null || { echo "找不到 codex 命令"  >&2; return 92; } ;;
    custom) [ -n "${VERISKILL_AGENT_CMD:-}" ] || { echo "未设置 VERISKILL_AGENT_CMD" >&2; return 92; } ;;
    stub)   : ;;
    *) echo "未知后端：$BACKEND" >&2; return 91 ;;
  esac
  command -v python3 >/dev/null || { echo "找不到 python3（用于解析 JSON）" >&2; return 92; }
}
