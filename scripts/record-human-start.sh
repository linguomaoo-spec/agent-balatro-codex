#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

shell_quote() {
  printf "'%s'" "$(printf "%s" "$1" | sed "s/'/'\\\\''/g")"
}

BASE_URL=${BALATROBOT_URL:-http://127.0.0.1:12346}
TIMEOUT=${BALATROBOT_TIMEOUT:-10}
INTERVAL=${INTERVAL:-1}
MODE=${MODE:-actions}
if [ "$MODE" = "snapshots" ]; then
  OUTPUT=${OUTPUT:-runs/human/live-$(date +%Y%m%d-%H%M%S).jsonl}
else
  OUTPUT=${OUTPUT:-runs/human/live-$(date +%Y%m%d-%H%M%S).json}
fi
PID_FILE=${PID_FILE:-runs/human/recorder.pid}
STDOUT_LOG=${STDOUT_LOG:-${OUTPUT%.*}.out}
STDERR_LOG=${STDERR_LOG:-${OUTPUT%.*}.err}

mkdir -p "$(dirname -- "$OUTPUT")" "$(dirname -- "$PID_FILE")"

if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null || true)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Recorder already running with PID $OLD_PID."
    exit 1
  fi
  rm -f "$PID_FILE"
fi

if [ "$MODE" = "snapshots" ]; then
  set -- python3 -m balatro_agent --base-url "$BASE_URL" --timeout "$TIMEOUT" record \
    --output "$OUTPUT" \
    --interval "$INTERVAL"
else
  set -- python3 -m balatro_agent --base-url "$BASE_URL" --timeout "$TIMEOUT" record-actions \
    --output "$OUTPUT" \
    --interval "$INTERVAL"
fi

if [ -n "${MAX_POLLS:-}" ]; then
  set -- "$@" --max-polls "$MAX_POLLS"
fi
if [ "$MODE" = "snapshots" ] && [ -n "${MAX_SNAPSHOTS:-}" ]; then
  set -- "$@" --max-snapshots "$MAX_SNAPSHOTS"
fi
if [ "$MODE" = "snapshots" ] && [ "${SUMMARY_ONLY:-0}" = "1" ]; then
  set -- "$@" --summary-only
fi
if [ "$MODE" = "snapshots" ] && [ "${RECORD_UNCHANGED:-0}" = "1" ]; then
  set -- "$@" --record-unchanged
fi
if [ "${NO_STOP_ON_GAME_OVER:-0}" = "1" ]; then
  set -- "$@" --no-stop-on-game-over
fi

if command -v tmux >/dev/null 2>&1 && [ "${USE_TMUX:-1}" = "1" ]; then
  TMUX_SESSION=${TMUX_SESSION:-balatro-recorder}
  if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    echo "Recorder tmux session already exists: $TMUX_SESSION" >&2
    exit 1
  fi

  COMMAND=""
  for arg do
    COMMAND="$COMMAND $(shell_quote "$arg")"
  done
  tmux new-session -d -s "$TMUX_SESSION" \
    "cd $(shell_quote "$ROOT_DIR") && echo \$\$ > $(shell_quote "$PID_FILE") && exec$COMMAND >$(shell_quote "$STDOUT_LOG") 2>$(shell_quote "$STDERR_LOG")"

  sleep 0.2
  PID=$(cat "$PID_FILE" 2>/dev/null || true)
else
  nohup "$@" >"$STDOUT_LOG" 2>"$STDERR_LOG" &
  PID=$!
  echo "$PID" >"$PID_FILE"
fi

echo "Recorder started with PID $PID."
if [ -n "${TMUX_SESSION:-}" ]; then
  echo "tmux: $TMUX_SESSION"
fi
echo "JSON: $OUTPUT"
echo "stdout: $STDOUT_LOG"
echo "stderr: $STDERR_LOG"
echo "Stop with: PID_FILE=$PID_FILE sh scripts/record-human-stop.sh"
