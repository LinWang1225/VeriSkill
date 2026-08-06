#!/usr/bin/env python3
"""对判错的题做错法分类 —— 建池前的数据集体检。

注意与 veriskill 的 diagnose_failure 的区别：那个**不给 gold**（防止答案泄漏进
g-improve 的训练信号）；这里是**离线数据集分诊**，结论只给人看、不进任何技能库，
所以把 gold 一并给分类器，判得准得多。今天已经实测过答案盲诊会编错因
（a100/a102 编出有效数字故事、a059 说"该用闭式"其实也不对）。

五类：
  判据错    选错公式/模型/理论分支
  约定错    符号、单位、因子、口径
  缺数据    方法全对，但需要相图/表格/图表数据而题面没给（技能救不了）
  数值精度  方法对，卡在有效数字或容差边缘
  gold有问题 gold 本身错、取的是别的子问、或单位标注不符（技能救不了）
"""
import json, os, re, shutil, subprocess, sys, tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

L = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(L, "MatSciBench-repo"))
from evaluation.rule_judge import judge_num_answer   # noqa: E402

OUT = os.path.join(L, "diag")
MODEL = os.environ.get("VERISKILL_MODEL", "glm-5.2")
PAR = int(os.environ.get("PAR", "8"))

PROMPT = """你是材料科学专家。下面是一道题、一份**判错**的解答、以及标准答案。
请判断这个"错"的**性质**，归入且仅归入一类。

## 题目
{q}

## 解答过程
{proc}

## 它给出的答案
{pred}

## 标准答案
{gold}

分类（只能选一个）：
- `判据错`     选错了公式/模型/理论分支（例如该用变温大气公式却用了等温式）
- `约定错`     符号、单位、因子、口径搞反或搞错（例如功的符号约定、排除体积的因子）
- `缺数据`     方法链条完全正确，但某一步需要**题面未提供**的相图/表格/图表数据，
               解答只能凭记忆编造该数据，因而失准
- `数值精度`   方法和数据都对，只是有效数字/修约/容差边缘导致不符
- `gold有问题` 解答其实是对的；标准答案本身有误、或取的是**另一个子问**的答案、
               或单位口径与题面要求不符

只输出一行 JSON，不要任何其他内容：
{{"cls": "<五选一>", "why": "<一句话，40字以内>"}}"""


def load_failed():
    items = {x["tid"]: x for x in json.load(open(os.path.join(L, "items_all.json")))}
    out = []
    for tid, it in items.items():
        f = os.path.join(L, "traj", f"{tid}.json")
        if not (os.path.exists(f) and os.path.getsize(f)):
            continue
        d = json.load(open(f))
        v = judge_num_answer(d["final_answer"], d["correct_answer"],
                             multiple=(it["n_ans"] == "multiple"))
        if not v["is_correct"]:
            out.append((it, d))
    return out


def one(job):
    it, d = job
    tid = it["tid"]
    dst = os.path.join(OUT, f"{tid}.json")
    if os.path.exists(dst) and os.path.getsize(dst):
        return (tid, "skip")
    work = tempfile.mkdtemp(prefix="cls-", dir=os.path.join(L, "tmp"))
    try:
        p = os.path.join(work, "p.txt")
        open(p, "w", encoding="utf-8").write(PROMPT.format(
            q=d["question_text"][:1800], proc=d["response"][:3500],
            pred=d["final_answer"][:200], gold=it["answer"][:200]))
        r = subprocess.run(["claude", "-p", "--output-format", "text", "--model", MODEL],
                           stdin=open(p), capture_output=True, text=True, cwd=work,
                           env=dict(os.environ), timeout=600)
        body = (r.stdout or "").strip()
        m = re.search(r'\{.*?"cls".*?\}', body, re.S)
        if not m:
            return (tid, f"noparse:{body[:40]}")
        o = json.loads(m.group(0))
        o.update(tid=tid, level=it["level"], n_ans=it["n_ans"],
                 pred=d["final_answer"], gold=it["answer"])
        json.dump(o, open(dst, "w"), ensure_ascii=False, indent=1)
        return (tid, o["cls"])
    except Exception as e:
        return (tid, f"err:{str(e)[:40]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    jobs = load_failed()
    print(f"判错 {len(jobs)} 题，开始分类…", flush=True)
    with ThreadPoolExecutor(max_workers=PAR) as ex:
        for i, (tid, st) in enumerate(ex.map(one, jobs), 1):
            if st.startswith(("err", "noparse")):
                print(f"  [{i}] {tid} {st}", flush=True)
    print("DONE")
