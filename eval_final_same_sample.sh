#!/usr/bin/env bash
# Held-out final evaluation for VeriSkill.
# Reruns the current G on a deterministic random test sample, asks D to judge the
# exact new trajectories, and writes same-sample G/D metrics. The test pool is
# never modified and the outputs must not be fed back to G or D.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
META=""
OUT_DIR=""
MAX="${VERISKILL_FINAL_TEST_MAX:-50}"
SEED=0
ROUND=""
GVERSION=""
SERIES=""

usage() {
  cat <<'USAGE' >&2
Usage: bash eval_final_same_sample.sh --meta pool/meta.json \
       --out-dir rounds/final_test [--max N] [--seed N] \
       --round N --g-version N [--series stats/test_eval.jsonl]
USAGE
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
[[ "$MAX" =~ ^[0-9]+$ ]] && [[ "$SEED" =~ ^-?[0-9]+$ ]] \
  && [[ "$ROUND" =~ ^[0-9]+$ ]] && [[ "$GVERSION" =~ ^[0-9]+$ ]] \
  || { echo "--max/--seed/--round/--g-version 必须是整数" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "缺少 python3" >&2; exit 1; }

TRAJ_DIR="${VERISKILL_TRAJ:-$HERE/pool/traj}"
JOBS="${VERISKILL_JOBS:-4}"
mkdir -p "$OUT_DIR/new_traj" "$OUT_DIR/oracle" "$OUT_DIR/stderr"
[ -z "$SERIES" ] || mkdir -p "$(dirname "$SERIES")"

python3 - "$META" "$TRAJ_DIR" "$OUT_DIR/sample.list" "$SEED" "$MAX" <<'PY'
import json, os, random, sys
meta, traj_dir, out, seed, maximum = sys.argv[1:]
items = json.load(open(meta, encoding="utf-8")).get("items", [])
ids = sorted(x["id"] for x in items if x.get("split") == "test")
ids = [x for x in ids if os.path.isfile(os.path.join(traj_dir, x + ".md"))]
random.seed(int(seed))
if len(ids) > int(maximum):
    ids = sorted(random.sample(ids, int(maximum)))
with open(out, "w", encoding="utf-8") as f:
    f.write("".join(x + "\n" for x in ids))
print(json.dumps({"sampled": len(ids), "seed": int(seed)}, ensure_ascii=False))
PY

FP="$(bash "$HERE/oracle_run.sh" --fingerprint)"
export HERE TRAJ_DIR OUT_DIR FP

eval_one() {
  local id="$1" rc
  set +e
  bash "$HERE/oracle_run.sh" "$TRAJ_DIR/$id.md" \
    --new-traj-out "$OUT_DIR/new_traj/$id.md" \
    > "$OUT_DIR/oracle/$id.json" 2> "$OUT_DIR/stderr/$id.err"
  rc=$?
  # rc=6 is a stable unscored condition; retrying cannot create truth.
  if [ "$rc" -ne 0 ] && [ "$rc" -ne 6 ]; then
    bash "$HERE/oracle_run.sh" "$TRAJ_DIR/$id.md" \
      --new-traj-out "$OUT_DIR/new_traj/$id.md" \
      > "$OUT_DIR/oracle/$id.json" 2> "$OUT_DIR/stderr/$id.err"
    rc=$?
  fi
  set -e
  echo "$rc" > "$OUT_DIR/oracle/$id.rc"
}
export -f eval_one

if [ -s "$OUT_DIR/sample.list" ]; then
  xargs -P "$JOBS" -I{} bash -c 'eval_one "$1"' _ {} < "$OUT_DIR/sample.list"
fi

python3 - "$OUT_DIR" <<'PY'
import json, os, sys
root = sys.argv[1]
ids = [x.strip() for x in open(os.path.join(root, "sample.list"), encoding="utf-8") if x.strip()]
judged = []
for item in ids:
    try:
        rc = int(open(os.path.join(root, "oracle", item + ".rc")).read().strip())
    except Exception:
        rc = -1
    op = os.path.join(root, "oracle", item + ".json")
    tp = os.path.join(root, "new_traj", item + ".md")
    if rc != 0 or not os.path.isfile(op) or not os.path.isfile(tp):
        continue
    try:
        obj = json.load(open(op, encoding="utf-8"))
    except Exception:
        continue
    if isinstance(obj.get("oracle_pass"), bool):
        judged.append(item)
with open(os.path.join(root, "judged.list"), "w", encoding="utf-8") as f:
    f.write("".join(x + "\n" for x in judged))
PY

: > "$OUT_DIR/post_verdicts.jsonl"
if [ -s "$OUT_DIR/judged.list" ]; then
  VERISKILL_TRAJ="$OUT_DIR/new_traj" \
  VERISKILL_TRAJ_FULL="$OUT_DIR/new_traj" \
    bash "$HERE/verify.sh" "$OUT_DIR/judged.list" "$OUT_DIR/post_verdicts.jsonl"
fi

python3 - "$OUT_DIR" "$FP" "$ROUND" "$GVERSION" "$SERIES" <<'PY'
from collections import Counter
import hashlib
import json, os, sys
root, fp, round_, g_version, series = sys.argv[1:]
round_ = int(round_)
g_version = int(g_version)
ids = [x.strip() for x in open(os.path.join(root, "sample.list"), encoding="utf-8") if x.strip()]
verdicts = {}
vp = os.path.join(root, "post_verdicts.jsonl")
if os.path.isfile(vp):
    for line in open(vp, encoding="utf-8"):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("item"):
            verdicts[str(row["item"])] = row

counts = Counter()
rows = []
n_pass = n_judged = n_unscored = n_env = n_missing_d = 0
for item in ids:
    try:
        rc = int(open(os.path.join(root, "oracle", item + ".rc")).read().strip())
    except Exception:
        rc = -1
    if rc == 6:
        n_unscored += 1
        continue
    if rc != 0:
        n_env += 1
        continue
    try:
        oracle = json.load(open(os.path.join(root, "oracle", item + ".json"), encoding="utf-8"))
    except Exception:
        n_env += 1
        continue
    opass = oracle.get("oracle_pass")
    if not isinstance(opass, bool):
        n_env += 1
        continue
    n_judged += 1
    n_pass += int(opass)
    d = verdicts.get(item)
    if not d or d.get("verdict") not in ("pass", "fail"):
        n_missing_d += 1
        continue
    dfail = d["verdict"] == "fail"
    kind = "TP" if dfail and not opass else "FP" if dfail and opass else "FN" if (not dfail and not opass) else "TN"
    counts[kind] += 1
    row = {
        "item": item,
        "segment": "final-test-random",
        "selection_d_verdict": None,
        "d_verdict": d["verdict"],
        "same_sample": True,
        "oracle_pass": opass,
        "kind": kind,
        "skill_hash": oracle.get("skill_hash", fp) or fp,
        "truth_source": oracle.get("truth_source", "unknown"),
        "rules_hit": d.get("rules_hit", []),
        "normalized_score": d.get("normalized_score"),
        "confidence": d.get("confidence"),
        "oracle_evidence": oracle.get("evidence", ""),
        "skill_result": (oracle.get("skill_result") or "")[:500],
    }
    rows.append(row)

with open(os.path.join(root, "audit.jsonl"), "w", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def div(a, b):
    return None if not b else a / b

tp, fp_, fn, tn = (counts[x] for x in ("TP", "FP", "FN", "TN"))
tpr = div(tp, tp + fn)
tnr = div(tn, tn + fp_)
sample_hash = hashlib.sha256(("\n".join(ids) + "\n").encode()).hexdigest()[:16]
g_rate = div(n_pass, n_judged)
summary = {
    # eval_test.sh-compatible fields, so plot_test_eval.py can consume the row.
    "round": round_,
    "g_version": g_version,
    "skill_hash": fp,
    "sample_hash": sample_hash,
    "evaluation_mode": "held-out-same-sample",
    "sample": ids,
    "n_sampled": len(ids),
    "n_judged": n_judged,
    "n_pass": n_pass,
    "n_env_fail": n_env,
    "n_unscored": n_unscored,
    "success_rate": g_rate,
    # Explicit aliases used by the result report.
    "n_oracle_judged": n_judged,
    "n_oracle_pass": n_pass,
    "g_success_rate": g_rate,
    "n_missing_d": n_missing_d,
    "same_sample_d_support": sum(counts.values()),
    "d_counts": {x: counts[x] for x in ("TP", "FP", "FN", "TN")},
    "d_fpr": div(fp_, fp_ + tn),
    "d_fnr": div(fn, fn + tp),
    "d_balanced_accuracy": None if tpr is None or tnr is None else (tpr + tnr) / 2,
    "selection": "uniform random sample of split=test; deterministic seed",
}
with open(os.path.join(root, "summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

if series:
    # The final same-sample point is authoritative for this round. Replace any
    # earlier G-only checkpoint at the same round to keep the plot single-valued.
    kept = []
    if os.path.isfile(series):
        for raw in open(series, encoding="utf-8"):
            line = raw.strip()
            if not line:
                continue
            try:
                old = json.loads(line)
            except Exception:
                kept.append(line)
                continue
            if old.get("round") == round_:
                continue
            kept.append(line)
    kept.append(json.dumps(summary, ensure_ascii=False))
    def order(line):
        try:
            return (0, int(json.loads(line).get("round", 10**9)))
        except Exception:
            return (1, 10**9)
    kept.sort(key=order)
    tmp = series + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for line in kept:
            f.write(line + "\n")
    os.replace(tmp, series)

print(json.dumps(summary, ensure_ascii=False))
PY
