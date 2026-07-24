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
print(json.dumps({"item":sys.argv[1],"oracle_pass":sys.argv[2]=="true",
                  "evidence":sys.argv[3][:1000],"skill_hash":sys.argv[4],
                  "truth_source":sys.argv[5],
                  "skill_result":sys.argv[6][:500]}, ensure_ascii=False))' \
    "$1" "$2" "$3" "$4" "$5" "$6"
}

# ---------------------------------------------------- 提示词：真实重跑做题
write_solve_prompt() {
  local out="$1" has_actor="$2" has_check="$3" data_name="$4"
  cat > "$out" <<'EOF'
你是解题执行者。当前目录下有：

- task.md   一道题目
EOF
  [ -n "$data_name" ] && cat >> "$out" <<EOF
- $data_name/   题目依赖的源文档/数据，从这里取数
EOF
  [ "$has_actor" = "yes" ] && cat >> "$out" <<'EOF'
- skills/actor/  解题技能库：先浏览，找出与本题相关的技能，按它的方法做
EOF
  [ "$has_check" = "yes" ] && cat >> "$out" <<'EOF'
- skills/check/  校验工具技能（怎么跑代码、怎么查数据等）
EOF
  cat >> "$out" <<'EOF'

把这道题**真实做一遍**：要跑代码就真的跑，要算就真的算，要查就真的查。
每一步结论都必须有真实执行结果支撑，禁止凭印象直接给答案。

你的解答过程会被另一个只能读文本的审查者核验，所以「过程」必须留下
可核对的证据：**每个用到的数都写明来源（文件名、位置）并摘录原文**，
每步计算写出算式和结果。没有证据的步骤会被当作未验证。

只输出下面这个 JSON，不要有任何别的文字：

```json
{
  "skills_used": ["用到的技能文件名，没用到就给空数组"],
  "process": "分步的取数与计算记录：来源引用（文件+位置+原文摘录）、算式、中间结果。这是审查的唯一依据，写全",
  "result": "你的最终答案，写完整",
  "evidence": "关键执行步骤和真实输出，两到四句"
}
```

如果环境问题（依赖缺失、外部服务不可用）让你无法得出可靠结果：

```json
{"env_failure": true, "evidence": "什么环节出的问题"}
```
EOF
  if [ -n "$SOLVE_NOTE" ]; then
    printf '\n附加说明（必须遵守）：\n%s\n' "$SOLVE_NOTE" >> "$out"
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
  # 失败(非零退出)时把现场(task/prompt/raw.txt/err.txt)留到 oracle_failures/<id>/
  # 供排查，再清 /tmp temp；成功则照常清。raw.txt 里的真因(如 429)不再随 temp 蒸发。
  _cleanup() {
    local rc=$?
    if [ "$rc" -ne 0 ] && [ -n "${WORK_ORACLE:-}" ] && [ -n "${id:-}" ]; then
      mkdir -p "$HERE/oracle_failures/$id" 2>/dev/null || true
      cp -a "$WORK_ORACLE/." "$HERE/oracle_failures/$id/" 2>/dev/null || true
      # 通知只写 loop 日志、不写 stderr：eval_test.sh 取 stderr 末行当 error，
      # 写 stderr 会盖住真因（[id] 重跑调用失败：… / 环境故障：…）
      if [ -n "${VERISKILL_LOOP_LOG:-}" ]; then
        printf '[%s] [%s] 失败现场已保存到 %s/oracle_failures/%s (rc=%s)\n' \
          "$(date +%H:%M:%S)" "$id" "$HERE" "$id" "$rc" >> "$VERISKILL_LOOP_LOG" 2>/dev/null || true
      fi
    fi
    rm -rf "${WORK_ORACLE:-}" 2>/dev/null || true
  }
  trap _cleanup EXIT
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

  # 重跑：429"请求过频"(rate-limit)是瞬时的，端点提示"wait a short moment and
  # retry"，退避重试，不要一遇就判 env_fail 丢掉这条审计/eval。
  # 配额级 429(exceeded ... quota / reset at)短退避救不回，不浪费重试，记下真因即可。
  local solve_ok=0 attempt
  for attempt in 1 2 3 4 5; do
    if backend_run "$solve_dir" "$solve_dir/prompt.txt" exec \
           > "$solve_dir/raw.txt" 2>"$solve_dir/err.txt"; then
      solve_ok=1; break
    fi
    if grep -q 'too frequent' "$solve_dir/raw.txt" 2>/dev/null || grep -q 'too frequent' "$solve_dir/err.txt" 2>/dev/null; then
      echo "[$id] backend 429 请求过频，退避 $((attempt*10))s 后重试 ($attempt/5)" >&2
      sleep $((attempt * 10))
    else
      # 配额级 429 / 非 429 故障：不重试。真因常在 stdout(raw.txt)，stderr 可能空
      echo "[$id] 重跑调用失败：stderr=$(tail -n 3 "$solve_dir/err.txt" | tr '\n' ' ') | stdout=$(tail -c 300 "$solve_dir/raw.txt" | tr '\n' ' ')" >&2
      exit 5
    fi
  done
  if [ "$solve_ok" -ne 1 ]; then
    echo "[$id] 重跑调用失败（请求过频退避 5 次仍 429）：$(tail -c 200 "$solve_dir/raw.txt" | tr '\n' ' ')" >&2
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
    printf '## 最终答案\n%s\n' "$result" > "$work/answer_wrap.md"
    local out rc
    set +e
    out="$("$checker" "$work/answer_wrap.md" 2>&1)"; rc=$?
    set -e
    case "$rc" in
      0) emit "$id" true  "checker: $(echo "$out" | tail -n 2 | tr '\n' ' ')" "$fp" checker "$result"; exit 0 ;;
      1) emit "$id" false "checker: $(echo "$out" | tail -n 2 | tr '\n' ' ')" "$fp" checker "$result"; exit 0 ;;
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
