#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

BASE_URL=${BALATROBOT_URL:-http://127.0.0.1:12346}
TIMEOUT=${BALATROBOT_TIMEOUT:-2}

echo "Running unit tests..."
python3 -m unittest discover -s tests

echo "Checking BalatroBot at $BASE_URL ..."
OUT_FILE=$(mktemp)
ERR_FILE=$(mktemp)
trap 'rm -f "$OUT_FILE" "$ERR_FILE"' EXIT HUP INT TERM

if python3 -m balatro_agent --base-url "$BASE_URL" --timeout "$TIMEOUT" doctor >"$OUT_FILE" 2>"$ERR_FILE"; then
  cat "$OUT_FILE"
  echo "BalatroBot check completed."
else
  echo "BalatroBot check failed. Start BalatroBot or set BALATROBOT_URL." >&2
  if [ -s "$ERR_FILE" ]; then
    echo "Details:" >&2
    tail -5 "$ERR_FILE" >&2
  fi
  exit 1
fi
