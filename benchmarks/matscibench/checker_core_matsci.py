#!/usr/bin/env python3
"""MatSciBench Oracle checker —— 直接调官方 rule_judge，零 LLM、零自研判分。

判分 = evaluation.rule_judge.judge_num_answer（sympy 符号等价 + \\boxed/前导括号
候选跨度 + 5% 相对容差逐元素比；符号相反直接判错）。切片全是 NUM 类，
不需要官方那条给 FORMULA 用的 LLM judge。

退出码：0 CORRECT；1 INCORRECT；4 数据问题（无 gold / 轨迹无答案）。
接口对齐 oracle_run.sh：checker <含「## 最终答案」节的文件>
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "matscibench"))
from evaluation.rule_judge import judge_num_answer   # noqa: E402


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


def extract_boxed(text):
    """官方 utils.extract_final_answer：取最后一个 \\boxed{} 的平衡括号内容。"""
    if not text:
        return ""
    ms = list(re.finditer(r"(?:\\)?boxed\s*\{", text))
    if not ms:
        return ""
    i = ms[-1].end()
    depth, j = 1, i
    while depth > 0 and j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
        j += 1
    return "" if depth > 0 else text[i:j - 1].strip()


def main():
    tid, traj = sys.argv[1], sys.argv[2]
    golds = json.load(open(os.path.join(HERE, "golds.json")))
    meta = json.load(open(os.path.join(HERE, "meta_ans.json")))
    if tid not in golds:
        print(f"no gold for {tid}"); return 4
    body = open(traj, encoding="utf-8", errors="replace").read()
    answer = extract_section(body, ["最终答案", "Final Answer", "答案"])
    if not answer:
        print("轨迹缺「最终答案」节"); return 4
    # oracle 重解时答案可能仍以 \boxed{} 形式给出，先剥一层（官方口径）
    boxed = extract_boxed(answer)
    cand = boxed or answer
    v = judge_num_answer(cand, golds[tid],
                         multiple=(meta.get(tid, "single") == "multiple"))
    print(v["judge_reasoning"][:300])
    return 0 if v["is_correct"] else 1


if __name__ == "__main__":
    sys.exit(main())
