#!/usr/bin/env bash
# 兼容入口：所有轮次统一交给 canonical launcher，避免旧脚本绕过同样本审计。
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROUNDS="${1:-3}"
BATCH="${2:-30}"
AUDIT_FRAC="${3:-0.2}"
EVAL_EVERY="${4:-4}"
EVAL_BASELINE="${5:-false}"
exec bash "$HERE/adapters/launch_loop_101.sh" \
  "$ROUNDS" "$BATCH" "$AUDIT_FRAC" "$EVAL_EVERY" "$EVAL_BASELINE"
# VERISKILL_CALIBRATION_V5_163DCD8
