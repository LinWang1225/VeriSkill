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
  local out="$1"
  cat > "$out" <<EOF
你是 VeriSkill 的判别器 D。当前目录下有：

- critics/  验证技能库
- traj.md   一条解答轨迹（题目、激活技能、过程、最终答案）。它是某
            一版解题技能库做题的执行样本，frontmatter 的 skill_hash
            标版本

你只能读这两样东西。**你没有标准答案。** 你的核心任务是评**产出这条
轨迹的那版技能好不好**：轨迹做对了 = 技能在这道题上是好的，判 pass；
轨迹有错 = 技能没解决这道题的问题，判 fail。你的判决直接反馈给技能
库的改进，判错方向会把技能带偏。

你有两类判断依据，都要用上：

1. **轨迹内部一致性**——过程有没有算错、代错值、前后自相矛盾、答非
   所问。可以用 Python（Bash 工具）**轻量**抽验决定结论的关键一两步，
   不要重跑整条推导。
2. **你自己的科学知识**——你是懂物理/化学/生物的专家，要判断这次
   解题**在科学上对不对**：题目的物理/化学情形有没有套错（比如把有
   驱动/温差的问题当成平衡态、忽略了关键效应）、用的原理/公式适不
   适用、最终答案的形式是否合理（量纲、极限行为、数量级、符号依赖
   关系是否说得通）、是否答了题目真正问的东西。**这类判断不需要标准
   答案，靠的是你的科学素养**——发现解法从根上就不对，同样判 fail。

边界：你**没有 gold**，判不了"这个数值/表达式和标准答案是否逐字相符"
这种纯比对（那是 Oracle 的活）；但"这个解法科学上站不站得住"你能判、
也应该判。拿不准、你的知识也不足以断定对错时，倾向判 pass，别误杀。
禁止上网、禁止找答案文件。

按下面的固定流程做，不要自由发挥：

1. 读 critics/ 下所有文件。挑出与本条轨迹相关的 critic：看它的 tags 和
   description 与题目类型、激活技能是否对得上。
2. 逐条执行这些 critic 里的 R 判据（形如
   \`- R-<名>-<三位数> [hard|soft] <判据内容> 依据:…\`）。
   判据的形式不一：可能是一个核对条件（检查它在轨迹上是否成立）、
   一个测试用例（把轨迹的答案代入，纸面推演结果是否符合）、一段验证
   步骤（照着重算一遍）。不管哪种形式，都**老老实实执行**，只有执行
   结果明确表明"违规成立"才算命中；执行不了或结果不明确的不算命中，
   不要脑补。
   - 命中任何一条 [hard] 判据 → verdict 直接为 fail，hard_rule_hit 置 true。
   - 命中 [soft] 判据 → 记进 rules_hit，继续往下走。
3. 没有命中 [hard] 规则时，按相关 critic 的评分细则逐项打分，每项
   0/1/2 分（0=完全没做到，1=部分做到，2=做到）。
   标准化分数 = 总分 ÷ (2 × 项数)。低于 ${THRESHOLD} 判 fail，否则判 pass。
4. 独立核查（**无论有没有相关 critic 都必须做**，保持轻量）：不依赖
   任何 critic，快速过一遍轨迹。两个维度：

   A) 内部一致性——
   - 找出 1–2 个决定最终答案的关键算式/代入，用 Python 抽验结果与
     轨迹所写是否一致（算错、代错值、单位没换在这里暴露）；不重跑整条；
   - 符号推导：关键变换是否成立、最终表达式是否真由前面步骤推出、
     前后有没有自相矛盾；
   - 叙述引用的数据与原始证据对照，有没有取错数；
   - 「激活技能」节列了技能时，「过程」是否真按技能方法执行了。

   B) 科学合理性（用你自己的学科知识判）——
   - 题目描述的物理/化学情形，解题有没有套错模型或前提（例：题目给了
     驱动力/温差/非平衡条件，解题却按平衡态或对称情形处理，直接得
     平凡解如 0）；
   - 用的定律/公式/近似在这道题的条件下适不适用；
   - 最终答案的形式合不合理：量纲对不对、极限行为对不对、该依赖的
     变量有没有依赖、数量级离不离谱；
   - 是否答了题目真正问的量。

   任一维度发现**明确成立**的错误（关键步算对不上、推导自相矛盾、
   取错数、模型/前提套错、答案形式明显不合理、答非所问）→ verdict
   为 fail，reason 指明错在哪。拿不准、你的知识也不足以断定的，倾向
   判 pass，别误杀。
   （边界：你没有 gold，判不了"数值/表达式与标准答案是否逐字相符"
   这种纯比对——那是 Oracle 的活。但"解法科学上站不站得住"你要判。）

**给出真实的分级信心,别一律满分。** confidence 是你对"这次判决对不对"
的**主观把握**,0 到 1:
- 判 fail 且证据确凿(命中 hard 判据、重算明确对不上、极限明显矛盾)→ 0.85~1.0；
- 判 pass 且你很有把握解法完全正确、每步都站得住 → 0.85~1.0；
- **判 pass 但心里存疑**(解法看着对但某步没验透、用了你不完全确定适用的
  定律、答案形式勉强合理但说不满、题目理解可能有偏)→ 给 **0.4~0.7** 的
  中间值,别硬给 1.0；
- 判 fail 但证据不够硬(疑似方法错但你也不完全确定)→ 0.5~0.7。
真实反映不确定性——这些中间置信度会被审计优先抽查、也让 G 知道哪些
"过了但不够好"值得改进。

`concerns` 列出你在核查中发现的**弱点或存疑步骤**(即使最终判 pass 也要
写),每条一句话指明"哪一步、疑在哪"。没有就给空数组。这是给 G 的
"次优可改进"信号。

只输出下面这个 JSON，不要有任何别的文字：

\`\`\`json
{
  "verdict": "pass 或 fail",
  "hard_rule_hit": false,
  "rules_hit": ["命中的 R 编号"],
  "rubric_scores": {"细则项名": 0},
  "normalized_score": 0.0,
  "confidence": 0.0,
  "concerns": ["存疑点，一句话一条；没有就空数组"],
  "reason": "一到两句话：判成这样的直接依据"
}
\`\`\`

最终 verdict：critic 判据/评分（第 2、3 步）与独立核查（第 4 步）
任一判 fail 即 fail。找不到相关 critic 时，rubric_scores 给空对象，
verdict 由第 4 步独立核查决定：核查通过 → normalized_score 给 1.0、
判 pass；核查发现明确错误 → normalized_score 给 0.0、判 fail。
无论 pass/fail 都要给出上面说的主观 confidence 和 concerns。
reason 里写明"无适用 critic，独立核查：…"。
EOF
}

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
  write_prompt "$work/prompt.txt"

  local raw="$work/raw.txt"
  if ! backend_run "$work" "$work/prompt.txt" exec > "$raw" 2>"$work/err.txt"; then
    echo "[$id] 后端调用失败：$(tail -n 3 "$work/err.txt" | tr '\n' ' ')" >&2
    return 1
  fi

  if ! python3 "$HERE/lib/jsonx.py" verdict --item "$id" --threshold "$THRESHOLD" \
         < "$raw" > "$outfile" 2>"$work/parse_err.txt"; then
    echo "[$id] 解析判决失败：$(cat "$work/parse_err.txt")" >&2
    return 1
  fi

  # 事后检查：判决理由不该提到真值来源，提到了说明隔离可能被绕过。
  # 只查 reason 字段，不能整行 grep —— 免得误伤字段名之类的正常内容。
  if python3 -c '
import json,sys,re
r = json.load(open(sys.argv[1]))["reason"]
sys.exit(0 if re.search(r"oracle|truth|标准答案|参考答案", r, re.I) else 1)' "$outfile" 2>/dev/null; then
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
  if ! backend_run "$work" "$work/prompt.txt" exec > "$raw" 2>"$work/err.txt"; then
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
