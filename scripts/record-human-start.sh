#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

BASE_URL=${BALATROBOT_URL:-http://127.0.0.1:12346}
TIMEOUT=${BALATROBOT_TIMEOUT:-10}
INTERVAL=${INTERVAL:-1}
OUTPUT=${OUTPUT:-runs/human/live-$(date +%Y%m%d-%H%M%S).jsonl}
PID_FILE=${PID_FILE:-runs/human/recorder.pid}
STDOUT_LOG=${STDOUT_LOG:-${OUTPUT%.jsonl}.out}
STDERR_LOG=${STDERR_LOG:-${OUTPUT%.jsonl}.err}

mkdir -p "$(dirname -- "$OUTPUT")" "$(dirname -- "$PID_FILE")"

if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null || true)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Recorder already running with PID $OLD_PID."
    exit 1
  fi
  rm -f "$PID_FILE"
fi

set -- python3 -m balatro_agent --base-url "$BASE_URL" --timeout "$TIMEOUT" record \
  --output "$OUTPUT" \
  --interval "$INTERVAL"

if [ -n "${MAX_POLLS:-}" ]; then
  set -- "$@" --max-polls "$MAX_POLLS"
fi
if [ -n "${MAX_SNAPSHOTS:-}" ]; then
  set -- "$@" --max-snapshots "$MAX_SNAPSHOTS"
fi
if [ "${SUMMARY_ONLY:-0}" = "1" ]; then
  set -- "$@" --summary-only
fi
if [ "${RECORD_UNCHANGED:-0}" = "1" ]; then
  set -- "$@" --record-unchanged
fi
if [ "${NO_STOP_ON_GAME_OVER:-0}" = "1" ]; then
  set -- "$@" --no-stop-on-game-over
fi

nohup "$@" >"$STDOUT_LOG" 2>"$STDERR_LOG" &
PID=$!
echo "$PID" >"$PID_FILE"

echo "Recorder started with PID $PID."
echo "JSONL: $OUTPUT"
echo "stdout: $STDOUT_LOG"
echo "stderr: $STDERR_LOG"
echo "Stop with: PID_FILE=$PID_FILE sh scripts/record-human-stop.sh"
