#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

BASE_URL=${BALATROBOT_URL:-http://127.0.0.1:12346}
TIMEOUT=${BALATROBOT_TIMEOUT:-10}
GENOME=${GENOME:-}
LOG_PATH=${LOG_PATH:-runs/decisions.jsonl}

if [ -n "$GENOME" ]; then
  python3 -m balatro_agent --base-url "$BASE_URL" --timeout "$TIMEOUT" --genome "$GENOME" step \
    --log "$LOG_PATH"
else
  python3 -m balatro_agent --base-url "$BASE_URL" --timeout "$TIMEOUT" step \
    --log "$LOG_PATH"
fi
