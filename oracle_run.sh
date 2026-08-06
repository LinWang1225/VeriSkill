#!/usr/bin/env bash
# oracle_run.sh —— 审计：用**当前**解题技能库把任务真实重跑一遍，给新
# 结果判真值，并产出一条带 skill_hash 的新轨迹（供编排者替换进池子）。
#
#   bash oracle_run.sh <轨迹路径> [--new-traj-out <路径>]
#   bash oracle_run.sh --fingerprint      # 只打印当前技能指纹，不花钱
#
# 唯一信号 oracle_pass = 当前技能重跑的成绩：既给 D 记 FP/FN（外环
# 校准），也是 G 的实战成绩。重跑全程看不到轨迹的旧过程旧答案（只抽
# 「题目」节），防锚定。
#
# 输出（stdout，一行 JSON）：
#   {"item":"<id>", "oracle_pass": true|false, "evidence":"…",
#    "skill_hash":"…", "truth_source":"checker|truth|redo",
#    "skill_result":"…"}
#
# --new-traj-out：把重跑写成规范轨迹（frontmatter 带 skill_hash，含
# 激活技能/过程/最终答案）落到给定路径。替换池子的动作归编排者。
#
# 退出码（编排者只认这个来区分"判了"和"没判成"）：
#   0  验证完成，结论在 oracle_pass 里（false = 当前技能没做对这道题）
#   非 0  环境故障：这条没验成，编排者应丢弃它、不计入预算
#      3  轨迹里抽不出「题目」节，没法重跑
#      4  校验脚本自身异常，或参数不对
#      5  模型调用失败、输出解析不了、或模型自报执行环境故障
#
# 重跑结果的判分真值，按序取第一个能用的：
#   1. pool/checkers/<id>.sh   —— 专用校验脚本，零模型调用。
#      约定：以一个含「## 最终答案」节的文件为参数，退出码 0=pass，
#      1=fail，其他=环境故障
#   2. pool/truth/<id>.md      —— 参考答案/判定标准，一次裁判调用
#   3. 都没有 → 只看执行本身：重跑成功得出结果、没报错 = pass
#
# 技能指纹：重跑用的是当前技能库，技能一变结果就可能变，去重键必须
# 包含指纹（编排者用 <条目ID>@<指纹>）——G 每出新版本，全池条目都
# 重新可审，新技能下的真实执行是一次新的观测。
#
# 绝对不能加载 critics（判别器 D 的库）：Oracle 是用来检验 D 判得对不对
# 的，让它用上 D 的技能等于让被考的人出考卷。

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/backend.sh
source "$HERE/lib/backend.sh"

CHECKER_DIR="${VERISKILL_CHECKERS:-$HERE/pool/checkers}"
TRUTH_DIR="${VERISKILL_TRUTH:-$HERE/pool/truth}"

ACTOR_SKILLS="${VERISKILL_ACTOR_SKILLS:-$HERE/workspace/actor_skills}"
CHECK_SKILLS="${VERISKILL_CHECK_SKILLS:-}"
# 任务数据目录：以同名 symlink 挂进做题工作区。可选
TASK_DATA="${VERISKILL_TASK_DATA:-}"
# 附加做题说明：逐字进提示词。可选
SOLVE_NOTE="${VERISKILL_SOLVE_NOTE:-}"

_hash_dir() {
  [ -d "$1" ] || return 0
  find "$1" -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 1 2>/dev/null
}

skill_fingerprint() {
  if [ ! -d "$ACTOR_SKILLS" ] && { [ -z "$CHECK_SKILLS" ] || [ ! -d "$CHECK_SKILLS" ]; }; then
    echo "none"; return 0
  fi
  { _hash_dir "$ACTOR_SKILLS"; _hash_dir "$CHECK_SKILLS"; } \
    | shasum -a 1 | cut -d' ' -f1 | cut -c1-12
}

# emit <id> <true|false> <evidence> <skill_hash> <truth_source> <skill_result>
emit() {
  python3 -c '
import json,sys
o={"item":sys.argv[1],"oracle_pass":sys.argv[2]=="true",
   "evidence":sys.argv[3][:1000],"skill_hash":sys.argv[4],
   "truth_source":sys.argv[5],
   "skill_result":sys.argv[6][:500]}
if len(sys.argv)>7 and sys.argv[7].strip(): o["failure_reason"]=sys.argv[7][:600]
print(json.dumps(o, ensure_ascii=False))' \
    "$1" "$2" "$3" "$4" "$5" "$6" "${7:-}"
}

# 判错时归纳「错因」——只描述做法哪里不对(可给出正确做法的名称/条件判据)，
# 严禁泄露正确数值答案。这句诊断会交给 g-improve，让它能写出可执行的决策规则，
# 而不是只知道"这条错了"却不知道错在哪。
diagnose_failure() {  # diagnose_failure <task.md> <轨迹过程> <学生答案>
  local task="$1" proc="$2" ans="$3"
  local d; d="$(mktemp -d "${TMPDIR:-/tmp}/veriskill-diag-XXXXXX")"
  {
    printf '你是学科专家。下面是一道题、一份**错误**的解答过程与它给出的答案。\n\n'
    printf '## 题目\n%s\n\n## 解答过程(有误)\n%s\n\n## 它给出的答案(错误)\n%s\n\n' \
      "$(head -c 2500 "$task")" "$(printf '%s' "$proc" | head -c 3000)" "$(printf '%s' "$ans" | head -c 200)"
    cat <<'EOP'
请指出**它错在哪一步、为什么错、这类题正确的做法是什么**。

硬性要求：
- **绝对不要写出正确的数值答案**（不给数字、不给可直接算出答案的完整代入）。
- 聚焦「判据」和「方法选择」：题面出现什么特征时该用哪个公式/模型/约定，它误用了哪个。
- 写成 2-4 句，形如："题面说 X（恒外压/可逆/…），应按 A 处理；该解答错用了 B，导致…"。
- 若是单位/量纲/有效数字问题，指出是哪一步的换算出错。
只输出这段诊断本身，不要任何前后缀。
EOP
  } > "$d/prompt.txt"
  # 诊断是"锦上添花"：失败就算了，绝不能拖累整轮。
  # 单独用最小重试(1次、不退避)，避免走 backend_run 默认的 30/60/120/240s 阶梯。
  local r
  r="$(VERISKILL_BACKEND_RETRIES=1 VERISKILL_BACKEND_BACKOFF=1 \
       backend_run "$d" "$d/prompt.txt" readonly 2>/dev/null | tr '\n' ' ' | head -c 600)"
  rm -rf "$d"
  case "$r" in
    *"Execution error"*|*"API Error"*) r="" ;;   # 拿到错误串就当没诊断
  esac
  printf '%s' "$r"
}

# ---------------------------------------------------- 提示词：真实重跑做题
write_solve_prompt() {
  local out="$1" has_actor="$2" has_check="$3" data_name="$4"
  # 基础提示词对齐 MatSciBench 官方 harness（MatSciBench-repo/methods/prompts.py
  # 的 SYSTEM_PROMPT），与无技能基线（matsci_probe/run_gen.py）逐字一致：同样的
  # persona、同样的 "reason step by step"、同样的 EXEC_NOTE、答案同样不带单位。
  # 技能库作为额外叠加——skill 空时本提示词≈官方原版，对照才干净；skill 非空时
  # 差异纯来自技能。
  #
  # 两处有意偏离官方，均已知并保留：
  #   1) 输出 JSON 信封。官方是自由文本 + \boxed{}；这里需要 result/process/
  #      evidence/skills_used 四个字段供 jsonx.py build_solve 解析、write_new_traj
  #      组装轨迹。checker 两种都吃（cand = boxed or answer），判分不受影响。
  #   2) 闭卷 / 禁查答案键那句官方没有。oracle 侧模型有 Read,Grep,Glob,Bash，
  #      pool/checkers/golds.json 是可达的，去掉这句等于给作弊开门；基线跑在
  #      tempdir 里且只有 Bash，不存在同等风险。
  cat > "$out" <<'EOF'
You are a renowned materials science engineering professor with extensive knowledge in the field. Your students have presented you with a challenging question related to materials science. Please reason step by step.

You may write and run Python via Bash for any non-trivial arithmetic — do not eyeball numeric results.

This is a closed-book exam: work only from the problem statement and standard scientific knowledge. You have no internet access. Do not look for answer keys or benchmark files on the filesystem; if you encounter one, do not use it.

The current directory contains:

- task.md   the problem to solve
EOF
  [ -n "$data_name" ] && cat >> "$out" <<EOF
- $data_name/   source documents / data the problem depends on
EOF
  [ "$has_actor" = "yes" ] && cat >> "$out" <<'EOF'
- skills/actor/   a solving-skill library

How to use skills/actor/ (this part is binding):

1. Before you start solving, list every file in skills/actor/ and open each one whose
   name OR description could plausibly bear on this problem. Filenames are short and
   often understate scope — do not decide from the filename alone. List every skill you
   actually applied in "skills_used".

2. Lines marked `判据` or `动作 → 检查` are constraints, not suggestions. If such a line
   tells you to compute a check before committing to a formula, compute it. If the check
   comes out saying your current model or convention is the wrong one, you must switch,
   and the switched result is your final answer.

3. If a skill's check produces a corrected value, report the CORRECTED value in "result".
   Never report the value the skill just told you is wrong and mention the correction only
   as an aside — an aside is not an answer.

4. You may decline to follow an applicable skill only by naming, in "process", the concrete
   feature of THIS problem that puts it outside the skill's stated scope. The following are
   NOT acceptable grounds for declining, because each one is a default that has already been
   observed to produce wrong answers on problems of this kind:
     - "the standard / textbook / conventional treatment does it the other way"
     - "the problem does not supply that parameter"  (look it up and state your source)
     - "the simpler model is clearly the intended one"
     - "the difference is small"
EOF
  [ "$has_check" = "yes" ] && cat >> "$out" <<'EOF'
- skills/check/   checking-tool skills (how to run code, query data, etc.)
EOF
  cat >> "$out" <<'EOF'

Give your final answer as a single number or a single closed-form expression in LaTeX. Include ONLY the final answer, without the unit — the problem statement may name the expected unit, but your answer must still carry no unit. Do not restate the same quantity in a second unit.

Output ONLY the following JSON and nothing else:

```json
{
  "skills_used": ["names of skill files you used, or [] if none"],
  "process": "your step-by-step derivation and any code outputs",
  "result": "your final answer, complete",
  "evidence": "key steps and real outputs, two to four sentences"
}
```

If an environment problem (missing dependency, unavailable service) prevents a reliable result:

```json
{"env_failure": true, "evidence": "what went wrong"}
```
EOF
  if [ -n "$SOLVE_NOTE" ]; then
    printf '\nNote (must follow):\n%s\n' "$SOLVE_NOTE" >> "$out"
  fi
}

# ---------------------------------------------------- 提示词：参考答案裁判
write_truth_judge_prompt() {
  local out="$1"
  cat > "$out" <<'EOF'
你是 VeriSkill 的 Oracle 裁判。当前目录下有：

- answer.md  刚刚由真实执行得出的最终答案
- truth.md   这道题的参考答案 / 判定标准

你的唯一任务：判断 answer.md 的答案是否满足 truth.md 的标准。

规则：

1. 只看答案对不对。表述不同但等价的，算 pass。
2. truth.md 给的是判定标准而非唯一答案时，逐条核对每一条标准。
3. 需要算数或跑代码来确认时，就动手算、动手跑，不要凭印象。
4. 拿不准时判 fail，并在 evidence 里说明是哪一点没法确认。

只输出下面这个 JSON，不要有任何别的文字：

```json
{"oracle_pass": true, "evidence": "一到三句话：核对了什么、结论依据是什么"}
```

如果环境问题（依赖缺失、外部服务不可用）让你无法核对：

```json
{"env_failure": true, "evidence": "什么环节出的问题"}
```
EOF
}

_solve_field() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2],""))' "$1" "$2"
}

write_new_traj() {  # write_new_traj <solve.json> <task.md> <out> <fp>
  python3 - "$1" "$2" "$3" "$4" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
task = open(sys.argv[2], encoding="utf-8").read().strip()
skills = s.get("skills_used") or []
skills_txt = "\n".join(f"- {x}" for x in skills) if skills else "（未使用技能）"
doc = (f"---\nskill_hash: {sys.argv[4]}\n---\n"
       f"## 题目\n{task}\n\n"
       f"## 激活技能\n{skills_txt}\n\n"
       f"## 过程\n{s.get('process','').strip()}\n\n"
       f"（执行证据）\n{s.get('evidence','').strip()}\n\n"
       f"## 最终答案\n{s['result'].strip()}\n")
open(sys.argv[3], "w", encoding="utf-8").write(doc)
PY
}

main() {
  local traj="${1:-}"
  local new_out=""
  if [ "${2:-}" = "--new-traj-out" ]; then
    new_out="${3:-}"
    [ -n "$new_out" ] || { echo "--new-traj-out 需要路径" >&2; exit 4; }
  fi

  if [ "$traj" = "--fingerprint" ]; then
    skill_fingerprint; exit 0
  fi

  if [ -z "$traj" ] || [ ! -f "$traj" ]; then
    echo "用法：bash oracle_run.sh <轨迹路径> [--new-traj-out <路径>]" >&2
    echo "      bash oracle_run.sh --fingerprint" >&2
    exit 4
  fi
  local id; id="$(basename "$traj" .md)"
  local fp; fp="$(skill_fingerprint)"
  local checker="$CHECKER_DIR/$id.sh"
  local truth="$TRUTH_DIR/$id.md"

  backend_preflight || exit 5
  WORK_ORACLE="$(mktemp -d "${TMPDIR:-/tmp}/veriskill-oracle-XXXXXX")"
  trap 'rm -rf "${WORK_ORACLE:-}"' EXIT
  local work="$WORK_ORACLE"

  # ---- 1) 从轨迹抽题目（extract.py 要求两个都抽；答案抽出即闲置，
  # 绝不进做题工作区——Oracle 看不到旧答案）----
  if ! python3 "$HERE/lib/extract.py" "$traj" \
         --task "$work/task.md" --answer "$work/unused_answer.md" 2>"$work/ext_err.txt"; then
    echo "[$id] $(cat "$work/ext_err.txt")" >&2
    exit 3
  fi

  # ---- 2) 带当前技能库真实重跑 ----
  local solve_dir="$work/solve"
  mkdir -p "$solve_dir"
  cp "$work/task.md" "$solve_dir/task.md"
  local has_actor=no has_check=no data_name=""
  if [ -d "$ACTOR_SKILLS" ]; then
    mkdir -p "$solve_dir/skills"; cp -R "$ACTOR_SKILLS" "$solve_dir/skills/actor"; has_actor=yes
  fi
  if [ -n "$CHECK_SKILLS" ] && [ -d "$CHECK_SKILLS" ]; then
    mkdir -p "$solve_dir/skills"; cp -R "$CHECK_SKILLS" "$solve_dir/skills/check"; has_check=yes
  fi
  if [ -n "$TASK_DATA" ] && [ -d "$TASK_DATA" ]; then
    data_name="$(basename "$TASK_DATA")"
    ln -s "$TASK_DATA" "$solve_dir/$data_name"   # symlink：语料可能很大，不复制
  fi
  write_solve_prompt "$solve_dir/prompt.txt" "$has_actor" "$has_check" "$data_name"

  if ! backend_run "$solve_dir" "$solve_dir/prompt.txt" exec \
         > "$solve_dir/raw.txt" 2>"$solve_dir/err.txt"; then
    echo "[$id] 重跑调用失败：$(tail -n 3 "$solve_dir/err.txt" | tr '\n' ' ')" >&2
    exit 5
  fi
  if ! python3 "$HERE/lib/jsonx.py" solve --item "$id" \
         < "$solve_dir/raw.txt" > "$work/solve.json" 2>"$work/solve_err.txt"; then
    echo "[$id] $(cat "$work/solve_err.txt")" >&2
    exit 5
  fi
  local result evidence
  result="$(_solve_field "$work/solve.json" result)"
  evidence="$(_solve_field "$work/solve.json" evidence)"

  # ---- 3) 产新轨迹（判分前写好；判 fail 的新轨迹同样有效——它如实
  # 记录了当前技能做错了，正是 D 该练的对象）----
  if [ -n "$new_out" ]; then
    mkdir -p "$(dirname "$new_out")"
    write_new_traj "$work/solve.json" "$work/task.md" "$new_out" "$fp"
  fi

  # ---- 4) 给重跑的新结果判真值 ----
  if [ -x "$checker" ]; then
    { printf '## 题目\n'; cat "$work/task.md" 2>/dev/null; printf '\n\n## 最终答案\n%s\n' "$result"; } > "$work/answer_wrap.md"
    local out rc
    set +e
    out="$("$checker" "$work/answer_wrap.md" 2>&1)"; rc=$?
    set -e
    case "$rc" in
      0) emit "$id" true  "checker: $(echo "$out" | tail -n 2 | tr '\n' ' ')" "$fp" checker "$result"; exit 0 ;;
      1) local _why=""
         [ -n "${VERISKILL_DIAGNOSE:-1}" ] && _why="$(diagnose_failure "$work/task.md" "$evidence" "$result")"
         emit "$id" false "checker: $(echo "$out" | tail -n 2 | tr '\n' ' ')" "$fp" checker "$result" "$_why"; exit 0 ;;
      *) echo "[$id] 校验脚本异常退出 rc=$rc: $(echo "$out" | tail -n 3)" >&2; exit 4 ;;
    esac
  fi

  if [ -f "$truth" ]; then
    local judge_dir="$work/judge"
    mkdir -p "$judge_dir"
    printf '%s\n' "$result" > "$judge_dir/answer.md"
    cp "$truth" "$judge_dir/truth.md"
    write_truth_judge_prompt "$judge_dir/prompt.txt"
    if ! backend_run "$judge_dir" "$judge_dir/prompt.txt" exec \
           > "$judge_dir/raw.txt" 2>"$judge_dir/err.txt"; then
      echo "[$id] 裁决调用失败：$(tail -n 3 "$judge_dir/err.txt" | tr '\n' ' ')" >&2
      exit 5
    fi
    local tj
    if ! tj="$(python3 "$HERE/lib/jsonx.py" oracle --item "$id" --skill-hash "$fp" \
           --source truth < "$judge_dir/raw.txt" 2>"$work/judge_err.txt")"; then
      echo "[$id] $(cat "$work/judge_err.txt")" >&2
      exit 5
    fi
    python3 -c '
import json,sys
o = json.loads(sys.argv[1]); o["skill_result"] = sys.argv[2][:500]
print(json.dumps(o, ensure_ascii=False))' "$tj" "$result"
    exit 0
  fi

  # ---- 没有 checker/truth：只能看执行本身，成功得出结果、没报错 = pass ----
  emit "$id" true "无 checker/truth；重跑成功得出结果（没报错）。执行证据：$evidence" \
       "$fp" redo "$result"
  exit 0
}

main "$@"
