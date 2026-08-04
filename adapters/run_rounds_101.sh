#!/bin/bash
# 确定性每轮驱动器：bash 控制 50 轮循环，每轮只起一个短命 claude 做「恰好一轮」。
# 漂移是单次 claude 长上下文退化导致(跳过 audit/improve/consolidate 只 verify+提交)；
# 一轮一个全新上下文就不会退化。每轮后校验 ledger 真的 +1，没涨则重试一次、再不行 ABORT。
#   bash run_rounds_101.sh [target_rounds]
set -uo pipefail
VS=/root/data/frontiersci_run/veriskill
cd "$VS" || exit 1
source env.sh
ROUNDS="${1:-50}"
MODEL="${VERISKILL_MODEL:-deepseek-v4-flash-260601}"
PARAMS="rounds=$ROUNDS batch=16 audit_frac=0.25 replay_K=999 train_ratio=0.8 split_seed=0 consolidate_every=6 edit_budget=15"
RTO="${ROUND_TIMEOUT:-5400}"   # 单轮上限 90min，防挂死
DLOG="driver_$(date +%m%d_%H%M).log"

rget(){ python3 -c "import json;print(json.load(open('ledger.json')).get('round',0))" 2>/dev/null || echo 0; }
say(){ echo "[driver $(date '+%F %T')] $*" | tee -a "$DLOG"; }

one_round(){  # $1=target round, $2=logfile, $3=extra note
  timeout "$RTO" claude -p "You are executing EXACTLY ONE round of the VeriSkill co-evolution loop: round $1.
Read .claude/commands/veriskill-loop.md and follow its 「每轮流程」 steps 1–7 for round $1 ONLY, PLUS step 8 (consolidate) if $1 % 6 == 0. Params: $PARAMS.
HARD RULES:
- Do the FULL round: sample -> verify -> **Oracle audit (step 3, MUST run oracle_run.sh on the audit queue)** -> **d-improve (step 4)** -> **g-improve (step 5)** -> gate (step 6) -> 记账 (step 7). A round WITHOUT oracle audit and without invoking d-improve/g-improve is INVALID — never skip them.
- On step 7 记账 you MUST set ledger.round=$1.
- When ledger.round==$1 is committed, STOP immediately. Do NOT start round $(($1+1)). Do NOT touch any other round.
$3" \
    --model "$MODEL" --dangerously-skip-permissions >> "$2" 2>&1
}

say "START target=$ROUNDS model=$MODEL params={$PARAMS}"

# ---- Setup once (cold start) ----
if [ "$(rget)" -eq 0 ]; then
  say "ledger.round=0 -> running Setup once"
  timeout "$RTO" claude -p "Execute ONLY the 「Setup」 section of .claude/commands/veriskill-loop.md (round 1 之前做一次): 预检(verify.sh --selftest)、建 rounds/history/stats、初始化 ledger.json、存 r0 快照、并用
  python3 lib/pool.py register --meta pool/meta.json --traj-dir pool/traj --seed 0 --train-ratio 0.8 --dataset ../olympiad.jsonl
登记轨迹池。Do NOT run any training round. Stop after Setup is done." \
    --model "$MODEL" --dangerously-skip-permissions >> "setup.log" 2>&1
  say "Setup done (ledger.round=$(rget))"
fi

# ---- per-round loop ----
while :; do
  cur=$(rget); nxt=$((cur+1))
  if [ "$cur" -ge "$ROUNDS" ]; then say "DONE: ledger.round=$cur >= $ROUNDS"; break; fi
  rlog="round_${nxt}.log"
  say "=== round $nxt START (ledger=$cur) log=$rlog ==="
  one_round "$nxt" "$rlog" ""
  rc=$?
  new=$(rget)
  say "round $nxt: claude rc=$rc, ledger $cur -> $new"
  if [ "$new" -le "$cur" ]; then
    say "round $nxt did NOT commit ledger — retry once"
    one_round "$nxt" "$rlog" "NOTE: a previous attempt at round $nxt did not commit. Reuse any existing rounds/r$nxt/ artifacts, finish the missing steps, and commit ledger.round=$nxt."
    new=$(rget)
    say "round $nxt retry: ledger now $new"
    if [ "$new" -le "$cur" ]; then
      say "ABORT: round $nxt failed twice; ledger stuck at $cur. Inspect $rlog"
      exit 2
    fi
  fi
done

# ---- 收尾 final_test ----
say "running 收尾 (final_test)"
timeout "$RTO" claude -p "Execute ONLY the 「收尾」 section of .claude/commands/veriskill-loop.md: 对全部 split=test 条目跑 verify.sh 算 fail_rate，抽 final_test_max=50 条逐条 oracle_run.sh(不放回)，统计 g_pass_rate 与 D 的 TP/FP/FN/TN，存 rounds/final_test/。不得再改 G/D。Stop when final_test summary is written." \
  --model "$MODEL" --dangerously-skip-permissions >> "final_test.log" 2>&1
say "EXIT ledger.round=$(rget)"
