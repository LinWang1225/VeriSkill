import json, os, sys
import os
# 路径按环境变量覆盖；默认指向本仓库
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", ".."))
VS = os.environ.get("VERISKILL_ROOT", _REPO)
PROBE = os.environ.get("MATSCI_PROBE", os.path.join(_REPO, "benchmarks", "matscibench", "results"))
REPO = os.environ.get("VERISKILL_REPO", _REPO)

VS = os.environ.get("VERISKILL_ROOT", _REPO)
os.chdir(VS)
sys.path.insert(0, "pool/checkers/matscibench")
from evaluation.rule_judge import judge_num_answer

PROBE = os.environ.get("MATSCI_PROBE", os.path.join(_REPO, "benchmarks", "matscibench", "results"))
items = {x["tid"]: x for x in json.load(open(f"{PROBE}/items_all.json"))}
meta = json.load(open("pool/meta.json"))["items"]
test = [x["id"] for x in meta if x["split"] == "test"]

per = {}
for t in test:
    f = f"{PROBE}/traj/{t}.json"
    if not os.path.exists(f):
        continue
    d = json.load(open(f))
    it = items[t]
    v = judge_num_answer(d["final_answer"], d["correct_answer"],
                         multiple=(it["n_ans"] == "multiple"))
    per[t] = bool(v["is_correct"])

json.dump(per, open("/tmp/base_test.json", "w"))
ok = sum(per.values())
print(f"无 skill 基线 test: {ok}/{len(per)} = {ok/len(per):.1%}")
