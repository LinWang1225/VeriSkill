#!/usr/bin/env python3
"""为每条轨迹生成 Oracle checker（零模型调用，官方 score_answer 判分）。

  python3 make_checkers.py --golds pool/checkers/golds.json --out pool/checkers

生成 pool/checkers/checker_core.py + 每题一个 <id>.sh。
oracle_run.sh 的约定：checker 以轨迹路径为参数，退出码 0=pass 1=fail
其他=环境故障。stdout 会进 audit.jsonl 的 oracle_evidence。
"""
import argparse
import json
import os
import stat

CORE = '''#!/usr/bin/env python3
import json, os, re, sys
sys.path.insert(0, "/root/data/EvoSkill")
sys.path.insert(0, "/root/data/officeqa_run")
def main():
    tid, traj_path = sys.argv[1], sys.argv[2]
    here = os.path.dirname(os.path.abspath(__file__))
    golds = json.load(open(os.path.join(here, "golds.json")))
    if tid not in golds:
        print(f"no gold for {tid}"); return 4
    text = open(traj_path, encoding="utf-8").read()
    # 取最后一个「## 最终答案」标记之后的内容——不用通用切节器，
    # 免得过程里出现 "Answer:" 之类行首词干扰
    marker = None
    for m in re.finditer(r"^#+\\s*最终答案\\s*$", text, re.M):
        marker = m
    if marker is None:
        print("轨迹缺「最终答案」节"); return 4
    pred = text[marker.end():].strip()
    if not pred:
        print("「最终答案」节为空"); return 4
    try:
        from run_officeqa import score_answer
    except Exception as e:
        print(f"score_answer 导入失败: {e}"); return 4
    gold = golds[tid]
    ok = score_answer(gold, pred) >= 0.5   # 官方口径 (gt, pred), tol=0
    print(f"score_answer(tol=0): pred={pred[:60]!r} gold={gold[:40]!r} -> {'pass' if ok else 'fail'}")
    return 0 if ok else 1
if __name__ == "__main__":
    sys.exit(main())
'''

SH = '''#!/bin/bash
exec /root/data/EvoSkill/.venv/bin/python "{core}" {tid} "$1"
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golds", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    golds = json.load(open(a.golds))
    os.makedirs(a.out, exist_ok=True)
    core = os.path.abspath(os.path.join(a.out, "checker_core.py"))
    with open(core, "w", encoding="utf-8") as f:
        f.write(CORE)
    os.chmod(core, os.stat(core).st_mode | stat.S_IEXEC)

    for tid in golds:
        p = os.path.join(a.out, f"{tid}.sh")
        with open(p, "w") as f:
            f.write(SH.format(core=core, tid=tid))
        os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
    print(json.dumps({"checkers": len(golds)}))


if __name__ == "__main__":
    main()
