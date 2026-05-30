#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

echo "Research run context"
echo
echo "Required reading:"
printf '%s\n' \
  "AGENTS.md" \
  "README.md" \
  "research/README.md" \
  "research/memory.md" \
  "research/sources.md" \
  "research/questions.md" \
  "research/findings.md" \
  "research/decisions.md"

echo
echo "Strategy memory:"
find strategy -maxdepth 3 -type f -name '*.md' | sort

echo
echo "Run logs:"
find research/runs -maxdepth 1 -type f -name '*.md' | sort

echo
echo "Recommended next focus:"
sed -n '/## 高优先级问题/,/## 中优先级问题/p' research/questions.md
