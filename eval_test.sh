#!/usr/bin/env bash
# eval_test.sh -- 周期/收尾评估：用**当前**解题技能库把 test 集真实重跑
# 一遍，统计成功率，并把 checkpoint 追加进时间序列供画图。
#
#   bash eval_test.sh --meta pool/meta.json --out-dir rounds/r10/test_eval \
#       --max 50 --seed 0 --round 10 --g-version 3 \
#       [--series stats/test_eval.jsonl]
#
# 它是 verify.sh / oracle_run.sh 的同层「永不编辑」核心脚本：编排者
# 只调用，不改它。和收尾的 test 重跑同一套抽样规则（按 ID 排序 ->
# random.seed(0) -> 取前 --max），保证各 checkpoint 可比。
#
# 关键约束（同收尾）：
#   - 调 oracle_run.sh **不带 --new-traj-out** -> test 池零改动，只读。
#   - 只写自己的 out-dir 与（可选）--series 文件；**绝不**碰
#     stats/audited.json、stats/audit_tally.json，也不喂 G/D。
#   - 结果纯监测：不参与停止/收敛判断。
#
# 成功率 = n_pass / n_judged（exit 0 = 已判；非 0 = 环境故障，计入
# n_env_fail 不计入分母，与收尾口径一致）。n_judged=0 记 null。
#
# 退出码：0 正常（哪怕 0 条 test）；1 参数/文件问题。

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/backend.sh
source "$HERE/lib/backend.sh"   # 复用 JOBS / TIMEOUT / preflight 约定

META=""
OUT_DIR=""
MAX="${VERISKILL_FINAL_TEST_MAX:-50}"
SEED=0
ROUND=""
GVERSION=""
SERIES=""

usage() { cat <<EOF >&2
用法：bash eval_test.sh --meta <meta.json> --out-dir <dir>
      [--max N] [--seed N] --round <r> --g-version <v>
      [--series <test_eval.jsonl>]
  --meta      pool/meta.json
  --out-dir   本 checkpoint 输出目录（结果/汇总落点）
  --max       最多重跑多少条 test（默认 VERISKILL_FINAL_TEST_MAX 或 50）
  --seed      抽样随机种子（默认 0，与收尾一致）
  --round     当前轮号（写进汇总与序列）
  --g-version 当前 G 库版本（写进汇总与序列）
  --series    时间序列文件；给了就把本行汇总原子追加进去
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --meta) META="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --max) MAX="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    --round) ROUND="$2"; shift 2 ;;
    --g-version) GVERSION="$2"; shift 2 ;;
    --series) SERIES="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数：$1" >&2; usage; exit 1 ;;
  esac
done

[ -n "$META" ] && [ -n "$OUT_DIR" ] && [ -n "$ROUND" ] && [ -n "$GVERSION" ] \
  || { echo "缺必填参数（--meta/--out-dir/--round/--g-version）" >&2; usage; exit 1; }
[ -f "$META" ] || { echo "找不到 meta：$META" >&2; exit 1; }

TRAJ_DIR="${VERISKILL_TRAJ:-$HERE/pool/traj}"
JOBS="${VERISKILL_JOBS:-4}"

mkdir -p "$OUT_DIR"

# ---- 1) 取 test 抽样：按 ID 排序 -> seed -> 取前 MAX（与收尾同口径）----
python3 - "$META" "$TRAJ_DIR" "$OUT_DIR/sample.list" "$SEED" "$MAX" <<'PY'
import json, random, sys, os
meta = json.load(open(sys.argv[1]))
traj_dir = sys.argv[2]
out = sys.argv[3]
seed = int(sys.argv[4])
mx = int(sys.argv[5])
ids = sorted(it["id"] for it in meta.get("items", []) if it.get("split") == "test")
# 只留轨迹文件存在的（test 池可能不全）
ids = [i for i in ids if os.path.isfile(os.path.join(traj_dir, i + ".md"))]
random.seed(seed)
if len(ids) > mx:
    # 与收尾一致：seed(0) 后 sample
    ids = sorted(random.sample(ids, mx))
with open(out, "w") as f:
    f.write("".join(i + "\n" for i in ids))
print(f"抽样：{len(ids)} 条 test（上限 {mx}）", file=sys.stderr)
PY

# ---- 2) 当前技能指纹（不花钱，只 shasum）----
FP="$(bash "$HERE/oracle_run.sh" --fingerprint)"

# ---- 3) 并发重跑：每条 oracle_run.sh 不带 --new-traj-out ----
TMP="$(mktemp -d "${TMPDIR:-/tmp}/veriskill-eval-XXXXXX")"
trap 'rm -rf "${TMP:-}"' EXIT

# 进度日志：把 eval 的后台进展落进 loop 日志（VERISKILL_LOOP_LOG 由
# launch_loop_101.sh 导出，指向当前 loop_*.log）。未设置则静默不写。
# 解决「基线/成功率 eval 跑起来后 loop 日志一片空白、不知道在干啥」的问题。
_log() {
  [ -n "${VERISKILL_LOOP_LOG:-}" ] || return 0
  printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >> "$VERISKILL_LOOP_LOG"
}

eval_one() {  # <id>
  local id="$1" out err rc
  out="$TMP/$id.out"; err="$TMP/$id.err"
  # 关闭 errexit 以真实捕获 oracle_run.sh 的退出码（含瞬时失败）。不能
  # 用 `cmd || true`：那会把 rc 永远罩成 0，使下面的重试成为死代码，
  # 并让 results.jsonl 里 rc 恒为 0、用空的 stdout 解析失败掩盖真因。
  set +e
  bash "$HERE/oracle_run.sh" "$TRAJ_DIR/$id.md" > "$out" 2>"$err"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    # 瞬时超时/解析失败占大头，重试一次（对齐审计步）
    bash "$HERE/oracle_run.sh" "$TRAJ_DIR/$id.md" > "$out" 2>"$err"
    rc=$?
  fi
  set -e
  if [ "$rc" -eq 0 ] && [ -s "$out" ]; then
    _log "eval r=$ROUND $id: $(python3 -c 'import json,sys;o=json.load(open(sys.argv[1]));print("pass=%s src=%s result=%r"%(o.get("oracle_pass"),o.get("truth_source",""),(o.get("skill_result") or "")[:80]))' "$out" 2>/dev/null || head -c 120 "$out")"
  else
    _log "eval r=$ROUND $id: ENV_FAIL rc=$rc - $(tail -1 "$err" 2>/dev/null)"
  fi
  echo "$rc" > "$TMP/$id.rc"
}
export -f eval_one _log
export HERE TRAJ_DIR TMP ROUND

_log "eval_test START round=$ROUND g_version=$GVERSION fp=$FP items=$(wc -l < "$OUT_DIR/sample.list" 2>/dev/null || echo 0) jobs=$JOBS timeout=${VERISKILL_TIMEOUT:-600}"

if [ -s "$OUT_DIR/sample.list" ]; then
  xargs -P "$JOBS" -I{} bash -c 'eval_one "$1"' _ {} < "$OUT_DIR/sample.list"
fi

# ---- 3b) 延后重试：主批次跑完后，对瞬时失败(429/后端抖动)的条目再补跑一次。
# 主批次里 eval_one 的立即重试只隔 15s，扛不过 >15s 的 429 窗口；这里等到其它
# 题都跑完、429 多半已过再补跑（顺序跑，不再加并发，避免又把端点打 429）。
# 模型自报的"环境故障"(数据真缺)跳过——重试也救不回，白烧调用。
deferred=""
if [ -s "$OUT_DIR/sample.list" ]; then
  while IFS= read -r id; do
    [ -n "$id" ] || continue
    rc=$(cat "$TMP/$id.rc" 2>/dev/null || echo 0)
    if [ "$rc" -ne 0 ] || ! [ -s "$TMP/$id.out" ]; then
      grep -q '环境故障：' "$TMP/$id.err" 2>/dev/null && continue   # 模型自报，跳过
      deferred="$deferred $id"
    fi
  done < "$OUT_DIR/sample.list"
fi
if [ -n "$deferred" ]; then
  _log "eval_test RETRY round=$ROUND: defer-retrying transient failures:$deferred"
  for id in $deferred; do
    [ -n "$id" ] || continue
    set +e
    bash "$HERE/oracle_run.sh" "$TRAJ_DIR/$id.md" > "$TMP/$id.out" 2>"$TMP/$id.err"
    drc=$?
    set -e
    echo "$drc" > "$TMP/$id.rc"
    if [ "$drc" -eq 0 ] && [ -s "$TMP/$id.out" ]; then
      _log "eval r=$ROUND $id: RECOVERED $(python3 -c 'import json,sys;o=json.load(open(sys.argv[1]));print("pass=%s src=%s result=%r"%(o.get("oracle_pass"),o.get("truth_source",""),(o.get("skill_result") or "")[:80]))' "$TMP/$id.out" 2>/dev/null || head -c 120 "$TMP/$id.out")"
    else
      _log "eval r=$ROUND $id: still ENV_FAIL rc=$drc after defer-retry - $(tail -1 "$TMP/$id.err" 2>/dev/null)"
    fi
  done
else
  _log "eval_test RETRY round=$ROUND: no transient failures to defer-retry"
fi

# ---- 4) 汇总：逐条解析，写 results.jsonl + summary.json，必要时追加序列 ----
python3 - "$OUT_DIR" "$TMP" "$ROUND" "$GVERSION" "$FP" "$SERIES" <<'PY'
import json, os, sys, time
out_dir, tmp, round_, gv, fp, series = sys.argv[1:7]
round_ = int(round_); gv = int(gv)

sample = [l.strip() for l in open(os.path.join(out_dir, "sample.list")) if l.strip()]
rows = []
n_judged = n_pass = n_env_fail = 0
for id_ in sample:
    rc_path = os.path.join(tmp, f"{id_}.rc")
    rc = -1
    if os.path.isfile(rc_path):
        try: rc = int(open(rc_path).read().strip() or "-1")
        except ValueError: rc = -1
    rec = {"item": id_, "oracle_pass": None, "truth_source": "",
           "skill_hash": fp, "rc": rc, "error": ""}
    if rc == 0:
        try:
            o = json.load(open(os.path.join(tmp, f"{id_}.out")))
            rec["oracle_pass"] = bool(o.get("oracle_pass"))
            rec["truth_source"] = o.get("truth_source", "")
            rec["skill_hash"] = o.get("skill_hash", fp) or fp
            rec["skill_result"] = (o.get("skill_result") or "")[:500]
            n_judged += 1
            if rec["oracle_pass"]: n_pass += 1
        except Exception as e:
            # exit 0 却解析不了：保守记 env_fail，不毒化成功率
            rec["error"] = f"parse: {e}"[:200]
            n_env_fail += 1
    else:
        err = ""
        p = os.path.join(tmp, f"{id_}.err")
        if os.path.isfile(p):
            err = open(p, errors="replace").read().strip().splitlines()
            err = err[-1] if err else ""
        rec["error"] = (err or f"rc={rc}")[:200]
        n_env_fail += 1
    rows.append(rec)

with open(os.path.join(out_dir, "results.jsonl"), "w") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

rate = (n_pass / n_judged) if n_judged else None
summary = {"round": round_, "g_version": gv, "skill_hash": fp,
           "n_sampled": len(sample), "n_judged": n_judged,
           "n_pass": n_pass, "n_env_fail": n_env_fail,
           "success_rate": rate, "sample": sample}
with open(os.path.join(out_dir, "summary.json"), "w") as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)

print(json.dumps(summary, ensure_ascii=False))

# 把 eval 终态汇总也落进 loop 日志（若有），tail -f 能看到收尾结论
_ll = os.environ.get("VERISKILL_LOOP_LOG")
if _ll:
    _rs = "null" if rate is None else f"{rate:.4f}"
    with open(_ll, "a", encoding="utf-8") as _lf:
        _lf.write(f"[{time.strftime('%H:%M:%S')}] eval_test DONE round={round_} g_version={gv} "
                  f"success_rate={_rs} pass={n_pass}/{n_judged} env_fail={n_env_fail} "
                  f"of {len(sample)}\n")

if series:
    # 原子追加一行（单行 write 在本地 fs 上原子；先去重同 round 旧行）
    lines = []
    if os.path.isfile(series):
        for l in open(series):
            l = l.strip()
            if not l: continue
            try:
                d = json.loads(l)
                if d.get("round") == round_:  # 同轮覆盖
                    continue
                lines.append(l)
            except Exception:
                lines.append(l)
    lines.append(json.dumps(summary, ensure_ascii=False))
    def _rk(l):
        try:
            return (0, json.loads(l).get("round", 10 ** 9))
        except Exception:
            return (1, 10 ** 9)
    lines.sort(key=_rk)
    tmpf = series + ".tmp"
    with open(tmpf, "w") as f:
        for l in lines:
            f.write(l + "\n")
    os.replace(tmpf, series)
PY
