#!/usr/bin/env python3
"""MatSciBench 探针：Materials:Metals × medium+hard × 纯文本NUM。

**完全按官方仓库格式**（Jun-Kai-Zhang/MatSciBench）：
  - 题面拼装照抄 methods/base.py:prepare_prompt
        单答案 → question + "The unit of the answer is {unit}."
        多答案 → question + "The units of each required answer are {unit}, respectively."
  - system prompt 照抄 methods/prompts.py:SYSTEM_PROMPT（要求 \\boxed{...}，不带单位）
  - 答案抽取用官方 utils.extract_final_answer（取最后一个 \\boxed{} 的内容）

唯一偏离：官方 tool 方法是"模型写 python 块 → 外部执行 → 回填结果"两轮；
我们的 harness 是 Claude Code CLI 带 Bash，模型自己执行。能力上等价或更强，
记为 tool-augmented 设定。
"""
import json, os, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

L = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(L, "MatSciBench-repo"))
from methods.prompts import SYSTEM_PROMPT          # noqa: E402
from utils import extract_final_answer             # noqa: E402

OUT = os.path.join(L, "traj")
MODEL = os.environ.get("VERISKILL_MODEL", "glm-5.2")
PAR = int(os.environ.get("PAR", "6"))

EXEC_NOTE = ("\n\nYou may write and run Python via Bash for any non-trivial arithmetic — "
             "do not eyeball numeric results.")


def question_text(it):
    """照抄官方 methods/base.py:prepare_prompt 的拼装逻辑。"""
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
    work = tempfile.mkdtemp(prefix="mgen-", dir=os.path.join(L, "tmp"))
    try:
        q = question_text(it)
        p = os.path.join(work, "prompt.txt")
        open(p, "w", encoding="utf-8").write(SYSTEM_PROMPT + EXEC_NOTE + "\n\n" + q)
        r = subprocess.run(["claude", "-p", "--output-format", "text", "--model", MODEL,
                            "--allowedTools", "Bash"],
                           stdin=open(p), capture_output=True, text=True, cwd=work,
                           env=dict(os.environ), timeout=1200)
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
        return (tid, f"err:{str(e)[:40]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    items = json.load(open(os.path.join(L, os.environ.get("ITEMS","items.json"))))
    done = 0
    with ThreadPoolExecutor(max_workers=PAR) as ex:
        for tid, st in ex.map(gen, items):
            done += 1
            if st not in ("ok", "skip"):
                print(f"[{done}/{len(items)}] {tid} {st}", flush=True)
            elif done % 20 == 0:
                print(f"[{done}/{len(items)}] ...", flush=True)
    print("DONE")
