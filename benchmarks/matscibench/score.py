#!/usr/bin/env python3
"""判分：直接调官方 evaluation.rule_judge.judge_num_answer，不做任何自研替代。

官方 rule judge 的行为（NUM 类）：
  1. sympy 符号等价（math_equal，Qwen-2.5-Math 血统）
  2. \\boxed{} / 前导 (...) 候选跨度逐个试
  3. 数值兜底：抽出所有数、个数必须一致、逐元素比 5% 相对误差
     符号相反直接判错；gold=0 要求 |pred| < 1e-12
FORMULA 类需要 LLM judge —— 我们的切片已排除，全是 NUM。
"""
import json, os, sys
from collections import Counter

L = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(L, "MatSciBench-repo"))
from evaluation.rule_judge import judge_num_answer   # noqa: E402

if __name__ == "__main__":
    items = {x["tid"]: x for x in json.load(open(os.path.join(L, os.environ.get("ITEMS","items.json"))))}
    st, rows = Counter(), []
    for tid, it in items.items():
        f = os.path.join(L, "traj", f"{tid}.json")
        if not (os.path.exists(f) and os.path.getsize(f)):
            st["未跑"] += 1; continue
        d = json.load(open(f))
        v = judge_num_answer(d["final_answer"], d["correct_answer"],
                             multiple=(it["n_ans"] == "multiple"))
        ok = bool(v["is_correct"])
        st["正确" if ok else "错误"] += 1
        if not d["final_answer"]:
            st["无boxed"] += 1
        rows.append((tid, ok, it["level"], it["n_ans"],
                     str(d["final_answer"])[:30], str(it["answer"])[:22],
                     v["judge_reasoning"]))
    n = st["正确"] + st["错误"]
    print(f"  已跑 {n} / {len(items)}   未跑 {st['未跑']}   无\\boxed {st['无boxed']}")
    if n:
        print(f"  pass 率 = {st['正确']}/{n} = {st['正确']/n:.1%}")
        for key, idx in (("难度", 2), ("答案数", 3)):
            print(f"  按{key}:")
            for v_ in sorted({r[idx] for r in rows}):
                sub = [r for r in rows if r[idx] == v_]
                c = sum(1 for r in sub if r[1])
                print(f"    {v_:<10} {c}/{len(sub)} = {c/len(sub):.1%}")
    if "-v" in sys.argv:
        print(f"\n  {'题':<7}{'':<4}{'难度':<8}{'模型答案':<32}{'gold':<24}")
        for tid, ok, lv, k, a, g, why in sorted(rows):
            print(f"  {tid:<7}{'✅' if ok else '❌':<4}{lv:<8}{a:<32}{g:<24}")
            if not ok and "-vv" in sys.argv:
                print(f"          {why[:150]}")
