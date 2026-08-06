#!/usr/bin/env bash
# 回归门 —— 用改后的 critics 重跑历史确认 TP 的轨迹，要求仍判 fail。
#
#   bash regression_gate.sh <out.jsonl> [抽样条数]
#
# 抽样条数默认 4（全跑 11 条太贵：每条一次后端调用，串行）。留空或给
# "all" 跑全量。抽样是确定性的：按轮次取最近的 N 条，保证每轮跑的是同
# 一批，退化能对得上账。
#
# 退出码：0 全部仍判 fail（通过）；1 环境/参数问题；2 有条目翻成 pass
# （退化，调用方须整库回滚到 history/r<r>_D_before/）。
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE" || exit 1

OUT="${1:-}"
N="${2:-4}"
LIST="stats/regression_tp.list"

[ -n "$OUT" ] || { echo "用法：bash regression_gate.sh <out.jsonl> [条数|all]" >&2; exit 1; }
[ -s "$LIST" ] || { echo "回归集为空，先跑 python3 lib/build_regression.py" >&2; exit 1; }
[ -d stats/tp_traj ] || { echo "找不到 stats/tp_traj" >&2; exit 1; }

TMPLIST="$(mktemp "${TMPDIR:-/tmp}/veriskill-reg-XXXXXX")"
trap 'rm -f "$TMPLIST"' EXIT
if [ "$N" = "all" ]; then
  cp "$LIST" "$TMPLIST"
else
  tail -n "$N" "$LIST" > "$TMPLIST"
fi

echo "[回归门] $(wc -l < "$TMPLIST" | tr -d ' ') 条历史 TP 轨迹，要求仍判 fail" >&2

# 只换轨迹目录，critics 用当前（待接受）的那版
VERISKILL_TRAJ="$HERE/stats/tp_traj" bash verify.sh "$TMPLIST" "$OUT"
rc=$?
if [ $rc -eq 1 ]; then
  echo "[回归门] verify.sh 环境失败，rc=1" >&2
  exit 1
fi

python3 - "$OUT" <<'PY'
import json, sys
bad, n = [], 0
for line in open(sys.argv[1]):
    line = line.strip()
    if not line:
        continue
    d = json.loads(line)
    n += 1
    if d.get("verdict") != "fail":
        bad.append((d.get("item"), d.get("adjusted_score"), (d.get("reason") or "")[:70]))
if bad:
    print(f"[回归门] 退化 {len(bad)}/{n} 条翻成 pass：", file=sys.stderr)
    for it, s, why in bad:
        print(f"    {it}  adjusted={s}  {why}", file=sys.stderr)
    sys.exit(2)
print(f"[回归门] 通过：{n}/{n} 条仍判 fail", file=sys.stderr)
PY
