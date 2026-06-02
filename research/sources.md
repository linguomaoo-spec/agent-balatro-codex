# 研究来源

## 需要监控的一手来源（Primary Sources To Monitor）

- 仓库代码：`balatro_agent/`
- 仓库测试：`tests/`
- 仓库示例：`examples/`
- 项目说明：`README.md`
- 由 `python3 -m balatro_agent step --log runs/decisions.jsonl` 等命令生成的本地决策日志
- 由 `python3 -m balatro_agent record --output runs/human/*.jsonl` 或 `scripts/record-human-start.sh` 生成的人工游玩状态日志
- 由 `python3 -m balatro_agent ... eval --log-dir runs/eval` 等命令生成的本地评估日志
- BalatroBot 上游仓库：https://github.com/coder/balatrobot
- BalatroBot 官方 API 参考：https://coder.github.io/balatrobot/api/（用于核对状态、schema、方法和 `won` 字段）
- BalatroLLM 上游仓库：https://github.com/coder/balatrollm
- 可从本地或上游 BalatroBot 项目获得的 BalatroBot OpenRPC schema

## 需要监控的二手来源（Secondary Sources To Monitor）

- 用户提供论文附件：`1-continual_learning_survey.pdf`（Never Stop Learning: A Survey of Continual Learning and Self-Iteration in Large Language Models）。该文标注由 Deli AutoResearch 框架部分生成，适合作为方法论启发；关键主张仍需用本项目日志和测试验证。本地附件路径包括 `/tmp/codex-remote-attachments/019e7883-8f9a-7530-b3c5-999e20916773/975BD3AC-8708-4588-8FA1-FF4569F47F3C/1-continual_learning_survey.pdf` 和 `/tmp/codex-remote-attachments/019e78a8-24a7-7270-b621-0055e70bedeb/DEC0DFF9-08B8-4D5B-9EB7-F6D00172F5CC/1-continual_learning_survey.pdf`。
- 仅作为启发式线索使用的 Balatro 策略讨论。
- 相关 Balatro 自动化项目的公开 issue 或 discussion。
- 通用游戏 AI、搜索、rollout 或启发式评估资料。

## 排除来源（Excluded Sources）

- 无法通过游戏证据检查的无来源 tier list 或策略主张。
- 不链接一手证据的生成式摘要。
- 与本地 schema 或实际观察行为冲突的过期 BalatroBot 端点说法。

## 来源质量规则（Source Quality Rules）

- 优先使用直接观察到的仓库行为、测试、日志和官方上游文档。
- 为每条发现记录精确文件路径、命令输出、URL 或日志路径。
- 在一手证据验证前，只把二手来源当作线索。
- 对网络来源，如果主张可能变化，在发现或运行日志中记录访问日期。
- 按证据质量分配置信度：`High（高）`、`Medium（中）` 或 `Low（低）`。
