#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

SEED_CONFIG=${SEED_CONFIG:-config/eval-seeds.json}

python3 -m balatro_agent seed-cohorts --seed-config "$SEED_CONFIG"
