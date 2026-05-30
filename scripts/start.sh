#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

BASE_URL=${BALATROBOT_URL:-http://127.0.0.1:12346}
TIMEOUT=${BALATROBOT_TIMEOUT:-10}
DECK=${DECK:-RED}
STAKE=${STAKE:-WHITE}
SEED=${SEED:-}

if [ -n "$SEED" ]; then
  python3 -m balatro_agent --base-url "$BASE_URL" --timeout "$TIMEOUT" start \
    --deck "$DECK" \
    --stake "$STAKE" \
    --seed "$SEED"
else
  python3 -m balatro_agent --base-url "$BASE_URL" --timeout "$TIMEOUT" start \
    --deck "$DECK" \
    --stake "$STAKE"
fi
