#!/usr/bin/env bash
# verify.sh —— 文本判决：用 critics 库读轨迹，逐条给出 pass/fail
#
#   bash verify.sh <batch.list> <out.jsonl>
#   bash verify.sh --selftest          # 不读轨迹，只验后端和 JSON 解析是否通
#
# batch.list：每行一个条目 ID
# out.jsonl ：每行一条判决，字段见 v3 方案第 2 步
#
# 隔离：每条轨迹单开一个临时工作目录，里面只放 critics 库和这一条轨迹，
# 后端以该目录为工作目录、只读模式运行。它拿不到 Oracle 真值、拿不到别的
# 轨迹、也看不到 rounds/ 和 stats/。
#
# 注意：这是"只给该给的"式的结构隔离，不是操作系统级沙箱。真要硬保证，
# 得把后端放进容器或用 sandbox-exec 限制根目录。本脚本额外做了一道
# 事后检查：判决理由里出现 oracle/truth 等字样会被标记出来。
#
# 退出码：0 全部判完；1 参数或环境问题；2 有条目判决失败（缺行，
# 交给编排者按 fail/confidence=0 补记）。

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/backend.sh
source "$HERE/lib/backend.sh"

CRITICS="${VERISKILL_CRITICS:-$HERE/workspace/critics}"
TRAJ_DIR="${VERISKILL_TRAJ:-$HERE/pool/traj}"
THRESHOLD="${VERISKILL_RUBRIC_THRESHOLD:-0.6}"
JOBS="${VERISKILL_JOBS:-4}"

# ---------------------------------------------------------------- 提示词
write_prompt() {
  cat > "$1" <<EOF
你是 VeriSkill 的判别器 D。你只允许读取当前工作目录里的：
- traj.md（必要时 traj.full.md）：待判轨迹
- critics/：当前 D 技能库

禁止读取或猜测 checker、truth、Oracle 输出、审计标签、其他条目的结果。
你的职责是判断轨迹里的答案和过程是否有可直接证实的问题。证据不足不等于错误；
不要因为轨迹简短、未展示全部中间步骤或看不出技能使用痕迹就判 fail。

按固定流程执行：
1. 读取 critics/，挑出适用 critic，把文件名写入 applicable_critics；没有则给空数组。
2. 执行适用 critic 的规则。只有轨迹中的可观察证据明确满足触发条件时才命中；
   执行不了、证据缺失或结论不明确都不命中。命中 [hard] 时
   hard_rule_hit=true；命中 [soft] 时只写入 rules_hit。
3. 没有命中 hard 时，按评分细则逐项打 0/1/2 分。
   normalized_score = 总分 / (2 * 项数)。低于 ${THRESHOLD} 时
   critic_verdict=fail，否则为 pass。没有适用 critic 时
   critic_verdict=not_applicable、rubric_scores={}、normalized_score=null。
4. 独立核查：只检查可由轨迹直接证实的重算不符、引用与原始证据矛盾、
   单位/口径冲突或答非所问。给 independent_verdict，并给
   evidence_coverage（0 到 1），表示实际覆盖关键结论的比例。
5. 保守聚合：
   - hard 命中 -> fail；
   - critic 与独立核查都 fail -> fail；
   - 仅独立核查 fail 时，必须有可定位直接错误且 evidence_coverage>=0.8 才 fail；
   - 仅 critic fail 时 -> pass，disagreement=true，交给审计；
   - 无适用 critic 时按独立核查的直接证据门槛决定。

只输出一个 JSON 对象，不要输出代码围栏或其他文字：
{
  "verdict": "pass 或 fail",
  "critic_verdict": "pass 或 fail 或 not_applicable",
  "independent_verdict": "pass 或 fail",
  "independent_direct_error": false,
  "hard_rule_hit": false,
  "applicable_critics": [],
  "rules_hit": [],
  "rubric_scores": {},
  "normalized_score": null,
  "evidence_coverage": 0.0,
  "disagreement": false,
  "reason": "一到两句话，指出直接证据；分歧时分别说明两条路径"
}
字段必须一致。independent_direct_error 只有在 reason 能定位具体矛盾或重算错误时
才能为 true。不要把“未展示”“没写全”“无法核对”改写成已经成立的错误。
EOF
}

# VERISKILL_CALIBRATION_V5_163DCD8
# ------------------------------------------------------- 判一条（子进程）
# 不用 RETURN trap：bash 里函数内设的 RETURN trap 会一直留到之后的调用栈，
# 等外层函数返回时再触发一次，那时局部变量早没了。显式清理最省事。
verify_one() {
  local id="$1" outfile="$2" work rc
  work="$(mktemp -d "${TMPDIR:-/tmp}/veriskill-verify-XXXXXX")"
  _verify_one_inner "$id" "$outfile" "$work"; rc=$?
  rm -rf "$work"
  return $rc
}

_verify_one_inner() {
  local id="$1" outfile="$2" work="$3"
  if [ ! -f "$TRAJ_DIR/$id.md" ]; then
    echo "[$id] 轨迹文件不存在：$TRAJ_DIR/$id.md" >&2
    return 1
  fi

  cp -R "$CRITICS" "$work/critics"
  cp "$TRAJ_DIR/$id.md" "$work/traj.md"
  local full_dir="${VERISKILL_TRAJ_FULL:-$TRAJ_DIR.full}"
  [ -f "$full_dir/$id.md" ] && cp "$full_dir/$id.md" "$work/traj.full.md"

  local check_traj="$work/traj.md"
  [ -f "$work/traj.full.md" ] && check_traj="$work/traj.full.md"
  if ! python3 "$HERE/lib/trajectory_checks.py" check "$check_traj" \
         > "$work/static_checks.json" 2>"$work/static_err.txt"; then
    echo "[$id] 确定性轨迹检查失败：$(cat "$work/static_err.txt")" >&2
    return 1
  fi
  if python3 -c 'import json,sys;sys.exit(0 if json.load(open(sys.argv[1])).get("hard_errors") else 1)' \
       "$work/static_checks.json"; then
    python3 "$HERE/lib/trajectory_checks.py" verdict-from-checks \
      --item "$id" --checks "$work/static_checks.json" > "$outfile"
    return 0
  fi

  write_prompt "$work/prompt.txt"
  local raw="$work/raw.txt"
  if ! backend_run "$work" "$work/prompt.txt" readonly > "$raw" 2>"$work/err.txt"; then
    echo "[$id] 后端调用失败：$(tail -n 3 "$work/err.txt" | tr '\n' ' ')" >&2
    return 1
  fi

  local model_out="$work/model_verdict.json"
  if ! python3 "$HERE/lib/jsonx.py" verdict --item "$id" --threshold "$THRESHOLD" \
         < "$raw" > "$model_out" 2>"$work/parse_err.txt"; then
    echo "[$id] 解析判决失败：$(cat "$work/parse_err.txt")" >&2
    return 1
  fi
  if ! python3 "$HERE/lib/trajectory_checks.py" merge-verdict \
         --checks "$work/static_checks.json" --verdict "$model_out" > "$outfile"; then
    echo "[$id] 合并确定性检查与模型判决失败" >&2
    return 1
  fi
  if python3 -c '
import json,sys,re
r = json.load(open(sys.argv[1])).get("reason", "")
sys.exit(0 if re.search(r"oracle|truth|标准答案|参考答案|审计标签|真值", r, re.I) else 1)' \
       "$outfile" 2>/dev/null; then
    echo "[$id] 警告：判决理由提到了真值来源，请人工看一眼" >&2
  fi
}

# ------------------------------------------------------------- selftest
selftest() {
  backend_preflight || return 1
  local work rc
  work="$(mktemp -d "${TMPDIR:-/tmp}/veriskill-selftest-XXXXXX")"
  _selftest_inner "$work"; rc=$?
  rm -rf "$work"
  return $rc
}

_selftest_inner() {
  local work="$1"
  mkdir -p "$work/critics"
  cat > "$work/critics/d-demo.md" <<'EOF'
---
name: d-demo
description: 自检用的最小 critic
tags: [demo]
---
## 规则
- R-demo-001 [hard] 触发条件:轨迹里出现字符串 SELFTEST_FAIL 依据:自检
## 评分细则
- 有最终答案
EOF
  printf '题目：自检\n过程：无\n最终答案：42\n' > "$work/traj.md"
  write_prompt "$work/prompt.txt"

  echo "后端=$BACKEND 模型=${MODEL:-默认} 超时=${TIMEOUT_SECS}s"
  echo "正在跑一次最小判决…"
  local raw="$work/raw.txt"
  if ! backend_run "$work" "$work/prompt.txt" readonly > "$raw" 2>"$work/err.txt"; then
    echo "失败：后端没跑通。stderr 末尾："; tail -n 10 "$work/err.txt"
    echo "多半是 CLI 参数名变了，去 lib/backend.sh 里改对应的 backend_$BACKEND 函数。"
    return 1
  fi
  if ! python3 "$HERE/lib/jsonx.py" verdict --item selftest --threshold "$THRESHOLD" < "$raw"; then
    echo "失败：后端有输出但抠不出合法 JSON。原始输出前 20 行："
    head -n 20 "$raw"
    return 1
  fi
  echo "自检通过。"
}

# ----------------------------------------------------------------- main
main() {
  if [ "${1:-}" = "--selftest" ]; then selftest; return $?; fi

  if [ $# -ne 2 ]; then
    echo "用法：bash verify.sh <batch.list> <out.jsonl>" >&2
    echo "      bash verify.sh --selftest" >&2
    return 1
  fi
  local list="$1" out="$2"
  [ -f "$list" ] || { echo "找不到 $list" >&2; return 1; }
  [ -d "$CRITICS" ] || { echo "找不到 critics 库：$CRITICS" >&2; return 1; }
  backend_preflight || return 1

  # 故意用全局变量：EXIT trap 是在 main 返回之后才求值的，
  # 那时 local 变量已经没了，trap 里会撞上未定义变量。
  TMPBATCH="$(mktemp -d "${TMPDIR:-/tmp}/veriskill-batch-XXXXXX")"
  trap 'rm -rf "${TMPBATCH:-}"' EXIT
  local tmp="$TMPBATCH"

  # 并发跑，但每条写自己的文件；最后按 batch.list 原顺序拼起来，
  # 保证输出与并发数无关、可复现。
  export -f verify_one _verify_one_inner write_prompt backend_run backend_claude \
            backend_codex backend_custom backend_stub _run_with_timeout _timeout_cmd
  export HERE CRITICS TRAJ_DIR THRESHOLD BACKEND MODEL TIMEOUT_SECS
  export VERISKILL_OUTDIR="$tmp"

  local n=0
  while IFS= read -r id; do
    [ -z "$id" ] && continue
    n=$((n + 1))
    printf '%s\t%s/%s.json\n' "$id" "$tmp" "$id"
  done < "$list" > "$tmp/plan.tsv"

  # 输出目录走环境变量传给子进程，不要往命令串里拼路径——那样引号一错就
  # 变成子 shell 里的未定义变量，而且路径带空格时会散架。
  awk -F'\t' '{print $1}' "$tmp/plan.tsv" \
    | xargs -P "$JOBS" -I{} bash -c 'verify_one "$1" "$VERISKILL_OUTDIR/$1.json" || true' _ {}

  : > "$out"
  local missing=0
  while IFS=$'\t' read -r id path; do
    if [ -s "$path" ]; then
      cat "$path" >> "$out"
    else
      missing=$((missing + 1))
      echo "[$id] 无判决输出" >&2
    fi
  done < "$tmp/plan.tsv"

  echo "判决完成：$((n - missing))/$n 条成功" >&2
  [ "$missing" -eq 0 ] || return 2
}

main "$@"
