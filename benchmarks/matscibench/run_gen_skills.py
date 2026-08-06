#!/usr/bin/env python3
"""官方 harness + 技能库 —— 与 run_gen.py 的无 skill 基线严格对齐的消融对照。

与 run_gen.py 逐项相同：
  - 题面拼装 question_text()（官方 prepare_prompt）
  - system prompt = 官方 SYSTEM_PROMPT + EXEC_NOTE
  - 答案抽取 = 官方 utils.extract_final_answer
  - 模型 glm-5.2，claude -p --output-format text

唯一差异（即被测变量）：
  - cwd 下放 skills/actor/（veriskill 的 actor_skills 快照）
  - system prompt 追加 SKILLS_BLOCK（原文取自 oracle_run.sh:write_solve_prompt
    的 has_actor 段，是技能的实际投送方式）
  - --allowedTools 增加 Read,Grep,Glob（读技能文件所必需；基线只有 Bash）

用法: SKILLS=<技能目录> OUT=<输出目录> PAR=4 python3 run_gen_skills.py
"""
import json, os, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

L = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(L, "MatSciBench-repo"))
from methods.prompts import SYSTEM_PROMPT          # noqa: E402
from utils import extract_final_answer             # noqa: E402

VS = os.path.expanduser("~/Documents/openclaw-rl/matsci_run/veriskill")
SKILLS = os.environ.get("SKILLS", os.path.join(VS, "stats/skills_snap_r20"))
OUT = os.environ.get("OUT", os.path.join(L, "traj_skills_r21"))
MODEL = os.environ.get("VERISKILL_MODEL", "glm-5.2")
PAR = int(os.environ.get("PAR", "4"))

# —— 与 run_gen.py 完全一致 ——
EXEC_NOTE = ("\n\nYou may write and run Python via Bash for any non-trivial arithmetic — "
             "do not eyeball numeric results.")

# —— 唯一新增：原文取自 oracle_run.sh:write_solve_prompt 的 has_actor 段 ——
SKILLS_BLOCK = """

The current directory contains skills/actor/ — a solving-skill library.

How to use skills/actor/ (this part is binding):

1. Before you start solving, list every file in skills/actor/ and open each one whose
   name OR description could plausibly bear on this problem. Filenames are short and
   often understate scope — do not decide from the filename alone.

2. Lines marked `判据` or `动作 → 检查` are constraints, not suggestions. If such a line
   tells you to compute a check before committing to a formula, compute it. If the check
   comes out saying your current model or convention is the wrong one, you must switch,
   and the switched result is your final answer.

3. If a skill's check produces a corrected value, report the CORRECTED value as your final
   answer. Never report the value the skill just told you is wrong and mention the
   correction only as an aside — an aside is not an answer.

4. You may decline to follow an applicable skill only by naming the concrete feature of
   THIS problem that puts it outside the skill's stated scope. The following are NOT
   acceptable grounds for declining, because each one is a default that has already been
   observed to produce wrong answers on problems of this kind:
     - "the standard / textbook / conventional treatment does it the other way"
     - "the problem does not supply that parameter"  (look it up and state your source)
     - "the simpler model is clearly the intended one"
     - "the difference is small"
"""


def question_text(it):
    """照抄官方 methods/base.py:prepare_prompt 的拼装逻辑（与 run_gen.py 同）。"""
    q = it["question"]
    if it["unit"].strip() != "":
        if it["n_ans"] == "single":
            q += f"The unit of the answer is {it['unit']}."
        elif it["n_ans"] == "multiple":
            q += f"The units of each required answer are {it['unit']}, respectively."
        else:
            raise ValueError(f"Invalid number of answers: {it['n_ans']}")
    return q


def gen(it):
    tid = it["tid"]
    out = os.path.join(OUT, f"{tid}.json")
    if os.path.exists(out) and os.path.getsize(out):
        return (tid, "skip")
    work = tempfile.mkdtemp(prefix="mgenskill-", dir=os.path.join(L, "tmp"))
    try:
        os.makedirs(os.path.join(work, "skills"), exist_ok=True)
        shutil.copytree(SKILLS, os.path.join(work, "skills", "actor"))
        q = question_text(it)
        p = os.path.join(work, "prompt.txt")
        open(p, "w", encoding="utf-8").write(
            SYSTEM_PROMPT + EXEC_NOTE + SKILLS_BLOCK + "\n\n" + q)
        r = subprocess.run(["claude", "-p", "--output-format", "text", "--model", MODEL,
                            "--allowedTools", "Read,Grep,Glob,Bash"],
                           stdin=open(p), capture_output=True, text=True, cwd=work,
                           env=dict(os.environ), timeout=1800)
        body = (r.stdout or "").strip()
        if not body or "Execution error" in body[:60] or "API Error" in body[:60]:
            return (tid, f"fail:{body[:40]}")
        final = extract_final_answer(body)          # 官方抽取
        json.dump({"tid": tid, "qid": it["qid"], "question_text": q,
                   "response": body, "final_answer": final,
                   "correct_answer": it["answer"], "n_ans": it["n_ans"],
                   "level": it["level"], "unit": it["unit"]},
                  open(out, "w"), ensure_ascii=False, indent=1)
        return (tid, "ok" if final else "no-boxed")
    except subprocess.TimeoutExpired:
        return (tid, "timeout")
    except Exception as e:
        return (tid, f"err:{str(e)[:60]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(L, "tmp"), exist_ok=True)
    items = {x["tid"]: x for x in json.load(open(os.path.join(L, "items_all.json")))}
    meta = json.load(open(os.path.join(VS, "pool/meta.json")))["items"]
    test = [x["id"] for x in meta if x["split"] == "test"]
    todo = [items[t] for t in test if t in items]
    print(f"官方 harness + 技能库({len(os.listdir(SKILLS))} 个) 跑 test {len(todo)} 条，并发 {PAR}",
          flush=True)
    with ThreadPoolExecutor(max_workers=PAR) as ex:
        for tid, st in ex.map(gen, todo):
            print(f"  {tid}: {st}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
