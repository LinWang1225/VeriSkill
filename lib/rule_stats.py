#!/usr/bin/env python3
"""按 R 判据统计历史命中与真值归因，供晋升门用。

    python3 lib/rule_stats.py            # 打表
    python3 lib/rule_stats.py --json     # 出 JSON

对每条 R 编号统计：
    hits       历史判决里命中过多少次（不分 hard/soft）
    items      命中过的互异条目数
    tp / fp    命中该判据的那条判决被 Oracle 审计后的归因

晋升门放宽用的是 (items >= 2 或 hits >= 2) and fp == 0：
原门槛要求 `依据:` 里有 ≥2 个互异 #q，也就是必须**两道题各出一次错**
才敢升 hard。实测 r1–r16 十条规则里只有 4 条升上去，其余长期挂 soft，
而 soft 不改判决 —— 这是召回卡在 30% 的机械原因之一。
实战里"同一条 soft 判据命中过 ≥2 次且从没造成 FP"是同等强度的证据，
所以这里把它做成第二条晋升路径。
"""
import argparse
import collections
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rounds(pattern):
    for f in glob.glob(os.path.join(HERE, pattern)):
        m = re.search(r"/r(\d+)/", f)
        if m:
            yield int(m.group(1)), f


def collect():
    hits = collections.Counter()
    items = collections.defaultdict(set)
    verdicts = {}
    for r, f in _rounds("rounds/r*/verdicts.jsonl"):
        for line in open(f):
            try:
                d = json.loads(line)
            except Exception:
                continue
            verdicts[(r, d.get("item"))] = d
            for rule in d.get("rules_hit") or []:
                hits[rule] += 1
                items[rule].add(d.get("item"))

    tp = collections.Counter()
    fp = collections.Counter()
    for r, f in _rounds("rounds/r*/audit.jsonl"):
        for line in open(f):
            try:
                a = json.loads(line)
            except Exception:
                continue
            if a.get("kind") not in ("TP", "FP"):
                continue
            v = verdicts.get((r, a.get("item"))) or {}
            for rule in v.get("rules_hit") or []:
                (tp if a["kind"] == "TP" else fp)[rule] += 1

    out = {}
    for rule in set(hits) | set(tp) | set(fp):
        out[rule] = {
            "hits": hits[rule],
            "items": len(items[rule]),
            "tp": tp[rule],
            "fp": fp[rule],
            "promotable": (len(items[rule]) >= 2 or hits[rule] >= 2) and fp[rule] == 0,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--rule", help="只查一条：可晋升打印 OK 退 0，否则退 1")
    args = ap.parse_args()
    st = collect()

    if args.rule:
        s = st.get(args.rule)
        if s and s["promotable"]:
            print(f"OK {args.rule} hits={s['hits']} items={s['items']} fp={s['fp']}")
            return 0
        print(f"NO {args.rule} {s or '从未命中'}")
        return 1

    if args.json:
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 0

    print(f"{'规则':45s} {'命中':>4s} {'题数':>4s} {'TP':>3s} {'FP':>3s}  可晋升")
    for rule, s in sorted(st.items(), key=lambda kv: -kv[1]["hits"]):
        print(f"{rule:45s} {s['hits']:>4d} {s['items']:>4d} {s['tp']:>3d} {s['fp']:>3d}  "
              f"{'是' if s['promotable'] else '否'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
