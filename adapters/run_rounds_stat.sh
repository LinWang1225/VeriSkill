#!/bin/bash
# 窄域(热力学/物化)确定性每轮驱动器。每轮一个短命 claude，bash 强制 ledger 前进。
# checker 为纯数值确定性(零LLM)，oracle 重解快，故单轮上限可小于 HLE。
set -uo pipefail
VS=/Users/danyangchen/Documents/openclaw-rl/stat_run/veriskill
cd "$VS" || exit 1
source env.sh
ROUNDS="${1:-50}"
MODEL="${VERISKILL_MODEL:-deepseek-v4-flash-260601}"
PARAMS="rounds=$ROUNDS batch=${BATCH:-16} audit_frac=${AF:-0.25} replay_K=999 train_ratio=0.8 split_seed=0 consolidate_every=6 edit_budget=15 final_test_max=50"
RTO="${ROUND_TIMEOUT:-5400}"
DLOG="driver_$(date +%m%d_%H%M).log"
# --- 可移植超时（macOS 无 timeout/gtimeout 时用后台看门狗）---
_to(){
  local s="$1"; shift
  if command -v timeout >/dev/null 2>&1; then timeout "$s" "$@"; return $?; fi
  if command -v gtimeout >/dev/null 2>&1; then gtimeout "$s" "$@"; return $?; fi
  "$@" & local p=$!
  ( sleep "$s"; kill -9 "$p" 2>/dev/null ) >/dev/null 2>&1 & local w=$!
  wait "$p"; local rc=$?
  kill -9 "$w" 2>/dev/null; wait "$w" 2>/dev/null
  return $rc
}

rget(){ python3 -c "import json;print(json.load(open('ledger.json')).get('round',0))" 2>/dev/null || echo 0; }
say(){ echo "[driver $(date '+%F %T')] $*" | tee -a "$DLOG"; }

one_round(){
  _to "$RTO" claude -p "You are executing EXACTLY ONE round of the VeriSkill co-evolution loop: round $1.
Read .claude/commands/veriskill-loop.md and follow its 「每轮流程」 steps 1–7 for round $1 ONLY, PLUS step 8 (consolidate) if $1 % 6 == 0. Params: $PARAMS.
Pool = SciBench thermodynamics/physical-chemistry problems (narrow domain, recurring error modes). The pool is already registered — do NOT re-run Setup. Checkers under pool/checkers/ are deterministic numeric comparisons (official rel_tol=0.05, zero model calls) — use oracle_run.sh as-is.
HARD RULES:
- Do the FULL round: sample -> verify -> **Oracle audit (step 3, MUST run oracle_run.sh on the audit queue)** -> **d-improve (step 4)** -> **g-improve (step 5)** -> gate (step 6) -> 记账 (step 7). A round WITHOUT oracle audit and without invoking d-improve/g-improve is INVALID.
- **RATE LIMIT**: the endpoint has very low concurrency. Run oracle_run.sh calls **STRICTLY SERIALLY**, one at a time; do not background them. **Also dispatch d-improve and g-improve SEQUENTIALLY (one Task at a time, wait for the first to finish before starting the second) — never in parallel**; parallel dispatch has caused "Response stalled mid-stream" failures that killed the whole round.
- On step 7 记账 you MUST set ledger.round=$1.
- When ledger.round==$1 is committed, STOP immediately. Do NOT start round $(($1+1)).
$2" \
    --model "$MODEL" --dangerously-skip-permissions >> "$3" 2>&1
}

say "START target=$ROUNDS model=$MODEL params={$PARAMS}"
while :; do
  cur=$(rget); nxt=$((cur+1))
  if [ "$cur" -ge "$ROUNDS" ]; then say "DONE: ledger.round=$cur >= $ROUNDS"; break; fi
  rlog="round_${nxt}.log"
  say "=== round $nxt START (ledger=$cur) log=$rlog ==="
  attempt=1; new=$cur
  while [ "$attempt" -le 3 ]; do
    note=""
    [ "$attempt" -gt 1 ] && note="NOTE: a previous attempt at round $nxt did not commit. Reuse any existing rounds/r$nxt/ artifacts, finish the missing steps, and commit ledger.round=$nxt."
    one_round "$nxt" "$note" "$rlog"; rc=$?
    new=$(rget); say "round $nxt attempt $attempt: claude rc=$rc, ledger $cur -> $new"
    [ "$new" -gt "$cur" ] && break
    if [ "$attempt" -lt 3 ]; then
      say "未提交（可能瞬时 429/限流）— 退避 ${BACKOFF:-600}s 后重试"
      sleep "${BACKOFF:-600}"
    fi
    attempt=$((attempt+1))
  done
  if [ "$new" -le "$cur" ]; then say "ABORT: round $nxt 三次未提交; ledger 停在 $cur. See $rlog"; exit 2; fi
done
say "running 收尾 (final_test)"
_to "$RTO" claude -p "Execute ONLY the 「收尾」 section of .claude/commands/veriskill-loop.md: 对全部 split=test 条目跑 verify.sh 算 fail_rate，逐条 oracle_run.sh(不放回)，统计 g_pass_rate 与 D 的 TP/FP/FN/TN，存 rounds/final_test/。务必报告 D 的 recall/precision/TP/FP/FN/TN，而不只是 accuracy。不得再改 G/D。" \
  --model "$MODEL" --dangerously-skip-permissions >> "final_test.log" 2>&1
say "EXIT ledger.round=$(rget)"
