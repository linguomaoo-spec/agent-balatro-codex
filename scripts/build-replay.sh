#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

LOG_DIR=${LOG_DIR:-runs/eval}
OUTPUT=${OUTPUT:-strategy/runs/replay.jsonl}
LIMIT=${LIMIT:-100}

python3 -m balatro_agent build-replay --log-dir "$LOG_DIR" --output "$OUTPUT" --limit "$LIMIT"
