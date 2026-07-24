#!/bin/bash
# 在 101 上点火：headless Claude Code 当编排者，nohup 常驻，断链不影响。
# watchdog：只认 ledger.round 跑满目标轮数才收工；否则自动续跑（含无痕
# 硬杀、提前 rc=0 收尾都续），最多 8 次。
#   bash launch_loop_101.sh [rounds] [batch] [audit_frac]
set -euo pipefail
VS=/root/data/frontiersci_run/veriskill
cd "$VS"
source env.sh

ROUNDS="${1:-10}"; BATCH="${2:-16}"; FRAC="${3:-0.25}"
MODEL="${VERISKILL_MODEL:-deepseek-v4-flash-260601}"
PROMPT="/veriskill-loop rounds=$ROUNDS batch=$BATCH audit_frac=$FRAC train_ratio=0.8 replay_K=999"

LOG="loop_$(date +%m%d_%H%M).log"
export PROMPT ROUNDS VS MODEL
nohup bash -c '
for i in 1 2 3 4 5 6 7 8; do
  echo "[watchdog] attempt $i start $(date "+%F %T")"
  claude -p "$PROMPT" \
    --model "$MODEL" \
    --dangerously-skip-permissions \
    --verbose
  rc=$?
  echo "[watchdog] attempt $i: claude exited rc=$rc at $(date "+%F %T")"
  R=$(python3 -c "import json;print(json.load(open(\"$VS/ledger.json\")).get(\"round\",0))" 2>/dev/null || echo 0)
  echo "[watchdog] ledger.round=$R / target=$ROUNDS"
  if [ "$R" -ge "$ROUNDS" ]; then echo "[watchdog] 跑满轮数，收工"; break; fi
  sleep 15
done' > "$LOG" 2>&1 &
echo "PID=$! LOG=$VS/$LOG"
