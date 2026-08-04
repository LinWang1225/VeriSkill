#!/usr/bin/env python3
"""SciBench-stat Oracle checker —— 官方协议，纯数值、零模型调用。

判分 = math.isclose(pred, gold, rel_tol=0.05)（scibench eval_few.py）。
pred 解析：先整串转 float，失败则取最后一个数值记号（支持 1.2e3 / 1.2×10^3 /
\times / 分数 a/b 与 \frac{a}{b}——分数按除法求值，不能只取分母）。

退出码：0 CORRECT；1 INCORRECT；4 数据问题（无 gold / 轨迹无答案 / 解析不出数）。
接口对齐 oracle_run.sh：checker <含「## 最终答案」节的文件>
"""
import json, math, os, re, sys

_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")

# 一个数值记号：普通数，或分数 a/b（斜杠两侧都必须紧邻数字，"kJ/K"、"J/mol" 这类
# 单位不会被误当分数）。分数放在前面，保证 "1/6" 整体匹配而不是拆成 1 和 6。
_NUM = r"[-+]?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?"
_TOKEN = re.compile(rf"({_NUM})\s*/\s*({_NUM})|({_NUM})")


def _eval_token(m):
    """把 _TOKEN 的一次匹配求值：分数做除法，普通数直接转 float。"""
    num, den, plain = m.group(1), m.group(2), m.group(3)
    if plain is not None:
        return float(plain.replace(",", ""))
    d = float(den.replace(",", ""))
    if d == 0:
        return None
    return float(num.replace(",", "")) / d

def extract_section(text, names):
    pat = r"^#+\s*(?:" + "|".join(names) + r")\s*$"
    last = None
    for m in re.finditer(pat, text, re.M):
        last = m
    if last is None:
        return None
    rest = text[last.end():]
    nxt = re.search(r"^#+\s+", rest, re.M)
    return (rest[:nxt.start()] if nxt else rest).strip()

def parse_num(s):
    s = str(s).strip()
    # 上标指数必须先转（10⁻³ → e-3），否则一般上标翻译会把 10⁶ 变成 "106" 丢掉指数语义
    s = re.sub(r"10\s*([⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+)",
               lambda m: "e" + m.group(1).translate(_SUP), s)
    s = s.translate(_SUP)
    s = re.sub(r"\\?\s*(?:times|cdot)\s*10\s*\^?\{?([-+]?\d+)\}?", r"e\1", s)
    s = re.sub(r"10\s*\^\s*\{?([-+]?\d+)\}?", r"e\1", s)
    # 合并 "2.31 × e6" / "4.2 e-20" → "2.31e6"（要求 e 两侧有数字，免得误伤 answer 这类词）
    s = re.sub(r"(\d)\s*[×*·]?\s*[eE]\s*([-+]?\d)", r"\1e\2", s)
    # \frac{a}{b} → a/b，必须在下面剥花括号之前做，否则分子分母会被拆散
    s = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r" \1/\2 ", s)
    s = s.replace("\\boxed{", " ").replace("$", " ").replace("}", " ")
    try:
        return float(s.replace(",", "").strip())
    except ValueError:
        pass
    # 取最后一个数值记号；分数按除法求值（"1/6" 是 0.1667，不是 6）
    for m in reversed(list(_TOKEN.finditer(s))):
        v = _eval_token(m)
        if v is not None:
            return v
    return None

def main():
    tid, traj = sys.argv[1], sys.argv[2]
    here = os.path.dirname(os.path.abspath(__file__))
    golds = json.load(open(os.path.join(here, "golds.json")))
    if tid not in golds:
        print(f"no gold for {tid}"); return 4
    answer = extract_section(open(traj, encoding="utf-8").read(), ["最终答案", "Final Answer", "答案"])
    if not answer:
        print("轨迹缺「最终答案」节"); return 4
    g, p = parse_num(golds[tid]), parse_num(answer)
    if g is None:
        print(f"gold 解析不出数: {golds[tid]!r}"); return 4
    if p is None:
        print(f"答案解析不出数: {answer[:60]!r} -> INCORRECT"); return 1
    ok = math.isclose(p, g, rel_tol=0.05)
    print(f"numeric(rel_tol=0.05): gold={g!r} pred={p!r} -> {'CORRECT' if ok else 'INCORRECT'}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
