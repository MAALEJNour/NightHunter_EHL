#!/bin/zsh
# Start the NightHunter agent for the Live Final and leave it running (no human in the loop after 12:00).
# Keeps the Mac awake (caffeinate) and logs everything to artifacts/final_live_<time>.log.
#   ./scripts/start_final.sh
cd "$(dirname "$0")/.."
LOG="artifacts/final_live_$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p artifacts
echo "NightHunter Live Final runner - log: $LOG"
uv run --project vendor/negotiation-arena-kit/starter-kit arena me > /dev/null && echo "arena key OK"
PYTHONPATH=.:scripts caffeinate -dimsu uv run --project vendor/negotiation-arena-kit/starter-kit \
  python scripts/final_runner.py --final --limit-usd 2.0 >> "$LOG" 2>&1 &
echo "runner PID $! (keep the laptop on power; do not close this machine)"
