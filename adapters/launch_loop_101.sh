#!/bin/bash
# 在 101 上点火：headless Claude Code 当编排者，nohup 常驻，断链不影响。
# watchdog：记录每次退出码；异常退出（编排者进程曾两次被无痕硬杀）自动
# 续跑，最多 5 次；ledger.round 跑满目标轮数即正常收工。
#   bash launch_loop_101.sh [rounds] [batch] [audit_frac] [eval_every] [eval_baseline]
# 4 点曲线测试：bash launch_loop_101.sh 12 30 0.2 4 true
#   -> rounds=12 eval_every=4 eval_baseline=true，出 r=0,4,8,12 四个点
set -euo pipefail
VS=/root/data/veriskill
cd "$VS"
source env.sh

ROUNDS="${1:-3}"; BATCH="${2:-30}"; FRAC="${3:-0.2}"
EVAL_EVERY="${4:-4}"; EVAL_BASELINE="${5:-false}"
# audit_frac=0.2：抽样审计，贴近真实使用场景（不靠全覆盖 Oracle 喂 D）
# eval_every=4：rounds<4 的短 smoke 不触发、零成本；12 轮 +baseline 出 4 点曲线
PROMPT="/veriskill-loop rounds=$ROUNDS batch=$BATCH audit_frac=$FRAC train_ratio=0.8 replay_K=3 eval_every=$EVAL_EVERY eval_baseline=$EVAL_BASELINE"

LOG="loop_$(date +%m%d_%H%M).log"
VERISKILL_LOOP_LOG="$VS/$LOG"   # 让 eval_test.sh 等子进程能把后台进展写进本 loop 日志
export PROMPT ROUNDS VS VERISKILL_LOOP_LOG
nohup bash -c '
for i in 1 2 3 4 5; do
  echo "[watchdog] attempt $i start $(date "+%F %T")"
  claude -p "$PROMPT" \
    --model deepseek-v4-flash \
    --dangerously-skip-permissions \
    --verbose
  rc=$?
  echo "[watchdog] attempt $i: claude exited rc=$rc at $(date "+%F %T")"
  R=$(python3 -c "import json;print(json.load(open(\"$VS/ledger.json\")).get(\"round\",0))" 2>/dev/null || echo 0)
  echo "[watchdog] ledger.round=$R / target=$ROUNDS"
  if [ "$R" -ge "$ROUNDS" ]; then echo "[watchdog] 跑满轮数，收工"; break; fi
  if [ "$rc" -eq 0 ]; then echo "[watchdog] 正常退出但未跑满（可能主动停止），不再重启"; break; fi
  sleep 15
done' > "$LOG" 2>&1 &
echo "PID=$! LOG=$VS/$LOG"
