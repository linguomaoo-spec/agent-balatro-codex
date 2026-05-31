#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

BASELINE=${BASELINE:?Set BASELINE to a summarize-eval JSON file}
CANDIDATE=${CANDIDATE:?Set CANDIDATE to a summarize-eval JSON file}
COHORT=${COHORT:-dev}

python3 -m balatro_agent promotion-gate \
  --baseline "$BASELINE" \
  --candidate "$CANDIDATE" \
  --cohort "$COHORT"
