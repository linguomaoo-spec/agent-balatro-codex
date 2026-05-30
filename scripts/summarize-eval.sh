#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

LOG_DIR=${LOG_DIR:-runs/eval}

python3 -m balatro_agent summarize-eval --log-dir "$LOG_DIR"
