import json, os, re, glob, collections, statistics
import os
# 路径按环境变量覆盖；默认指向本仓库
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", ".."))
VS = os.environ.get("VERISKILL_ROOT", _REPO)
PROBE = os.environ.get("MATSCI_PROBE", os.path.join(_REPO, "benchmarks", "matscibench", "results"))
REPO = os.environ.get("VERISKILL_REPO", _REPO)


os.chdir(os.environ.get("VERISKILL_ROOT", _REPO))

rows = []
for f in glob.glob("rounds/r*/audit.jsonl"):
    r = int(re.search(r"/r(\d+)/", f).group(1))
    for l in open(f, encoding="utf-8", errors="replace"):
        if l.strip():
            d = json.loads(l); d["_r"] = r; rows.append(d)

# 每轮 D 的 fail_rate（全量 16 条，非抽样）
fr = {}
for r in sorted({x["_r"] for x in rows}):
    try:
        v = [json.loads(l) for l in open(f"rounds/r{r}/verdicts.jsonl",
                                        encoding="utf-8", errors="replace") if l.strip()]
        fr[r] = sum(1 for x in v if x["verdict"] == "fail") / len(v)
    except Exception:
        pass


def est(name, sel):
    s = [x for x in rows if sel(x["_r"])]
    fails = [x for x in s if x["d_verdict"] == "fail"]      # 误杀段
    passes = [x for x in s if x["d_verdict"] == "pass"]     # 随机+低置信段
    rnd = [x for x in passes if x.get("segment") == "随机"]  # 只有随机段是 D-pass 的无偏样本

    prec = sum(1 for x in fails if not x["oracle_pass"]) / len(fails) if fails else float("nan")
    miss = sum(1 for x in rnd if not x["oracle_pass"]) / len(rnd) if rnd else float("nan")
    f = statistics.mean([fr[r] for r in {x["_r"] for x in s} if r in fr])

    # 重加权真实召回： D判fail中真失败 / 全部真失败
    num = f * prec
    den = f * prec + (1 - f) * miss
    rec = num / den if den else float("nan")
    truefail = den
    print(f"{name}")
    print(f"   D 判 fail 比例 f            = {f:.3f}   (每轮 16 条全量)")
    print(f"   D-fail 里真失败（=精度）    = {prec:.2f}   (误杀段 n={len(fails)})")
    print(f"   D-pass 里真失败（漏检率）   = {miss:.2f}   (随机段 n={len(rnd)})")
    print(f"   → 推算总体真实失败率        = {truefail:.2f}")
    print(f"   → 推算 D 真实召回           = {rec:.2f}")
    print()


print("=" * 68)
print("D（verifier）真实召回 —— 按 D 判决重加权")
print("=" * 68)
print("审计段是按 D 的判决分层的，不是随机抽样：")
c = collections.Counter((x.get("segment"), x["d_verdict"]) for x in rows)
for k, v in sorted(c.items(), key=lambda kv: -kv[1]):
    print(f"   {k[0]:4s} × D={k[1]:4s}: {v}")
print("   → 误杀段全部来自 D 判 fail；随机/低置信段全部来自 D 判 pass。")
print("   → 直接把四段汇总算召回 = 采样伪影，必须按 f 重加权。")
print()
est("旧口径 r1–r17", lambda r: r <= 17)
est("新口径 r18–r22", lambda r: r >= 18)
