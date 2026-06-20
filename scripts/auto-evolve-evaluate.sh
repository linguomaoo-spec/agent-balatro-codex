#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

COHORT=${1:?Usage: auto-evolve-evaluate.sh COHORT LOG_DIR}
LOG_DIR=${2:?Usage: auto-evolve-evaluate.sh COHORT LOG_DIR}

python3 -m balatro_agent \
  --base-url "${BALATROBOT_URL:-http://127.0.0.1:12346}" \
  --timeout "${BALATROBOT_TIMEOUT:-10}" \
  eval --deck "${DECK:-RED}" --stake "${STAKE:-WHITE}" \
  --seed-config "${SEED_CONFIG:-config/eval-seeds.json}" \
  --cohort "$COHORT" --max-steps "${MAX_STEPS:-500}" --log-dir "$LOG_DIR"
