#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

TASK=${1:-}
OUTPUT=${2:-}

if [ -z "$TASK" ]; then
  echo "Usage: sh scripts/subagent-task.sh \"task description\" [output.md]" >&2
  exit 2
fi

if [ -z "$OUTPUT" ]; then
  mkdir -p runs/subagents
  OUTPUT="runs/subagents/$(date +%Y%m%d-%H%M%S).md"
else
  mkdir -p "$(dirname "$OUTPUT")"
fi

{
  echo "# 子 agent 任务包"
  echo
  echo "## 任务"
  echo
  echo "$TASK"
  echo
  echo "## 约束"
  echo
  echo "- 只处理本任务，不重写项目架构。"
  echo "- 优先使用一手证据：策略记忆、研究文件、日志、代码和测试。"
  echo "- 输出必须包含：观察、证据、建议策略记忆更新、仍需验证。"
  echo "- 没有证据的判断只能标注为工作假设。"
  echo
  echo "## 必读入口"
  echo
  printf '%s\n' \
    "- README.md" \
    "- strategy/index.md" \
    "- research/memory.md" \
    "- research/questions.md" \
    "- research/findings.md" \
    "- research/decisions.md"
  echo
  echo "## 策略文件索引"
  echo
  find strategy -maxdepth 3 -type f -name '*.md' | sort | sed 's/^/- /'
  echo
  echo "## 最近研究运行"
  echo
  find research/runs -maxdepth 1 -type f -name '*.md' | sort | tail -5 | sed 's/^/- /'
} > "$OUTPUT"

echo "$OUTPUT"
