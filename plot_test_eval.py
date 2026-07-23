#!/usr/bin/env python3
"""读 test 评估时间序列，画「成功率随 skill 演进」变化图。

  python3 plot_test_eval.py [stats/test_eval.jsonl]

输入：eval_test.sh 追加的每行一个 summary：
  {"round":10,"g_version":3,"skill_hash":"...","n_sampled":20,
   "n_judged":19,"n_pass":8,"n_env_fail":1,"success_rate":0.42,"sample":[...]}

输出（落在输入文件同目录，默认 stats/）：
  test_eval.svg   纯 stdlib 手画折线图（CJK 由浏览器渲染，任何环境都能出）
  test_eval.png   matplotlib 可用时额外输出（英文标注，避免缺中文字体）
stdout：数据表 + ASCII 折线。

无依赖、空/单点/多点均不崩。
"""
import json
import os
import sys

IN = sys.argv[1] if len(sys.argv) > 1 else "stats/test_eval.jsonl"
OUT_DIR = os.path.dirname(os.path.abspath(IN)) or "."


def load(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if "round" not in d:
                continue
            rows.append(d)
    rows.sort(key=lambda d: d["round"])
    return rows


def ascii_chart(rows):
    if not rows:
        print("（暂无 checkpoint，无法画图）")
        return
    print("成功率演进：")
    print(f"{'轮':>4}  {'g_version':>9}  {'通过/已判':>10}  图")
    W = 30
    for d in rows:
        r = d.get("success_rate")
        judged = d.get("n_judged", 0)
        passed = d.get("n_pass", 0)
        env = d.get("n_env_fail", 0)
        rate_txt = f"{r:.1%}" if isinstance(r, (int, float)) else "  -  "
        bar = ("#" * int(round(r * W))) if isinstance(r, (int, float)) else ("?" * 3)
        env_txt = f" [环境故障 {env}]" if env else ""
        print(f"{d['round']:>4}  {d.get('g_version','?'):>9}  "
              f"{passed}/{judged:>3}{env_txt:<14} {bar} {rate_txt}")


def svg_chart(rows, out):
    W, H = 940, 540
    L, R, T, B = 80, 40, 60, 80
    pw, ph = W - L - R, H - T - B

    def xp(i, n):
        if n <= 1:
            return L + pw / 2
        return L + pw * i / (n - 1)

    def yp(v):
        v = 0 if v is None else max(0.0, min(1.0, float(v)))
        return T + ph * (1 - v)

    parts = [
        f'<?xml version="1.0" encoding="utf-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'font-family="sans-serif" font-size="12">',
        f'<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{W/2}" y="30" text-anchor="middle" font-size="16" '
        f'font-weight="bold">Test 成功率随 skill 演进</text>',
    ]
    if not rows:
        parts.append(f'<text x="{W/2}" y="{H/2}" text-anchor="middle" '
                      f'fill="#888">暂无 checkpoint 数据</text>')
        parts.append("</svg>")
        open(out, "w", encoding="utf-8").write("\n".join(parts))
        return

    # 坐标轴
    parts.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{T+ph}" '
                 f'stroke="#333"/>')
    parts.append(f'<line x1="{L}" y1="{T+ph}" x2="{L+pw}" y2="{T+ph}" '
                 f'stroke="#333"/>')
    for v in (0, 0.25, 0.5, 0.75, 1.0):
        y = yp(v)
        parts.append(f'<line x1="{L}" y1="{y}" x2="{L+pw}" y2="{y}" '
                     f'stroke="#eee"/>')
        parts.append(f'<text x="{L-8}" y="{y+4}" text-anchor="end" '
                     f'fill="#666">{v:.0%}</text>')
    parts.append(f'<text x="{L-50}" y="{T+ph/2}" transform="rotate(-90 '
                 f'{L-50} {T+ph/2})" text-anchor="middle">test 成功率</text>')
    parts.append(f'<text x="{L+pw/2}" y="{H-15}" text-anchor="middle">'
                 f'轮次（标注为 g_version）</text>')

    n = len(rows)
    pts = []
    for i, d in enumerate(rows):
        r = d.get("success_rate")
        x = xp(i, n)
        if isinstance(r, (int, float)):
            y = yp(r)
            pts.append((x, y))
        else:
            pts.append(None)

    # 折线（跳过 None，断开）
    seg = []
    for p in pts:
        if p is None:
            if len(seg) >= 2:
                pts_attr = " ".join(f"{x},{y}" for x, y in seg)
                parts.append(f'<polyline points="{pts_attr}" fill="none" '
                             f'stroke="#2b6cb0" stroke-width="2"/>')
            seg = []
        else:
            seg.append(p)
    if len(seg) >= 2:
        pts_attr = " ".join(f"{x},{y}" for x, y in seg)
        parts.append(f'<polyline points="{pts_attr}" fill="none" '
                     f'stroke="#2b6cb0" stroke-width="2"/>')

    # 点 + 标注
    for i, d in enumerate(rows):
        x = xp(i, n)
        r = d.get("success_rate")
        gv = d.get("g_version", "?")
        judged = d.get("n_judged", 0)
        passed = d.get("n_pass", 0)
        rate_txt = f"{r:.0%}" if isinstance(r, (int, float)) else "n/a"
        if isinstance(r, (int, float)):
            y = yp(r)
            parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#2b6cb0"/>')
            parts.append(f'<text x="{x}" y="{y-10}" text-anchor="middle" '
                         f'font-size="11" fill="#2b6cb0">{rate_txt}</text>')
        else:
            y = T + ph
            parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="none" '
                         f'stroke="#cc4444"/>')
        parts.append(f'<text x="{x}" y="{T+ph+18}" text-anchor="middle" '
                     f'font-size="11">r{d["round"]}</text>')
        parts.append(f'<text x="{x}" y="{T+ph+34}" text-anchor="middle" '
                     f'font-size="10" fill="#888">gv{gv}</text>')
        parts.append(f'<text x="{x}" y="{T+ph+48}" text-anchor="middle" '
                     f'font-size="9" fill="#aaa">{passed}/{judged}</text>')

    parts.append("</svg>")
    open(out, "w", encoding="utf-8").write("\n".join(parts))


def mpl_chart(rows, out):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"[info] matplotlib 不可用（{e}），跳过 PNG，仅输出 SVG。")
        return False
    xs = [d["round"] for d in rows]
    ys = [d.get("success_rate") for d in rows]
    ys_clean = [None if y is None else y for y in ys]
    fig, ax = plt.subplots(figsize=(9.4, 5.4))
    cx = [x for x, y in zip(xs, ys_clean) if y is not None]
    cy = [y for y in ys_clean if y is not None]
    if cx:
        ax.plot(cx, cy, "-o", color="#2b6cb0")
    for x, y, d in zip(xs, ys_clean, rows):
        if y is None:
            ax.plot(x, 0, "o", mfc="none", mec="#cc4444")
        else:
            ax.annotate(f"{y:.0%}", (x, y), textcoords="offset points",
                        xytext=(0, 8), ha="center", fontsize=9)
        ax.annotate(f"r{d['round']}\ngv{d.get('g_version','?')}", (x, 0),
                    textcoords="offset points", xytext=(0, -16),
                    ha="center", fontsize=8, color="#666")
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlabel("round (g_version)")
    ax.set_ylabel("test success rate")
    ax.set_title("Test success rate vs skill evolution")
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return True


def main():
    rows = load(IN)
    ascii_chart(rows)
    svg = os.path.join(OUT_DIR, "test_eval.svg")
    svg_chart(rows, svg)
    print(f"\nSVG  -> {svg}")
    png = os.path.join(OUT_DIR, "test_eval.png")
    if mpl_chart(rows, png):
        print(f"PNG  -> {png}")


if __name__ == "__main__":
    main()
