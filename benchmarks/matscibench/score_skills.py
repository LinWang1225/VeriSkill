#!/usr/bin/env python3
"""官方 harness 下的消融对照评分：无 skill(traj/) vs 有 skill(traj_skills_r21/)。

两侧唯一差异是技能库，判分链路完全相同（官方 extract_final_answer + judge_num_answer）。
"""
import json, os, sys
from math import comb

L = os.path.dirname(os.path.abspath(__file__))
VS = os.path.expanduser("~/Documents/openclaw-rl/matsci_run/veriskill")
sys.path.insert(0, os.path.join(VS, "pool/checkers/matscibench"))
from evaluation.rule_judge import judge_num_answer  # noqa: E402

SK = os.environ.get("OUT", os.path.join(L, "traj_skills_r21"))
items = {x["tid"]: x for x in json.load(open(os.path.join(L, "items_all.json")))}
meta = json.load(open(os.path.join(VS, "pool/meta.json")))["items"]
test = [x["id"] for x in meta if x["split"] == "test"]


def score(d, tids):
    per = {}
    for t in tids:
        f = os.path.join(d, f"{t}.json")
        if not (os.path.exists(f) and os.path.getsize(f)):
            continue
        j = json.load(open(f))
        v = judge_num_answer(j["final_answer"], j["correct_answer"],
                             multiple=(items[t]["n_ans"] == "multiple"))
        per[t] = bool(v["is_correct"])
    return per


base = score(os.path.join(L, "traj"), test)
skil = score(SK, test)
print(f"无 skill (官方 harness): {sum(base.values())}/{len(base)} = {sum(base.values())/len(base):.1%}")
if not skil:
    print("有 skill: 尚无结果")
    sys.exit()
print(f"有 skill (官方 harness): {sum(skil.values())}/{len(skil)} = {sum(skil.values())/len(skil):.1%}")

common = sorted(set(base) & set(skil))
pp = pf = fp = ff = 0
gained, lost = [], []
for k in common:
    if base[k] and skil[k]:
        pp += 1
    elif base[k] and not skil[k]:
        pf += 1; lost.append(k)
    elif not base[k] and skil[k]:
        fp += 1; gained.append(k)
    else:
        ff += 1
print(f"\n配对（共同 {len(common)} 条，同 harness、同判分、只差技能）")
print(f"  无skill {sum(base[k] for k in common)}/{len(common)} = {sum(base[k] for k in common)/len(common):.1%}"
      f"  →  有skill {sum(skil[k] for k in common)}/{len(common)} = {sum(skil[k] for k in common)/len(common):.1%}")
print(f"  都对={pp}  进步={fp} {gained}  退步={pf} {lost}  都错={ff}")
n = pf + fp
if n:
    k = min(pf, fp)
    p = min(sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n * 2, 1.0)
    print(f"  McNemar 精确检验 双尾 p = {p:.4f}")
else:
    print("  无变化条目")

# 与 oracle_run harness 那次(63.8%)对照
print("\n参考：oracle_run harness + 同一技能库 = 30/47 = 63.8%")
