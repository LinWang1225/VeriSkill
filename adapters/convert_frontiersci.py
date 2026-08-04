#!/usr/bin/env python3
"""all_ds4flash.pkl（FrontierScience-Olympiad）→ VeriSkill 规范轨迹。

  PYTHONPATH=/root/data/EvoSkill:/root/data/frontiersci_run \
  /root/data/EvoSkill/.venv/bin/python convert_frontiersci.py \
      --pkl /root/data/frontiersci_run/results/all_ds4flash.pkl \
      --keys /root/.frontiersci_keys/olympiad_all.csv \
      --traj-out pool/traj_full --gold-out pool/checkers/golds.json

题目从 keys CSV（不含答案）取，避免把 pkl 里 ground_truth 的痕迹带进
轨迹。error 条目（超时等）跳过。gold 只进 golds.json（给 checker），
绝不进轨迹。「过程」= reasoning + 原始消息流节选（含工具调用/结果，
D 靠它核对推导与计算）。
"""
import argparse
import csv
import json
import os
import pickle


def blocks_text(content):
    if isinstance(content, str):
        return content
    out = []
    for b in (content or []):
        t = getattr(b, "text", None)
        if t:
            out.append(t)
            continue
        n = getattr(b, "name", None)
        if n is not None:  # ToolUseBlock
            try:
                arg = json.dumps(getattr(b, "input", {}), ensure_ascii=False, default=str)
            except Exception:
                arg = str(getattr(b, "input", ""))
            out.append(f"[工具调用 {n}] {arg[:800]}")
            continue
        c = getattr(b, "content", None)
        if c is not None:  # ToolResultBlock
            body = c if isinstance(c, str) else blocks_text(c)
            out.append("[工具结果] " + body[:2000])
            continue
        if isinstance(b, dict):
            if b.get("type") == "text":
                out.append(b.get("text", ""))
            elif b.get("type") == "tool_use":
                out.append(f"[工具调用 {b.get('name')}] "
                           + json.dumps(b.get("input", {}), ensure_ascii=False)[:800])
            elif b.get("type") == "tool_result":
                c = b.get("content", "")
                out.append("[工具结果] " + (c if isinstance(c, str) else blocks_text(c))[:2000])
    return "\n".join(out)


def render_messages(msgs, cap=24000):
    parts = []
    for m in msgs:
        cls = type(m).__name__
        if cls == "SystemMessage":
            continue
        content = getattr(m, "content", None)
        if content is None:
            r = getattr(m, "result", None)
            if r:
                parts.append(f"### 收尾\n{str(r)[:800]}")
            continue
        role = "assistant" if "Assistant" in cls else ("user" if "User" in cls else cls)
        t = blocks_text(content).strip()
        if t:
            parts.append(f"### {role}\n{t}")
    body = "\n\n".join(parts)
    return body[:cap] + ("\n…（消息流已截断）" if len(body) > cap else "")


def strip_answer_suffix(q):
    # keys 里题面追加的输出格式说明不进轨迹题目节，保持题面纯净
    for marker in ("\n\nGive your final answer",):
        i = q.find(marker)
        if i >= 0:
            return q[:i].strip()
    return q.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkl", required=True)
    ap.add_argument("--keys", required=True)
    ap.add_argument("--traj-out", required=True)
    ap.add_argument("--gold-out", required=True)
    ap.add_argument("--cap", type=int, default=24000)
    a = ap.parse_args()

    keys = list(csv.DictReader(open(a.keys, encoding="utf-8")))
    d = pickle.load(open(a.pkl, "rb"))
    os.makedirs(a.traj_out, exist_ok=True)
    os.makedirs(os.path.dirname(a.gold_out) or ".", exist_ok=True)

    golds, n, skipped = {}, 0, 0
    for r in d:
        if r.error:
            skipped += 1
            continue
        idx = int(r.index)
        if idx >= len(keys):
            skipped += 1
            continue
        out = getattr(r.trace, "output", None)
        fa = getattr(out, "final_answer", None) if out is not None else None
        reasoning = getattr(out, "reasoning", "") if out is not None else ""
        if fa is None:
            fa = getattr(r.trace, "result", "")
        tid = f"q{idx:03d}"
        question = strip_answer_suffix(keys[idx]["question"])
        doc = (f"---\nskill_hash: 0\n---\n"
               f"## 题目\n{question}\n\n"
               f"## 过程\n"
               f"（模型自述的推导与计算过程）\n{str(reasoning).strip()}\n\n"
               f"（原始执行记录节选）\n{render_messages(r.trace.messages, a.cap)}\n\n"
               f"## 最终答案\n{str(fa).strip()}\n")
        with open(os.path.join(a.traj_out, f"{tid}.md"), "w", encoding="utf-8") as f:
            f.write(doc)
        golds[tid] = keys[idx]["answer"]
        n += 1

    with open(a.gold_out, "w", encoding="utf-8") as f:
        json.dump(golds, f, ensure_ascii=False, indent=1)
    print(json.dumps({"written": n, "golds": len(golds), "skipped": skipped}))


if __name__ == "__main__":
    main()
