# 研究发现

用这个文件记录有证据支撑的观察。添加新发现前，先搜索已有条目，避免重复。

## 发现（Findings）

### 2026-05-30

- 日期（Date）：2026-05-30
- 发现（Finding）：当前仓库是一个 Python Balatro agent 项目，包含一个小型包、示例、测试和 README 驱动的命令。
- 证据（Evidence）：仓库检查显示存在 `balatro_agent/`、`examples/`、`tests/`、`pyproject.toml` 和 `README.md`。
- 来源（Source）：本地仓库文件列表和 `README.md`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：研究工作流应支持策略、评估、集成和决策日志分析，而不是替换应用代码。
- 关联问题（Related question）：自动运行应该跟踪哪些基线指标？

- 日期（Date）：2026-05-30
- 发现（Finding）：用户提供的持续学习综述把持续学习和自我迭代统一为三轴框架：学习什么、如何学习、何时更新；并强调 replay、外部验证、回归评估和稳定性-可塑性权衡。
- 证据（Evidence）：`1-continual_learning_survey.pdf` 第 1.2、1.3、3.6、4.7、4.8、6.2、6.3、6.5、7.6 和第 8 节分别讨论持续学习/自我改进/在线适应定义、三轴 taxonomy、方法选择、收敛与崩溃条件、prompt-level replay、评估指标、遗忘指标、统一评估协议和 agent 框架集成。
- 来源（Source）：用户提供论文附件 `1-continual_learning_survey.pdf`；本次运行本地路径 `/tmp/codex-remote-attachments/019e7883-8f9a-7530-b3c5-999e20916773/975BD3AC-8708-4588-8FA1-FF4569F47F3C/1-continual_learning_survey.pdf`。
- 置信度（Confidence level）：Medium（中）。该文适合作为方法论启发，但文件自述由自动研究框架部分生成，项目结论必须继续由本地日志、测试和 BalatroBot 行为验证。
- 影响（Impact）：本项目的改造应优先建立 replay 经验库、固定 seed 回归基准、held-out 验证集和策略晋升门槛，再推进更强 hand/shop 策略或 genome 进化。
- 关联问题（Related question）：自动运行应该跟踪哪些基线指标？如何比较多代 genome 权重，才能避免过拟合到很小的 seed 集？

- 日期（Date）：2026-05-30
- 发现（Finding）：当前 live runner 结束时返回 `status: "game_over"`，但进化评分只给 `status == "game_over_win"` 加胜利奖励；在现有 live run 路径中，胜利奖励可能无法触发。
- 证据（Evidence）：`balatro_agent/runner.py` 在 `GAME_OVER` 阶段返回 `{"status": "game_over", ...}`；`balatro_agent/evolution.py` 的 `EvalResult.score` 只在 `run.get("status") == "game_over_win"` 时增加 `100.0` 分。
- 来源（Source）：`balatro_agent/runner.py`；`balatro_agent/evolution.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：如果不先修正或明确胜负判定，后续 genome 进化和策略自我迭代会缺少可靠外部奖励信号。
- 关联问题（Related question）：自动运行应该跟踪哪些基线指标？当前评估循环在固定 seed 上是否能产生可复现结果？

- 日期（Date）：2026-05-30
- 发现（Finding）：BalatroBot 官方 API 参考中的 `GameState` schema 包含 `won`、`ante_num`、`round_num` 和 Area `cards` 结构，可作为本项目解析胜负、进度和区域卡牌的主要状态来源。
- 证据（Evidence）：BalatroBot API Reference 的 `GameState Schema` 示例列出 `"won": false`、`"ante_num": 1`、`"round_num": 1` 和 `"hand": { ... }`；`Area` schema 使用 `"cards": [ ... ]`；同页说明 `gamestate` 返回完整 `GameState`，`GAME_OVER` 表示游戏结束。
- 来源（Source）：https://coder.github.io/balatrobot/api/；访问日期：2026-05-30。
- 置信度（Confidence level）：Medium（中）。官方文档是一手来源，但仍需在本地实际 BalatroBot 运行中确认当前安装版本行为。
- 影响（Impact）：`Runner.run` 可以基于 `GameState.won` 输出明确胜负状态，进化评分也可以兼容旧日志中的 `state.won`；解析层应兼容官方 schema 的编号字段和 Area 结构。
- 关联问题（Related question）：当前评估循环在固定 seed 上是否能产生可复现结果？

- 日期（Date）：2026-05-30
- 发现（Finding）：本地代码已统一胜负状态契约，并新增只读评估日志汇总入口。
- 证据（Evidence）：`GameState.summary()` 现在包含 `won`、`jokers` 和 `consumables`，并兼容 `ante_num`、`round_num` 和 Area `cards`；`Runner.run` 在 `GAME_OVER` 时返回 `game_over_win`、`game_over_loss` 或 `game_over`；`EvalResult.score` 兼容 `state.won == true`；`balatro_agent.analysis.summarize_jsonl_logs` 和 `summarize-eval` CLI 输出 run 数、胜率、错误数、最高 ante、失败阶段、分数差距等指标。
- 来源（Source）：`balatro_agent/model.py`、`balatro_agent/runner.py`、`balatro_agent/evolution.py`、`balatro_agent/analysis.py`、`balatro_agent/cli.py`、`tests/test_model.py`、`tests/test_runner.py`、`tests/test_evolution.py`、`tests/test_analysis.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：后续策略改造可以先用稳定的本地指标摘要做回归检查，再决定是否把策略记忆晋升为代码或 genome 权重。
- 关联问题（Related question）：自动运行应该跟踪哪些基线指标？replay 经验库应保存哪些最小字段？
