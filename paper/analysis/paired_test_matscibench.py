import os, re, json, sys, glob
import os
# 路径按环境变量覆盖；默认指向本仓库
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", ".."))
VS = os.environ.get("VERISKILL_ROOT", _REPO)
PROBE = os.environ.get("MATSCI_PROBE", os.path.join(_REPO, "benchmarks", "matscibench", "results"))
REPO = os.environ.get("VERISKILL_REPO", _REPO)

from math import comb

VS = os.environ.get("VERISKILL_ROOT", _REPO)
P = os.environ.get("MATSCI_PROBE", os.path.join(_REPO, "benchmarks", "matscibench", "results"))


def main():
    os.chdir(VS)
    sys.path.insert(0, "pool/checkers/matscibench")
    from evaluation.rule_judge import judge_num_answer

    items = {x["tid"]: x for x in json.load(open(f"{P}/items_all.json"))}

    def load_out(d):
        out = {}
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".out"):
                continue
            p = os.path.join(d, fn)
            if not os.path.getsize(p):
                continue
            txt = open(p, encoding="utf-8", errors="replace").read()
            m = None
            for line in txt.splitlines():
                line = line.strip()
                if line.startswith("{") and '"oracle_pass"' in line:
                    mm = re.search(r'"oracle_pass":\s*(true|false)', line)
                    if mm:
                        m = mm.group(1) == "true"
            if m is not None:
                out[fn[:-4]] = m
        return out

    def load_probe(sub):
        o = {}
        for f in glob.glob(f"{P}/{sub}/*.json"):
            t = os.path.basename(f)[:-5]
            if t not in items:
                continue
            j = json.load(open(f))
            v = judge_num_answer(j["final_answer"], j["correct_answer"],
                                 multiple=(items[t]["n_ans"] == "multiple"))
            o[t] = bool(v["is_correct"])
        return o

    r27 = load_out("stats/test_eval_r27")
    base = load_probe("traj")
    r21 = load_probe("traj_skills_r21")

    def pair(a, b, na, nb):
        common = sorted(set(a) & set(b))
        g = [k for k in common if not a[k] and b[k]]
        l = [k for k in common if a[k] and not b[k]]
        n = len(g) + len(l)
        p = 1.0
        if n:
            kk = min(len(g), len(l))
            p = min(sum(comb(n, i) for i in range(kk + 1)) / 2 ** n * 2, 1.0)
        ra = sum(a[k] for k in common); rb = sum(b[k] for k in common)
        print(f"\n【{na} → {nb}】共同 {len(common)} 条")
        print(f"  {ra}/{len(common)} = {ra/len(common):.1%}  →  {rb}/{len(common)} = {rb/len(common):.1%}")
        print(f"  进步 {len(g)} {g}")
        print(f"  退步 {len(l)} {l}")
        print(f"  McNemar 双尾 p = {p:.4f}")

    print("=== 绝对数 ===")
    print(f"  无技能基线          : {sum(base.values())}/{len(base)} = {sum(base.values())/len(base):.1%}")
    print(f"  r21 库（28 技能）   : {sum(r21.values())}/{len(r21)} = {sum(r21.values())/len(r21):.1%}")
    print(f"  r27 库（37 技能）   : {sum(r27.values())}/{len(r27)} = {sum(r27.values())/len(r27):.1%}")

    pair(base, r27, "无技能", "r27")
    pair(r21, r27, "r21  ", "r27")


if __name__ == "__main__":
    main()
