#!/bin/zsh
# Fail-closed launcher for the Live Final. Run from anywhere in this checkout:
#   ./scripts/start_final.sh --check   # safe preflight; GET /v1/me only
#   ./scripts/start_final.sh           # preflight, then start the autonomous final runner
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"
KIT="$ROOT/vendor/negotiation-arena-kit/starter-kit"

case "${1:-}" in
  ""|--check) ;;
  -h|--help)
    print "Usage: ./scripts/start_final.sh [--check]"
    print "  --check  Verify launch readiness without starting the final runner."
    print "  no args  Verify readiness, then start the autonomous final runner."
    exit 0
    ;;
  *)
    print -u2 "Usage: ./scripts/start_final.sh [--check]"
    exit 2
    ;;
esac

if ! command -v caffeinate >/dev/null 2>&1; then
  print -u2 "ERROR: caffeinate is unavailable; use the prepared Mac final machine."
  exit 1
fi
RUNNER_PY="$KIT/.venv/bin/python"
if [[ ! -x "$RUNNER_PY" ]]; then
  print -u2 "ERROR: locked project environment is missing. Set it up before final day."
  exit 1
fi

export PYTHONPATH="$ROOT:$ROOT/scripts:$KIT${PYTHONPATH:+:$PYTHONPATH}"

print "Checking source freeze, environment, data, budget, model configuration, and runner state..."
if ! "$RUNNER_PY" scripts/final_preflight.py --online; then
  print -u2 "ERROR: preflight failed; the final runner was not started."
  exit 1
fi

if [[ "${1:-}" == "--check" ]]; then
  print "Preflight only: no negotiation session or model call was started."
  exit 0
fi

mkdir -p artifacts
LAUNCH_LOCK="artifacts/final_runner.launch.lock"
if ! mkdir "$LAUNCH_LOCK" 2>/dev/null; then
  print -u2 "ERROR: another launcher may be starting the final; do not click start twice."
  exit 1
fi
print -r -- "$$" > "$LAUNCH_LOCK/pid"
trap 'rm -f "$LAUNCH_LOCK/pid"; rmdir "$LAUNCH_LOCK" 2>/dev/null || true' EXIT INT TERM HUP

PIDFILE="artifacts/final_runner.pid"
if [[ -f "$PIDFILE" ]]; then
  OLD_PID="$(<"$PIDFILE")"
  if [[ "$OLD_PID" == <-> ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    print -u2 "ERROR: PID $OLD_PID from the final runner lock is still active. Do not start a second copy."
    exit 1
  fi
  rm -f "$PIDFILE"
fi

LOG="artifacts/final_live_$(date -u +%Y%m%dT%H%M%SZ)_$$.log"
print "Starting frozen runner. Log: $LOG"
nohup caffeinate -dimsu "$RUNNER_PY" scripts/final_runner.py --final --limit-usd 2.0 \
  >> "$LOG" 2>&1 < /dev/null &
PID=$!
print -r -- "$PID" > "$PIDFILE"
READY=0
for _ in {1..15}; do
  if ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$PIDFILE"
    print -u2 "ERROR: runner exited during startup. Last log lines:"
    tail -n 40 "$LOG" >&2 || true
    exit 1
  fi
  if grep -Fq "Final runner ready: polling final cases" "$LOG"; then
    READY=1
    break
  fi
  sleep 1
done

if [[ "$READY" != 1 ]]; then
  print -u2 "ERROR: process $PID is alive, but startup was not confirmed. Inspect the log and do not launch a second copy."
  print -u2 "Log: $LOG"
  exit 1
fi

print "Runner is alive and polling for wave 1 (PID $PID). Leave this Mac plugged in."
print "Monitor: python3 scripts/progress.py"
print "Log: tail -f $LOG"
