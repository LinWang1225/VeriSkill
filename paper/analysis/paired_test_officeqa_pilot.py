import json, subprocess
import os
# 路径按环境变量覆盖；默认指向本仓库
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", ".."))
VS = os.environ.get("VERISKILL_ROOT", _REPO)
PROBE = os.environ.get("MATSCI_PROBE", os.path.join(_REPO, "benchmarks", "matscibench", "results"))
REPO = os.environ.get("VERISKILL_REPO", _REPO)

from math import comb

REPO = os.environ.get("VERISKILL_REPO", _REPO)
BASE = "archive/before_v6_clean/rounds"


def load(path):
    out = subprocess.run(["git", "show", f"origin/main:{path}"],
                         cwd=REPO, capture_output=True, text=True).stdout
    d = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        d[o["item"]] = o["oracle_pass"]   # True / False / None(env fail)
    return d


r0 = load(f"{BASE}/r0_test_eval/results.jsonl")
r4 = load(f"{BASE}/r4/test_eval/results.jsonl")
fin = load(f"{BASE}/final_test/results.jsonl")

for name, d in (("r0 (0 skills)", r0), ("r4", r4), ("r11 final", fin)):
    ok = sum(1 for v in d.values() if v is True)
    bad = sum(1 for v in d.values() if v is False)
    env = sum(1 for v in d.values() if v is None)
    print(f"{name:14s} pass={ok} fail={bad} env_fail={env}  rate={ok/(ok+bad):.1%}")

# 配对：只取两侧都有有效判决的题
common = [k for k in r0 if r0.get(k) is not None and fin.get(k) is not None]
g = [k for k in common if not r0[k] and fin[k]]
l = [k for k in common if r0[k] and not fin[k]]
n = len(g) + len(l)
p = 1.0
if n:
    kk = min(len(g), len(l))
    p = min(sum(comb(n, i) for i in range(kk + 1)) / 2 ** n * 2, 1.0)

a = sum(1 for k in common if r0[k])
b = sum(1 for k in common if fin[k])
print(f"\n配对（两侧都有有效判决的 {len(common)} 题）")
print(f"  r0  {a}/{len(common)} = {a/len(common):.1%}   →   r11 {b}/{len(common)} = {b/len(common):.1%}")
print(f"  进步 {len(g)} {g}")
print(f"  退步 {len(l)} {l}")
print(f"  McNemar 精确检验 双尾 p = {p:.4f}")
print(f"\n环境故障（两次任一为 None）: {sorted(set(r0) - set(common))}")
