#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

BASE_URL=${BALATROBOT_URL:-http://127.0.0.1:12346}
TIMEOUT=${BALATROBOT_TIMEOUT:-10}
DECK=${DECK:-RED}
STAKE=${STAKE:-WHITE}
if [ -n "${SEED:-}" ]; then
  echo "实际启动禁止预设 seed；请取消设置 SEED。" >&2
  exit 2
fi

python3 -m balatro_agent --base-url "$BASE_URL" --timeout "$TIMEOUT" start \
  --deck "$DECK" \
  --stake "$STAKE"
