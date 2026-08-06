#!/usr/bin/env python3
"""把历史上确认过的 TP 轨迹攒成回归集。

    python3 lib/build_regression.py          # 重建 stats/tp_traj + regression_tp.list

TP = D 判 fail、Oracle 也判 fail 的那条**具体轨迹**。这条轨迹被"放回"
换掉之后仍留在 `rounds/r<N>/replaced/<id>.md`，所以能原样取回。

为什么要它：r1–r16 的门控冒烟只抽 2 条 TN（防误杀），不防遗忘。实测
e055 r6/r7 连抓两次、r15 又漏了；m128 r3 抓到、r11/r12 连漏；m029 r11
抓到、r14 漏。共 12 道重复审计的题里 9 道最后一次仍 oracle-fail —— 新
规则在挤掉旧能力，而门控看不见。把这些轨迹钉成回归集，每轮接受编辑前
重跑一遍、必须仍判 fail，退化就回滚。

同一条目多轮 TP 时取最近一轮的快照。
"""
import glob
import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(HERE, "stats", "tp_traj")
LIST = os.path.join(HERE, "stats", "regression_tp.list")


def main():
    best = {}
    for f in glob.glob(os.path.join(HERE, "rounds/r*/audit.jsonl")):
        m = re.search(r"/r(\d+)/", f)
        if not m:
            continue
        r = int(m.group(1))
        for line in open(f):
            try:
                a = json.loads(line)
            except Exception:
                continue
            if a.get("kind") != "TP":
                continue
            item = a["item"]
            if item not in best or r > best[item][0]:
                best[item] = (r, a.get("oracle_evidence", ""))

    os.makedirs(DEST, exist_ok=True)
    kept, missing = [], []
    for item, (r, _) in sorted(best.items()):
        src = os.path.join(HERE, f"rounds/r{r}/replaced/{item}.md")
        if not os.path.exists(src):
            missing.append((item, r))
            continue
        shutil.copy(src, os.path.join(DEST, f"{item}.md"))
        kept.append((item, r))

    with open(LIST, "w") as fh:
        for item, _ in kept:
            fh.write(item + "\n")

    print(f"回归集 {len(kept)} 条 → {LIST}")
    for item, r in kept:
        print(f"  {item}  (r{r} 确认 TP)")
    if missing:
        print("缺快照（跳过）:", missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
