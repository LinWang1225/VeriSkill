#!/usr/bin/env python3
"""从模型的自由文本输出里抠出一个 JSON 对象，并按 schema 规整。

模型经常在 JSON 前后带一段解释，或者包在 ```json 围栏里。这里按
"围栏块 → 最后一个平衡的花括号块"的顺序尝试，都失败就退出码 1。

用法：
    jsonx.py verdict --item <id> --threshold 0.6 < raw_output
    jsonx.py oracle  --item <id>                 < raw_output

成功时向 stdout 打一行规整后的 JSON；失败时 stderr 说明原因，退出 1。
"""
import argparse
import json
import re
import sys


def _candidates(text):
    for m in re.finditer(r"```(?:json)?\s*(.*?)```", text, re.S):
        yield m.group(1)
    # 从后往前找平衡的花括号块：模型的最终答案通常在最后
    starts = [i for i, c in enumerate(text) if c == "{"]
    for s in reversed(starts):
        depth, in_str, esc = 0, False, False
        for i in range(s, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    yield text[s:i + 1]
                    break


def extract(text, required):
    """挑出含有 required 里任一字段的 JSON 对象。

    不能"找到第一个能解析的就返回"：输出里嵌套的 rubric_scores 之类的
    小对象也能解析成功，会把真正的结果盖掉。所以先按必需字段过滤，
    再取字段最多的那个。
    """
    found = []
    for cand in _candidates(text):
        try:
            obj = json.loads(cand)
        except Exception:
            continue
        if isinstance(obj, dict):
            found.append(obj)
    hits = [o for o in found if any(k in o for k in required)]
    if hits:
        return max(hits, key=len)
    return None


def clamp01(x):
    try:
        x = float(x)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, x))


def as_list(v):
    if isinstance(v, list):
        return [str(x) for x in v]
    if v in (None, ""):
        return []
    return [str(v)]


def build_verdict(obj, item, threshold):
    verdict = str(obj.get("verdict", "")).strip().lower()
    if verdict not in ("pass", "fail"):
        raise ValueError(f"verdict 非法：{obj.get('verdict')!r}")

    rules = as_list(obj.get("rules_hit"))
    scores = obj.get("rubric_scores")
    if not isinstance(scores, dict):
        scores = {}

    # 标准化分数：模型给了就用，没给就按 sum/(2×项数) 自己算
    norm = obj.get("normalized_score")
    if norm is None:
        if scores:
            try:
                norm = sum(float(v) for v in scores.values()) / (2.0 * len(scores))
            except Exception:
                norm = None
    norm = clamp01(norm) if norm is not None else None

    # confidence：采信模型自报的主观把握（D 对"这次判决有多大信心"的实质
    # 判断），而不是标准化分数离阈值的机械换算——机械换算会把 pass 挤到
    # 大片 1.0，抹掉中间地带，让审计无从挑"D 不确定的"、G 拿不到分级信号。
    # 模型没给或非法时，回退到旧的机械换算兜底。
    hard_hit = bool(obj.get("hard_rule_hit")) or (verdict == "fail" and not scores)
    mc = obj.get("confidence")
    try:
        confidence = round(clamp01(float(mc)), 2) if mc is not None else None
    except Exception:
        confidence = None
    if confidence is None:  # 兜底：旧机械换算
        if norm is None:
            confidence = 0.9 if hard_hit else 0.5
        else:
            confidence = round(min(1.0, abs(norm - threshold) / 0.2), 2)

    # D 标注的存疑点（即使判 pass 也可指出弱步骤），供 G 从"次优"学
    concerns = as_list(obj.get("concerns"))

    reason = str(obj.get("reason", ""))[:600]

    return {
        "item": item,
        "verdict": verdict,
        "rules_hit": rules,
        "rubric_scores": scores,
        "normalized_score": norm,
        "confidence": confidence,
        "concerns": concerns,
        "reason": reason,
    }


class EnvFailure(Exception):
    """模型自报环境故障：没验成，不是验出了 fail。"""


def check_env_failure(obj):
    if obj.get("env_failure"):
        raise EnvFailure(str(obj.get("evidence", "模型未说明原因"))[:500])


def build_solve(obj, item):
    check_env_failure(obj)
    result = str(obj.get("result", "")).strip()
    if not result:
        raise ValueError("solve 输出缺少 result 字段")
    skills = obj.get("skills_used")
    if not isinstance(skills, list):
        skills = []
    return {
        "item": item,
        "result": result[:2000],
        # 过程与激活技能：solve_run.sh 组装轨迹时用；oracle 的重做路径不用
        "process": str(obj.get("process", ""))[:8000],
        "skills_used": [str(x) for x in skills][:20],
        "evidence": str(obj.get("evidence", ""))[:1000],
    }


def build_oracle(obj, item, skill_hash, source):
    check_env_failure(obj)
    if "oracle_pass" in obj:
        val = obj["oracle_pass"]
    elif "pass" in obj:
        val = obj["pass"]
    else:
        raise ValueError("缺少 oracle_pass 字段")
    if isinstance(val, str):
        val = val.strip().lower() in ("true", "pass", "yes", "1")
    if not isinstance(val, bool):
        raise ValueError(f"oracle_pass 非法：{obj.get('oracle_pass')!r}")
    return {
        "item": item,
        "oracle_pass": val,
        "evidence": str(obj.get("evidence", ""))[:1000],
        "skill_hash": skill_hash,
        "truth_source": source,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["verdict", "oracle", "solve"])
    ap.add_argument("--item", required=True)
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--skill-hash", default="none")
    ap.add_argument("--source", default="redo",
                    help="真值来源 checker|truth|redo，进输出的 truth_source")
    args = ap.parse_args()

    raw = sys.stdin.read()
    required = {
        "verdict": ["verdict"],
        "oracle": ["oracle_pass", "pass", "env_failure"],
        "solve": ["result", "env_failure"],
    }[args.kind]
    obj = extract(raw, required)
    if obj is None:
        print("输出里找不到合法 JSON 对象", file=sys.stderr)
        return 1
    try:
        if args.kind == "verdict":
            out = build_verdict(obj, args.item, args.threshold)
        elif args.kind == "solve":
            out = build_solve(obj, args.item)
        else:
            out = build_oracle(obj, args.item, args.skill_hash, args.source)
    except EnvFailure as e:
        # 退出码 2：环境故障，和"输出解析不了"(1) 区分开
        print(f"环境故障：{e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
