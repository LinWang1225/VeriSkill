#!/usr/bin/env python3
"""从 matsci_probe 的 553 条轨迹建 1:1 平衡池 + 分层 train/test 划分。

要点（都是今天踩出来的教训）：
  1. 单位/格式要求必须留在题面里 —— 用官方 prepare_prompt 拼好的 question_text，
     oracle 重解才知道要什么单位（SciBench 那次漏了这个，判分整批作废）。
  2. 划分用**精确配额**（hash 排序取前 k），不是 Bernoulli —— 之前 Bernoulli
     导致 test 只有 18 题而不是 20。
  3. 1:1 平衡：全部错题 + 等量正确题，按难度分层配对，使"全判 pass"只值 50%。
"""
import hashlib, json, os, random, shutil, subprocess, sys

L = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.expanduser("~/Documents/openclaw-rl/matsci_probe")
sys.path.insert(0, os.path.join(L, "pool/checkers/matscibench"))
from evaluation.rule_judge import judge_num_answer  # noqa: E402

TEST_FRAC = 0.2


def h(s):
    return hashlib.sha1(s.encode()).hexdigest()


def assign_splits(tids, frac):
    """精确配额划分：按 hash 排序，前 k 个进 test。"""
    ordered = sorted(tids, key=h)
    k = round(len(ordered) * frac)
    return {t: ("test" if i < k else "train") for i, t in enumerate(ordered)}


def main():
    items = {x["tid"]: x for x in json.load(open(os.path.join(PROBE, "items_all.json")))}
    correct, wrong = [], []
    for tid, it in items.items():
        f = os.path.join(PROBE, "traj", f"{tid}.json")
        if not (os.path.exists(f) and os.path.getsize(f)):
            continue
        d = json.load(open(f))
        v = judge_num_answer(d["final_answer"], d["correct_answer"],
                             multiple=(it["n_ans"] == "multiple"))
        (correct if v["is_correct"] else wrong).append((tid, it, d))
    print(f"打标签: 正确 {len(correct)} / 错误 {len(wrong)}  "
          f"(pass {len(correct)/(len(correct)+len(wrong)):.1%})")

    # ---- 1:1，按难度分层配对 ----
    random.seed(0)
    by_lv_c = {}
    for rec in correct:
        by_lv_c.setdefault(rec[1]["level"], []).append(rec)
    for v in by_lv_c.values():
        v.sort(key=lambda r: r[0]); random.shuffle(v)
    keep = list(wrong)
    need = {}
    for rec in wrong:
        need[rec[1]["level"]] = need.get(rec[1]["level"], 0) + 1
    for lv, n in need.items():
        pool = by_lv_c.get(lv, [])
        if len(pool) < n:
            print(f"  ⚠️ {lv} 正确样本不足：要 {n} 只有 {len(pool)}，按可得取")
        keep += pool[:n]
    print(f"1:1 池: {len(wrong)} 错 + {len(keep)-len(wrong)} 对 = {len(keep)} 题")

    # ---- 分层精确配额划分（错/对 各自内部再按难度分层）----
    split = {}
    for lab, group in (("wrong", wrong), ("right", keep[len(wrong):])):
        by_lv = {}
        for rec in group:
            by_lv.setdefault(rec[1]["level"], []).append(rec[0])
        for lv, tids in by_lv.items():
            split.update(assign_splits(tids, TEST_FRAC))

    # ---- 落盘 ----
    for d in ("pool/traj", "pool/traj_full"):
        os.makedirs(os.path.join(L, d), exist_ok=True)
    golds, meta_ans, meta = {}, {}, []
    for tid, it, d in keep:
        doc = (f"---\nskill_hash: 0\n---\n"
               f"## 题目\n{d['question_text'].strip()}\n\n"
               f"## 过程\n{d['response'].strip()}\n\n"
               f"## 最终答案\n{d['final_answer'].strip()}\n")
        for sub in ("traj", "traj_full"):
            open(os.path.join(L, "pool", sub, f"{tid}.md"), "w", encoding="utf-8").write(doc)
        golds[tid] = it["answer"]
        meta_ans[tid] = it["n_ans"]
        meta.append({"id": tid, "g_version": 0, "used_count": 0, "split": split[tid]})
    json.dump(golds, open(os.path.join(L, "pool/checkers/golds.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(meta_ans, open(os.path.join(L, "pool/checkers/meta_ans.json"), "w"), ensure_ascii=False, indent=1)
    json.dump({"items": meta}, open(os.path.join(L, "pool/meta.json"), "w"), ensure_ascii=False, indent=1)

    # ---- 每题一个 checker 包装 ----
    for tid, _, _ in keep:
        p = os.path.join(L, "pool/checkers", f"{tid}.sh")
        open(p, "w").write(f'#!/bin/bash\nexec python3 "$(dirname "$0")/checker_core_matsci.py" {tid} "$1"\n')
        os.chmod(p, 0o755)

    tr = sum(1 for m in meta if m["split"] == "train")
    print(f"划分: train {tr} / test {len(meta)-tr}")
    wt = {s: sum(1 for t, i, _ in wrong if split[t] == s) for s in ("train", "test")}
    print(f"  其中错题: train {wt['train']} / test {wt['test']}")
    print(f"落盘: {len(keep)} 轨迹 + golds.json + {len(keep)} 个 checker")


if __name__ == "__main__":
    main()
