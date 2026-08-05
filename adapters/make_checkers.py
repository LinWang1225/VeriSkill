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
from decimal import Decimal, InvalidOperation
sys.path.append("/root/data/EvoSkill")
sys.path.append("/root/data/officeqa_run")

NUMBER_RE = re.compile(r"[-+−]?\\d[\\d,]*(?:\\.\\d+)?(?:[eE][-+]?\\d+)?")
SCALAR_RE = re.compile(r"^\\s*[-+−]?\\d[\\d,]*(?:\\.\\d+)?(?:[eE][-+]?\\d+)?\\s*%?\\s*$")
BRACKET_RE = re.compile(r"\\[([^\\]]+)\\]")


def _decimal(token):
    try:
        return Decimal(token.replace(",", "").replace("−", "-"))
    except InvalidOperation:
        return None


def _numbers(text):
    values = []
    for token in NUMBER_RE.findall(text):
        value = _decimal(token)
        if value is not None:
            values.append(value)
    return values


def _list_numbers(content):
    # 括号列表里逗号是元素分隔符，不是千分位——先按逗号切分再逐元素解析，
    # 否则 "10102000000,4.73" 会被 NUMBER_RE 当成一个数 101020000004.73。
    values = []
    for part in content.split(","):
        part = part.strip()
        if not part:
            continue
        value = _decimal(part)
        if value is not None:
            values.append(value)
    return values


def _numeric_fallback(gold, pred):
    """Only normalize clearly numeric scalar/list answers; never guess prose semantics."""
    gold_text = str(gold).strip()
    pred_text = str(pred).strip()

    gold_list = BRACKET_RE.fullmatch(gold_text)
    if gold_list:
        pred_list = BRACKET_RE.search(pred_text)
        if not pred_list:
            return False, "numeric-list:no bracketed prediction"
        gold_values = _list_numbers(gold_list.group(1))
        pred_values = _list_numbers(pred_list.group(1))
        ok = bool(gold_values) and gold_values == pred_values
        return ok, f"numeric-list:{pred_values!s} vs {gold_values!s}"

    if SCALAR_RE.fullmatch(gold_text):
        gold_values = _numbers(gold_text)
        pred_match = NUMBER_RE.match(pred_text)
        pred_value = _decimal(pred_match.group(0)) if pred_match else None
        ok = bool(gold_values) and pred_value == gold_values[0]
        return ok, f"numeric-scalar:{pred_value!s} vs {gold_values[:1]!s}"

    return False, "numeric-fallback:not-applicable"


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
    official_ok = score_answer(gold, pred) >= 0.5   # 官方口径 (gt, pred), tol=0
    fallback_ok, fallback_evidence = _numeric_fallback(gold, pred)
    ok = official_ok or fallback_ok
    route = "official" if official_ok else ("numeric-fallback" if fallback_ok else "fail")
    print(
        f"score_answer(tol=0): pred={pred[:60]!r} gold={str(gold)[:40]!r} "
        f"-> {'pass' if ok else 'fail'} route={route} {fallback_evidence}"
    )
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
