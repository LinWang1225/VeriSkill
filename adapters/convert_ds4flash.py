#!/usr/bin/env python3
"""hard_ds4flash.pkl → VeriSkill 规范轨迹。在 101 上用 EvoSkill venv 跑：

  PYTHONPATH=/root/data/EvoSkill:/root/data/officeqa_run \
  /root/data/EvoSkill/.venv/bin/python convert_ds4flash.py \
      --pkl /root/data/officeqa_run/results/hard_ds4flash.pkl \
      --traj-out pool/traj --gold-out pool/checkers/golds.json

按 2026-07-22 实测结构写死：list[IndexedEvalResult]，字段
error/ground_truth/index/question/trace；trace.output.final_answer 是
结构化最终答案，trace.output.reasoning 是模型自述的取数与计算过程，
trace.messages 是 SDK 消息对象流。

每条轨迹产出两份：--traj-out 下是压缩骨架版（过程节缩减为首尾 + 省略
标注），<--traj-out>.full 下是非压缩版（过程节为消息流全文）。gold 只进
golds.json（给 checker），绝不进轨迹。
"""
import argparse
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
            out.append(f"[工具调用 {n}] {arg}")
            continue
        c = getattr(b, "content", None)
        if c is not None:  # ToolResultBlock
            body = c if isinstance(c, str) else blocks_text(c)
            out.append("[工具结果] " + body)
            continue
        if isinstance(b, dict):
            if b.get("type") == "text":
                out.append(b.get("text", ""))
            elif b.get("type") == "tool_use":
                out.append(f"[工具调用 {b.get('name')}] "
                           + json.dumps(b.get("input", {}), ensure_ascii=False))
            elif b.get("type") == "tool_result":
                c = b.get("content", "")
                out.append("[工具结果] " + (c if isinstance(c, str) else blocks_text(c)))
    return "\n".join(out)


def render_messages(msgs):
    """返回消息块列表 [(role_line, content), ...]，不含块间分隔。"""
    parts = []
    for m in msgs:
        cls = type(m).__name__
        if cls == "SystemMessage":
            continue
        content = getattr(m, "content", None)
        if content is None:
            r = getattr(m, "result", None)
            if r:
                parts.append(("### 收尾", str(r)))
            continue
        role = "assistant" if "Assistant" in cls else ("user" if "User" in cls else cls)
        t = blocks_text(content).strip()
        if t:
            parts.append((f"### {role}", t))
    return parts


# ---------------------------------------------------------------- 压缩骨架
# 确定性、无 API：把消息流压成骨架，供压缩版轨迹。每个 ### role 块单独
# 缩减，块标记行原样保留（脉络不能丢）。短块不动，长块保留首尾 + 省略标注。

def _compress_call_line(line, cap=200):
    """工具调用行 `[工具调用 X] {json}`：参数超 cap 截断，保留工具名。"""
    if len(line) <= cap:
        return line
    idx = line.find("] ")
    if idx < 0:
        return line[:cap] + f"…(省略 {len(line) - cap} 字符)"
    arg = line[idx + 2:]
    if len(arg) <= cap:
        return line
    return line[:idx + 2] + arg[:cap] + f"…(参数省略 {len(arg) - cap} 字符)"


def compress_block(text, head=3, tail=2):
    """压缩单个消息块正文：工具调用行截参数，多行内容首尾保留。短块原样。"""
    lines = [_compress_call_line(ln) if ln.startswith("[工具调用") else ln
             for ln in text.split("\n")]
    if len(lines) <= head + tail:
        return "\n".join(lines)
    mid = len(lines) - head - tail
    return "\n".join(lines[:head] + [f"…(省略 {mid} 行)"] + lines[-tail:])


def body_full(parts):
    """完整版过程：每块前加 `## 块k` 标题，与压缩版块号一一对应。"""
    return "\n\n".join(f"## 块{k}\n{role}\n{content}"
                       for k, (role, content) in enumerate(parts, 1))


def body_comp(parts):
    """压缩版过程：每块前加 `[块k]` 锚点 + 块内骨架压缩。"""
    return "\n\n".join(f"[块{k}] {role}\n{compress_block(content)}"
                       for k, (role, content) in enumerate(parts, 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkl", required=True)
    ap.add_argument("--traj-out", required=True)
    ap.add_argument("--gold-out", required=True)
    ap.add_argument("--full-out", default=None,
                    help="非压缩版输出目录；默认 <traj-out>.full")
    a = ap.parse_args()

    full_out = a.full_out or (a.traj_out.rstrip("/") + ".full")

    d = pickle.load(open(a.pkl, "rb"))
    os.makedirs(a.traj_out, exist_ok=True)
    os.makedirs(full_out, exist_ok=True)
    os.makedirs(os.path.dirname(a.gold_out) or ".", exist_ok=True)

    full_rel = os.path.basename(full_out.rstrip("/"))
    golds, n = {}, 0
    for r in d:
        if r.error:
            continue
        out = getattr(r.trace, "output", None)
        fa = getattr(out, "final_answer", None) if out is not None else None
        reasoning = getattr(out, "reasoning", "") if out is not None else ""
        if fa is None:
            fa = getattr(r.trace, "result", "")
        tid = f"q{int(r.index):03d}"
        parts = render_messages(r.trace.messages)
        q, proc, ans = str(r.question).strip(), str(reasoning).strip(), str(fa).strip()
        # 非压缩版：过程节为消息流全文（按 `## 块k` 编号，与压缩版对应）
        doc_full = (f"---\ng_version: 0\n---\n"
                    f"## 题目\n{q}\n\n"
                    f"## 过程\n"
                    f"（模型自述的取数与计算过程）\n{proc}\n\n"
                    f"（原始执行记录全文）\n{body_full(parts)}\n\n"
                    f"## 最终答案\n{ans}\n")
        # 压缩版：过程节为骨架（每块 `[块k]` 锚点），顶部指明完整版位置与查询方式
        doc_comp = (f"---\ng_version: 0\n---\n"
                    f"## 题目\n{q}\n\n"
                    f"## 过程\n"
                    f"（模型自述的取数与计算过程）\n{proc}\n\n"
                    f"（原始执行记录·压缩骨架，完整版见 {full_rel}/{tid}.md，"
                    f"按 `## 块k` 查询对应块）\n"
                    f"{body_comp(parts)}\n\n"
                    f"## 最终答案\n{ans}\n")
        with open(os.path.join(a.traj_out, f"{tid}.md"), "w", encoding="utf-8") as f:
            f.write(doc_comp)
        with open(os.path.join(full_out, f"{tid}.md"), "w", encoding="utf-8") as f:
            f.write(doc_full)
        golds[tid] = str(r.ground_truth)
        n += 1

    with open(a.gold_out, "w", encoding="utf-8") as f:
        json.dump(golds, f, ensure_ascii=False, indent=1)
    print(json.dumps({"written": n, "golds": len(golds), "full_out": full_out}))


if __name__ == "__main__":
    main()
