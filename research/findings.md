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

- 日期（Date）：2026-05-30
- 发现（Finding）：本地已建立初始 seed cohort 和 replay 案例抽取入口，但真实 BalatroBot 当前不可用，尚未完成真实固定 seed 小批量验证。
- 证据（Evidence）：`config/eval-seeds.json` 定义 `dev`、`regression`、`heldout`；`scripts/eval.sh` 支持 `COHORT`/`SEED_CONFIG`；`balatro_agent.analysis.extract_replay_cases` 抽取 `error`、`terminal_win`、`terminal_loss`、`terminal_unknown`；`scripts/doctor.sh` 运行时 BalatroBot 检查在 `http://127.0.0.1:12346` 超时。
- 来源（Source）：`config/eval-seeds.json`、`scripts/eval.sh`、`balatro_agent/analysis.py`、`scripts/build-replay.sh`、本次 `sh scripts/doctor.sh` 输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：离线持续学习基础设施可用；下一步瓶颈是启动真实 BalatroBot 并产生评估日志。
- 关联问题（Related question）：当前评估循环在固定 seed 上是否能产生可复现结果？真实 BalatroBot 结束局是否稳定返回 `won` 字段？

- 日期（Date）：2026-05-30
- 发现（Finding）：当前代码已具备持续学习改造的基础入口，但尚未实现策略晋升门槛、遗忘/迁移指标、replay top-k 检索或按 replay 自动生成子 agent 上下文。
- 证据（Evidence）：`balatro_agent.analysis.summarize_jsonl_logs` 汇总 run 数、胜率、错误数、最高 ante 等指标；`extract_replay_cases` 只抽取错误和终局案例；`config/eval-seeds.json` 只定义 `dev`、`regression`、`heldout` 初始 cohort；`scripts/subagent-task.sh` 只注入策略和研究入口，没有注入 replay 案例。
- 来源（Source）：`balatro_agent/analysis.py`、`config/eval-seeds.json`、`scripts/subagent-task.sh`、`strategy/runs/README.md`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：下一轮改造应优先补“候选策略如何被验证并晋升”的质量门禁，而不是直接扩大 hand/shop 规则复杂度。
- 关联问题（Related question）：策略晋升门槛应使用哪些阈值？replay 经验库应保存哪些最小字段？

### 2026-05-31

- 日期（Date）：2026-05-31
- 发现（Finding）：本地已实现持续学习反馈闭环的只读基础设施：策略晋升比较、replay 决策案例扩展、replay top-k 查询和 replay-aware 子 agent 任务包。
- 证据（Evidence）：`balatro_agent.analysis.compare_eval_summaries` 输出 `promote`、`failed_checks`、`deltas` 和 `lost_wins`；`extract_replay_cases` 增加 `decision` 案例和动作参数/候选数/agent 字段；`replay-query` CLI 可按阶段和类型查询 replay；`scripts/subagent-task.sh` 可通过 `REPLAY`、`PHASE`、`CASE_TYPE` 和 `REPLAY_LIMIT` 注入相关案例。
- 来源（Source）：`balatro_agent/analysis.py`、`balatro_agent/cli.py`、`scripts/promotion-gate.sh`、`scripts/subagent-task.sh`、`tests/test_analysis.py`、`strategy/runs/README.md`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：后续 hand/shop 策略候选可以先用固定 seed 摘要和 replay 案例进行门禁检查，再决定是否晋升为稳定策略或 genome 权重。
- 关联问题（Related question）：策略晋升门槛应使用哪些阈值？replay 经验库应如何按阶段、ante、deck、stake、小丑牌标签、失败类型和相似动作做 top-k 检索？

- 日期（Date）：2026-05-31
- 发现（Finding）：真实 Balatro + Lovely + BalatroBot 已能在本机启动，并通过 `http://127.0.0.1:12346` 响应健康检查；本地安装的 BalatroBot mod 版本是 `1.4.0`。
- 证据（Evidence）：`/Users/suriness/Library/Application Support/Balatro/Mods/balatrobot/balatrobot.json` 记录 `"version": "1.4.0"`；用 `run_lovely_macos.sh` 启动后，`lsof -nP -iTCP:12346 -sTCP:LISTEN` 显示 `love` 监听 `127.0.0.1:12346`；`python3 -m balatro_agent --timeout 3 doctor` 返回 `{"status": "ok"}`。
- 来源（Source）：本地 Balatro 安装目录、BalatroBot mod 文件、2026-05-31 本地命令输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：真实固定 seed 评估不再被 BalatroBot 启动问题阻塞，可以继续收集 live 决策日志。
- 关联问题（Related question）：当前使用的本地 BalatroBot schema 版本是什么，是否匹配仓库假设？当前评估循环在固定 seed 上是否能产生可复现结果？

- 日期（Date）：2026-05-31
- 发现（Finding）：真实 BalatroBot loss 终局会返回 `phase: "GAME_OVER"` 和 `won: false`；但当前 JSONL 决策日志没有记录 `Runner.run` 结束时读取到的终局状态，导致 `summarize-eval` 把这局标记为 `incomplete`，`build-replay` 抽不到终局失败案例。
- 证据（Evidence）：`SEEDS=AGENT1 MAX_STEPS=30 LOG_DIR=runs/eval/live-20260531-134011-stage1 sh scripts/eval.sh` 返回 `status: "game_over_loss"`、`steps: 5`、终局 state 包含 `phase: "GAME_OVER"`、`won: false`、`score: 224`；随后直接查询 `BalatroBotClient().gamestate()` 得到同样的 `GAME_OVER`/`won: false` 摘要。可是 `python3 -m balatro_agent summarize-eval --log-dir runs/eval/live-20260531-134011-stage1` 对 `AGENT1.jsonl` 输出 `status: "incomplete"`、`failure_phase: "SELECTING_HAND"`，`build-replay` 输出 `case_count: 0`；该 JSONL 只有 5 条动作前状态记录，最后一条仍是 `SELECTING_HAND`。
- 来源（Source）：`runs/eval/live-20260531-134011-stage1/AGENT1.jsonl`、本次 `eval`/`summarize-eval`/`build-replay`/`gamestate` 命令输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：当前 live runner 的返回值可用于判断本次 run 胜负，但只读日志闭环对终局统计和 replay 抽取不可靠；下一步应补终局日志记录或让汇总入口读取 eval 返回摘要。
- 关联问题（Related question）：真实 BalatroBot 结束局是否稳定返回 `won` 字段？当前 baseline agent 的决策日志中有哪些常见失败模式？replay 经验库应保存哪些最小字段？

### 2026-06-01

- 日期（Date）：2026-06-01
- 发现（Finding）：默认 genome 在真实 BalatroBot 的 `dev` cohort 三个固定 seed 上均未通关；本次最佳游戏内分数为 AGENT1 的 13224，最高到 ante 5 / round 15。
- 证据（Evidence）：`COHORT=dev MAX_STEPS=500 LOG_DIR=runs/eval/live-20260601-clear-attempt-dev sh scripts/eval.sh` 返回 3 个 `game_over_loss`；`summarize-eval` 输出 `run_count: 3`、`win_count: 0`、`loss_count: 3`、`max_ante: 5`，其中 AGENT1 `final_score: 13224` / `final_required_score: 22000`，AGENT2 `final_score: 2908` / `final_required_score: 4000`，AGENT3 `final_score: 240` / `final_required_score: 300`。
- 来源（Source）：`runs/eval/live-20260601-clear-attempt-dev/AGENT1.jsonl`、`runs/eval/live-20260601-clear-attempt-dev/AGENT2.jsonl`、`runs/eval/live-20260601-clear-attempt-dev/AGENT3.jsonl`、本次 `eval` 和 `summarize-eval` 命令输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：当前默认 agent 尚不能稳定通过 white stake 的 dev seed；AGENT1 的 ante 5 失败局是下一轮策略分析的最高价值案例。
- 关联问题（Related question）：当前 baseline agent 的决策日志中有哪些常见失败模式？提高顺子/同花优先级是否能提升真实 run 的中后期得分？
