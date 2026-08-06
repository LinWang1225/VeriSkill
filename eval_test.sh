#!/bin/bash
# 轮外 test 评估 —— 从轮内移出来的（48 条逐条 oracle 重解耗时超过整轮预算，
# 放轮内必然被 ROUND_TIMEOUT 砍掉；r10 实测跑到第 31 条被 SIGKILL）。
#
# 用法:  bash eval_test.sh [并发数]
#   并发默认 6。用**当前**技能库跑全部 split=test 条目，结果追加进
#   stats/test_curve.jsonl。不放回、不写新轨迹、不动 test 池。
#
# 与 driver 并发跑是安全的：只读技能库、只写自己的目录。
set -u
VS="$(cd "$(dirname "$0")" && pwd)"
cd "$VS" || exit 1
set -a; . ./env.sh; set +a
PAR="${1:-6}"

R=$(python3 -c "import json;print(json.load(open('ledger.json'))['round'])")
G=$(python3 -c "import json;print(json.load(open('ledger.json'))['g_version'])")
H=$(python3 - <<'PY'
import hashlib, os
h = hashlib.sha1()
for d in ("workspace/actor_skills", "workspace/critics"):
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        p = os.path.join(d, f)
        if os.path.isfile(p):
            h.update(f.encode()); h.update(open(p, 'rb').read())
print(h.hexdigest()[:12])
PY
)
D="stats/test_eval_r${R}"
mkdir -p "$D" stats
python3 -c "
import json
print('\n'.join(x['id'] for x in json.load(open('pool/meta.json'))['items'] if x['split']=='test'))
" > "$D/items.list"
N=$(wc -l < "$D/items.list" | tr -d ' ')
echo "[$(date '+%H:%M:%S')] test 评估 r=$R g_version=$G skill_hash=$H  共 $N 条  并发 $PAR"

one() {
  it="$1"; D="$2"
  [ -s "$D/$it.out" ] && return
  bash oracle_run.sh "pool/traj/$it.md" > "$D/$it.out" 2> "$D/$it.err"
}
export -f one
xargs -P "$PAR" -I{} bash -c "one {} '$D'" < "$D/items.list"

python3 - "$D" "$R" "$G" "$H" <<'PY'
import json, os, re, sys
d, r, g, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
ok = bad = envfail = 0
for it in open(os.path.join(d, "items.list")).read().split():
    p = os.path.join(d, f"{it}.out")
    if not (os.path.exists(p) and os.path.getsize(p)):
        envfail += 1; continue
    txt = open(p, encoding="utf-8", errors="replace").read()
    m = None
    for line in txt.splitlines():
        line = line.strip()
        if line.startswith("{") and '"oracle_pass"' in line:
            mm = re.search(r'"oracle_pass":\s*(true|false)', line)
            if mm: m = mm.group(1) == "true"
    if m is None: envfail += 1
    elif m: ok += 1
    else: bad += 1
n = ok + bad
row = {"round": r, "g_version": g, "skill_hash": h,
       "pass": ok, "total": n, "rate": round(ok / n, 4) if n else None,
       "env_fail": envfail}
with open("stats/test_curve.jsonl", "a") as f:
    f.write(json.dumps(row) + "\n")
print(f"  → {ok}/{n} = {ok/n:.1%}   环境故障剔除 {envfail}" if n else "  → 全部失败")
PY
echo "[$(date '+%H:%M:%S')] DONE"
