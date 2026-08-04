#!/usr/bin/env python3
"""轨迹压缩：原版 → 压缩版。零模型调用、确定性、幂等。

  python3 lib/compress.py <in.md> <out.md>            # 单文件
  python3 lib/compress.py --dir <in_dir> <out_dir>    # 整目录

只压「过程」节，其余（frontmatter、题目、激活技能、最终答案）原样
保留——判决、checker、extract 依赖的两节不受影响。

压缩策略（证据优先于叙述，见 README 转换器契约）：
- **执行过程完整保留**：证据行（以 [工具调用] / [工具结果] 开头的
  原始执行记录）一行不删、一字不截——D 抓"取错数但算式自洽"类错误
  全靠拿叙事和原始记录交叉核对，证据被截，这类错误就纸面不可判了；
- 只压**叙述散文**（模型的自述文字）：按原顺序保留到预算（默认
  1500 字），超出的丢弃，丢弃处插一行省略标记；
- 过程节里叙述不超预算时原样保留（幂等：压缩版再压缩不变）。

压缩版结尾带标记行，G/D 需要完整叙述时按它去读原版
（pool/traj_full/<同名文件>）。
"""
import argparse
import os
import re
import sys

EVID = re.compile(r"^\s*\[工具(调用|结果)\]")
PROC = re.compile(r"^##\s*(过程|执行过程|Process|Trace)\s*$", re.M | re.I)
NEXT = re.compile(r"^##\s+", re.M)
MARK = "（压缩版：仅叙述散文被压缩，原始执行记录完整；完整叙述见 pool/traj_full/ 同名文件）"

NAR_BUDGET = 1500


def compress_text(text: str) -> str:
    m = PROC.search(text)
    if not m:
        return text
    m2 = NEXT.search(text, m.end())
    if not m2:
        return text
    head, body, tail = text[:m.end()], text[m.end():m2.start()], text[m2.start():]
    if MARK in body:          # 已是压缩版
        return text

    lines = body.splitlines()
    nar_total = sum(len(ln) for ln in lines if not EVID.match(ln))
    if nar_total <= NAR_BUDGET:
        return text

    nar_left = NAR_BUDGET
    out, dropping = [], False
    for ln in lines:
        if EVID.match(ln):
            out.append(ln)            # 证据行完整保留，不截断
            dropping = False
        else:
            if nar_left - len(ln) >= 0:
                out.append(ln)
                nar_left -= len(ln)
                dropping = False
            else:
                if not dropping:
                    out.append("…（叙述已压缩）")
                    dropping = True
    out.append("")
    out.append(MARK)
    return head + "\n" + "\n".join(out) + "\n\n" + tail


def one(src: str, dst: str) -> None:
    text = open(src, encoding="utf-8").read()
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(compress_text(text))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", action="store_true", help="目录模式")
    ap.add_argument("src")
    ap.add_argument("dst")
    a = ap.parse_args()

    if a.dir:
        os.makedirs(a.dst, exist_ok=True)
        n = 0
        for name in sorted(os.listdir(a.src)):
            if name.endswith(".md"):
                one(os.path.join(a.src, name), os.path.join(a.dst, name))
                n += 1
        print(f'{{"compressed": {n}}}')
    else:
        one(a.src, a.dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
