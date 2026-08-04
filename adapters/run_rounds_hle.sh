#!/bin/bash
# HLE 确定性每轮驱动器：bash 控循环，每轮一个短命 claude 做「恰好一轮」，
# 每轮后校验 ledger 真 +1，没涨重试一次再 ABORT。setup_hle.sh 已建好池/注册，跳 Setup。
set -uo pipefail
VS=/root/data/hle_run/veriskill
cd "$VS" || exit 1
source env.sh
ROUNDS="${1:-50}"
MODEL="${VERISKILL_MODEL:-deepseek-v4-flash-260601}"
PARAMS="rounds=$ROUNDS batch=16 audit_frac=0.25 replay_K=999 train_ratio=0.8 split_seed=0 consolidate_every=6 edit_budget=15 final_test_max=50"
RTO="${ROUND_TIMEOUT:-5400}"
DLOG="driver_$(date +%m%d_%H%M).log"
rget(){ python3 -c "import json;print(json.load(open('ledger.json')).get('round',0))" 2>/dev/null || echo 0; }
say(){ echo "[driver $(date '+%F %T')] $*" | tee -a "$DLOG"; }

one_round(){
  timeout "$RTO" claude -p "You are executing EXACTLY ONE round of the VeriSkill co-evolution loop: round $1.
Read .claude/commands/veriskill-loop.md and follow its 「每轮流程」 steps 1–7 for round $1 ONLY, PLUS step 8 (consolidate) if $1 % 6 == 0. Params: $PARAMS.
The workspace pool is HLE math problems; the pool is already registered (do NOT re-run Setup). Checkers under pool/checkers/ already judge correctness (official HLE judge) — use oracle_run.sh as-is.
HARD RULES:
- Do the FULL round: sample -> verify -> **Oracle audit (step 3, MUST run oracle_run.sh on the audit queue)** -> **d-improve (step 4)** -> **g-improve (step 5)** -> gate (step 6) -> 记账 (step 7). A round WITHOUT oracle audit and without invoking d-improve/g-improve is INVALID.
- **RATE LIMIT (重要)**: the ark endpoint rejects too-frequent requests (429 AccountRateLimitExceeded). Run the Oracle audit oracle_run.sh calls **STRICTLY SERIALLY — one at a time, wait for each to finish before starting the next, do NOT background them or run them concurrently**. Likewise do not launch many parallel subprocesses at once. Keeping concurrency low avoids the 429 hangs.
- On step 7 记账 you MUST set ledger.round=$1.
- When ledger.round==$1 is committed, STOP immediately. Do NOT start round $(($1+1)). Do NOT touch any other round.
$2" \
    --model "$MODEL" --dangerously-skip-permissions >> "$3" 2>&1
}

say "START target=$ROUNDS model=$MODEL params={$PARAMS}"
# r0 快照（setup 没做）
[ -d history/r0_G_initial ] || { mkdir -p history/r0_G_initial history/r0_D_initial; cp -R workspace/actor_skills/. history/r0_G_initial/ 2>/dev/null; cp -R workspace/critics/. history/r0_D_initial/ 2>/dev/null; }

while :; do
  cur=$(rget); nxt=$((cur+1))
  if [ "$cur" -ge "$ROUNDS" ]; then say "DONE: ledger.round=$cur >= $ROUNDS"; break; fi
  rlog="round_${nxt}.log"
  say "=== round $nxt START (ledger=$cur) log=$rlog ==="
  one_round "$nxt" "" "$rlog"; rc=$?
  new=$(rget); say "round $nxt: claude rc=$rc, ledger $cur -> $new"
  if [ "$new" -le "$cur" ]; then
    say "round $nxt 未提交 — 重试一次"
    one_round "$nxt" "NOTE: previous attempt at round $nxt did not commit. Reuse existing rounds/r$nxt/ artifacts, finish missing steps, commit ledger.round=$nxt." "$rlog"
    new=$(rget); say "round $nxt retry: ledger now $new"
    if [ "$new" -le "$cur" ]; then say "ABORT: round $nxt failed twice; ledger stuck at $cur. See $rlog"; exit 2; fi
  fi
done
say "running 收尾 (final_test)"
timeout "$RTO" claude -p "Execute ONLY the 「收尾」 section of .claude/commands/veriskill-loop.md: 对全部 split=test 条目跑 verify.sh 算 fail_rate，抽 final_test_max=50 条(HLE test 仅14条,全跑)逐条 oracle_run.sh(不放回)，统计 g_pass_rate 与 D 的 TP/FP/FN/TN，存 rounds/final_test/。不得再改 G/D。Stop when final_test summary is written." \
  --model "$MODEL" --dangerously-skip-permissions >> "final_test.log" 2>&1
say "EXIT ledger.round=$(rget)"
