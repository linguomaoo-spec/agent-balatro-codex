#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

PID_FILE=${PID_FILE:-runs/human/recorder.pid}
STOP_TIMEOUT=${STOP_TIMEOUT:-5}

if [ ! -f "$PID_FILE" ]; then
  echo "Recorder PID file not found: $PID_FILE" >&2
  exit 1
fi

PID=$(cat "$PID_FILE")
if [ -z "$PID" ] || ! kill -0 "$PID" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "Recorder was not running."
  exit 0
fi

kill -INT "$PID" 2>/dev/null || true

elapsed=0
while kill -0 "$PID" 2>/dev/null && [ "$elapsed" -lt "$STOP_TIMEOUT" ]; do
  sleep 1
  elapsed=$((elapsed + 1))
done

if kill -0 "$PID" 2>/dev/null; then
  kill -TERM "$PID" 2>/dev/null || true
  echo "Recorder did not stop after ${STOP_TIMEOUT}s; sent TERM."
else
  echo "Recorder stopped."
fi

rm -f "$PID_FILE"
