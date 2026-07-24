#!/usr/bin/env python3
"""轨迹的规范格式解析器：从轨迹文件抽「题目」和「最终答案」两节。

这是全系统**唯一**的机器切节点（verify/裁决/子 Agent 都是把整个文件给
模型读，不挑格式；只有 Oracle 真实重做前需要机器准确切出这两节）。
不同来源的轨迹格式不一样时，在**入库前**各自转成规范格式，不要来改
这里兼容——解析器只认一种格式，转换器每个来源各写各的。

规范格式（节标记行 = 行首可有 #/>/* 修饰 + 关键词 + 冒号或行尾）：

    ---
    g_version: 0          # 可选
    ---
    ## 题目
    ...
    ## 激活技能            # 可选
    ...
    ## 过程                # 可选
    ...
    ## 最终答案
    ...

关键词同义词（大小写不敏感）：
    题目   ← 任务 / 问题 / Task / Problem / Question
    最终答案 ← 答案 / Final Answer / Answer / Result
    激活技能 ← 激活的技能 / Skills / Activated Skills
    过程   ← 轨迹 / Process / Trace / Steps

用法：
    extract.py <traj.md> --task <out> --answer <out>   # 抽两节，缺则退 1
    extract.py --check <目录>                          # 全量体检，报不合格清单
"""
import argparse
import json
import os
import re
import sys

ALIASES = {
    "题目": "task", "任务": "task", "问题": "task",
    "task": "task", "problem": "task", "question": "task",
    "最终答案": "answer", "答案": "answer",
    "final answer": "answer", "answer": "answer", "result": "answer",
    "激活技能": "skills", "激活的技能": "skills",
    "skills": "skills", "activated skills": "skills",
    "过程": "process", "轨迹": "process",
    "process": "process", "trace": "process", "steps": "process",
}

# 长词在前，防止"最终答案"被"答案"、"final answer"被"answer"抢先命中
_KEYS = sorted(ALIASES, key=len, reverse=True)
MARKER = re.compile(
    r"^[\s#>*]*(" + "|".join(re.escape(k) for k in _KEYS) + r")[\s*]*(?:[:：]\s*(.*)|)$",
    re.IGNORECASE,
)


def strip_frontmatter(lines):
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[i + 1:]
    return lines


def extract(text):
    sections = {}
    current = None
    for line in strip_frontmatter(text.splitlines()):
        m = MARKER.match(line)
        if m:
            current = ALIASES[m.group(1).lower()]
            sections.setdefault(current, [])
            rest = m.group(2)
            if rest:
                sections[current].append(rest)
            continue
        if current:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def missing_of(path):
    text = open(path, encoding="utf-8").read()
    sec = extract(text)
    return [z for z, k in (("题目", "task"), ("最终答案", "answer"))
            if not sec.get(k)]


def cmd_check(traj_dir):
    ok, bad = 0, []
    for fn in sorted(os.listdir(traj_dir)):
        if not fn.endswith(".md"):
            continue
        miss = missing_of(os.path.join(traj_dir, fn))
        if miss:
            bad.append({"id": fn[:-3], "missing": miss})
        else:
            ok += 1
    print(json.dumps({"ok": ok, "bad": bad}, ensure_ascii=False, indent=1))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("traj", nargs="?")
    ap.add_argument("--check", metavar="DIR")
    ap.add_argument("--task")
    ap.add_argument("--answer")
    args = ap.parse_args()

    if args.check:
        return cmd_check(args.check)

    if not (args.traj and args.task and args.answer):
        ap.error("抽取模式需要 <traj> --task --answer；体检模式用 --check <目录>")

    text = open(args.traj, encoding="utf-8").read()
    sec = extract(text)
    miss = [z for z, k in (("题目", "task"), ("最终答案", "answer"))
            if not sec.get(k)]
    if miss:
        print(f"轨迹里抽不出这些节：{'、'.join(miss)}", file=sys.stderr)
        return 1

    open(args.task, "w", encoding="utf-8").write(sec["task"] + "\n")
    open(args.answer, "w", encoding="utf-8").write(sec["answer"] + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
