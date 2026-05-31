#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

BASE_URL=${BALATROBOT_URL:-http://127.0.0.1:12346}
TIMEOUT=${BALATROBOT_TIMEOUT:-10}
GENOME=${GENOME:-}
DECK=${DECK:-RED}
STAKE=${STAKE:-WHITE}
SEEDS="${SEEDS:-}"
SEED_CONFIG=${SEED_CONFIG:-config/eval-seeds.json}
COHORT=${COHORT:-dev}
MAX_STEPS=${MAX_STEPS:-500}
LOG_DIR=${LOG_DIR:-runs/eval}

set -f

SEED_ARGS="--seed-config $SEED_CONFIG --cohort $COHORT"
if [ -n "$SEEDS" ]; then
  SEED_ARGS="--seeds $SEEDS"
fi

if [ -n "$GENOME" ]; then
  python3 -m balatro_agent --base-url "$BASE_URL" --timeout "$TIMEOUT" --genome "$GENOME" eval \
    --deck "$DECK" \
    --stake "$STAKE" \
    $SEED_ARGS \
    --max-steps "$MAX_STEPS" \
    --log-dir "$LOG_DIR"
else
  python3 -m balatro_agent --base-url "$BASE_URL" --timeout "$TIMEOUT" eval \
    --deck "$DECK" \
    --stake "$STAKE" \
    $SEED_ARGS \
    --max-steps "$MAX_STEPS" \
    --log-dir "$LOG_DIR"
fi
