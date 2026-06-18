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

- 日期（Date）：2026-06-01
- 发现（Finding）：四轮针对 `dev` cohort 失败日志的最小策略修正显著提高了固定 seed 进度，但仍未通关；最终候选的 eval score 为 115.12933333333334，`win_count: 0`、`loss_count: 3`、`max_ante: 5`、无错误动作或 rejected 动作。
- 证据（Evidence）：`runs/eval/live-20260601-trigger-keep-dev` 将 AGENT1 从 13224/22000 提升到 14816/22000；`runs/eval/live-20260601-last-hand-dev` 将 AGENT3 从 ante 1 的 240/300 推进到 ante 2 的 627/1600；`runs/eval/live-20260601-icecream-dev` 将 AGENT3 推进到 ante 5 的 10524/11000；`runs/eval/live-20260601-close-last-hand-dev` 将 AGENT3 推进到 ante 5 的 10875/11000。`python3 -m balatro_agent summarize-eval --log-dir runs/eval/live-20260601-close-last-hand-dev` 输出 `run_count: 3`、`win_count: 0`、`loss_count: 3`、`error_count: 0`、`rejected_count: 0`。
- 来源（Source）：上述本地 JSONL 评估日志、对应 `summarize-eval` 输出、`balatro_agent/agents.py`、`tests/test_orchestrator.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：当前改动是实证正向的，但还不能声明策略晋升完成；下一轮应优先解决 AGENT3 只差 125 分的近失误和 AGENT2 ante 3 构筑不足。
- 关联问题（Related question）：当前 baseline agent 的决策日志中有哪些常见失败模式？哪些商店决策对后续 ante 的负面影响最大？

- 日期（Date）：2026-06-01
- 发现（Finding）：AGENT3 首轮失败的一个直接原因是最后一手无小丑时把弱低两对当成可过盲牌；用最后弃牌保留高同花/顺子听牌后，AGENT3 能越过 ante 1。
- 证据（Evidence）：`runs/eval/live-20260601-clear-attempt-dev/AGENT3.jsonl` 在 ante 1 round 1 以 240/300 失败且 4 次弃牌未使用；`runs/eval/live-20260601-last-hand-dev/AGENT3.jsonl` 在同一局面 `164/300` 时执行 `discard {"cards": [3, 4, 5, 6, 7]}`，随后推进到 ante 2 round 6；新增测试 `test_selecting_hand_uses_last_discard_when_plain_two_pair_cannot_clear_blind` 覆盖该形态。
- 来源（Source）：上述本地 JSONL 日志；`tests/test_orchestrator.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：早期无小丑时需要用更接近真实基础分的估计来判断弱成型牌是否足够过盲，不能只依赖启发式牌型分。
- 关联问题（Related question）：哪些手牌选择启发式最常错过更高分方案？

- 日期（Date）：2026-06-01
- 发现（Finding）：AGENT3 ante 2 失败被商店占槽放大：购买 `Credit Card` 后错过 `Ice Cream`，而显式降低 `Credit Card`、提高 `Ice Cream` 后，AGENT3 从 ante 2 推进到 ante 5。
- 证据（Evidence）：`runs/eval/live-20260601-last-hand-dev/AGENT3.jsonl` 显示 ante 2 round 4 买入 `Credit Card`，ante 2 round 5 商店出现 `Ice Cream` 后未买入，最终 627/1600 失败；`runs/eval/live-20260601-icecream-dev/AGENT3.jsonl` 显示后续候选持有 `j_ice_cream` 推进到 ante 5，并在 round 13 达到 10524/11000；新增测试 `test_shop_skips_credit_card_when_it_would_only_fill_a_slot` 和 `test_shop_sells_credit_card_for_ice_cream_when_slots_are_full` 覆盖该策略。
- 来源（Source）：上述本地 JSONL 日志；`balatro_agent/agents.py`；`tests/test_orchestrator.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：商店阶段需要更多早期生存牌与低价值占槽牌的显式分类；这可能比继续微调出牌启发式更能提升早期稳定性。
- 关联问题（Related question）：哪些商店决策对后续 ante 的负面影响最大？哪些具体小丑牌应进入“成长型优先名单”，以及每张成长型小丑牌对应的最佳增强操作是什么？

### 2026-06-02

- 日期（Date）：2026-06-02
- 发现（Finding）：本仓库现在有显式启动/停止的人工游玩状态 recorder，可只读轮询 BalatroBot `gamestate` 并把状态变化写成 JSONL。
- 证据（Evidence）：新增 `balatro_agent/recorder.py`、`record` CLI、`scripts/record-human-start.sh`、`scripts/record-human-stop.sh` 和 `tests/test_recorder.py`；`python3 -m unittest tests.test_recorder` 通过。
- 来源（Source）：本地仓库文件 `balatro_agent/recorder.py`、`balatro_agent/cli.py`、`scripts/record-human-start.sh`、`scripts/record-human-stop.sh`、`tests/test_recorder.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：后续可以在用户人工游玩时收集一手状态变化证据，用于复盘人类操作和对比 agent 决策；该工具不记录系统键鼠或屏幕，不能直接还原每次点击。
- 关联问题（Related question）：人类游玩状态日志应如何映射成可复用的 replay 案例？

### 2026-06-06

- 日期（Date）：2026-06-06
- 发现（Finding）：当前策略在完整 `dev` cohort 仍未通关，但相比 2026-06-06 早期候选，AGENT3 从 ante 3 的 3796/4000 推进到 ante 5 的 17928/22000；AGENT1 保持 ante 6 的 25960/30000，AGENT2 仍在 ante 3 的 3130/4000。
- 证据（Evidence）：`python3 -m balatro_agent summarize-eval --log-dir runs/eval/live-20260606-dev-banner-gros` 输出 `run_count: 3`、`win_count: 0`、`loss_count: 3`、`max_ante: 6`、`error_count: 0`、`rejected_count: 0`；AGENT1 `25960/30000`，AGENT2 `3130/4000`，AGENT3 `17928/22000`。对照 `runs/eval/live-20260606-current-dev-v3/AGENT3.jsonl` 的 `3796/4000`。
- 来源（Source）：`runs/eval/live-20260606-dev-banner-gros/*.jsonl`、`runs/eval/live-20260606-current-dev-v3/AGENT3.jsonl`、本次 `summarize-eval` 输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：本轮策略对 AGENT3 明显正向，但尚未解决 dev 通关；后续优先关注 AGENT2 早期弱 Joker 构筑和 AGENT1/AGENT3 中后期倍率不足。
- 关联问题（Related question）：当前 baseline agent 的决策日志中有哪些常见失败模式？AGENT2 为什么稳定卡在 ante 3 round 9？

- 日期（Date）：2026-06-06
- 发现（Finding）：AGENT3 的 ante 3 失败主因之一是 Boss `The Psychic` 要求出 5 张牌；旧日志在该局面连续打 4 张两对导致得分保持 0，修正后第一手改为 5 张并能推进到 ante 5。
- 证据（Evidence）：`runs/eval/live-20260606-current-dev-v3/AGENT3.jsonl` 在 ante 3 round 9 多次打 4 张牌且 `score` 仍为 0；`runs/eval/live-20260606-agent3-startwait/AGENT3.jsonl` 在同一 Psychic 局面第一手打 5 张牌，并最终推进到 ante 5 的 10949/16500；相关单元测试覆盖 Psychic 必须打 5 张。
- 来源（Source）：上述本地 JSONL 日志；`balatro_agent/agents.py`；`tests/test_orchestrator.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：Boss 盲注约束必须进入手牌选择器，而不能只靠普通牌型最大化。
- 关联问题（Related question）：在 round、hand、shop、booster 阶段，所有被选中的动作是否都合法，并正确映射到 BalatroBot 端点？

- 日期（Date）：2026-06-06
- 发现（Finding）：中后期满 Joker 槽时，为 `Banner` 替换 plain `Joker` 是正向的 AGENT3 修正；但继续保护 `Supernova` 并强推 `Gros Michel` 替换 `Mad Joker` 是负向假设。
- 证据（Evidence）：`runs/eval/live-20260606-agent3-banner-gros/AGENT3.jsonl` 在 ante 4 round 10 卖出 plain `Joker` 并买入 `Banner`，随后 AGENT3 推进到 ante 5 round 15 的 17928/22000；`runs/eval/live-20260606-agent3-gros-replace/AGENT3.jsonl` 在测试强推后退化到 ante 4 round 11 的 6936/7500。相关测试保留 plain `Joker` -> `Banner`/`Gros Michel` 替换，但撤回 `Mad Joker` -> `Gros Michel` 假设。
- 来源（Source）：上述本地 JSONL 日志；`balatro_agent/agents.py`；`tests/test_orchestrator.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：后续商店替换需要考虑 Joker 的当前累计价值和构筑上下文，不能只按静态表强行替换。
- 关联问题（Related question）：哪些商店决策对后续 ante 的负面影响最大？哪些低价值占槽 Joker 应显式降权？

- 日期（Date）：2026-06-06
- 发现（Finding）：BalatroBot live eval 存在启动/菜单状态不稳定性：`start` 后过早触发 `menu` 可导致 Lua 侧 `screenwipe` nil 崩溃；等待 `start` 后 `gamestate` 离开 `MENU` 能避免本轮完整 dev eval 的即时崩溃路径。
- 证据（Evidence）：Lovely 日志 `lovely-2026.06.06-16.07.36.log` 记录 `start({seed="AGENT1"})` 后接 `menu()`，随后 `functions/button_callbacks.lua:3185: attempt to index field 'screenwipe' (a nil value)`；后续增加 start 后等待并完成 `runs/eval/live-20260606-dev-banner-gros` 全 cohort，无启动崩溃。
- 来源（Source）：`/Users/suriness/Library/Application Support/Balatro/Mods/lovely/log/lovely-2026.06.06-16.07.36.log`、`balatro_agent/evolution.py`、`tests/test_evolution.py`、`runs/eval/live-20260606-dev-banner-gros/*.jsonl`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：真实策略评估前必须确认 BalatroBot 端点稳定，并避免把启动/菜单崩溃误判为策略失败。
- 关联问题（Related question）：当前评估循环在固定 seed 上是否能产生可复现结果？

### 2026-06-06

- 日期（Date）：2026-06-06
- 发现（Finding）：当前候选策略在真实 BalatroBot 的 `dev` cohort 三个固定 seed 上仍未通关，但 AGENT1 明显推进到 ante 6，AGENT2 小幅改善，AGENT3 退回 ante 3。
- 证据（Evidence）：`COHORT=dev LOG_DIR=runs/eval/live-20260606-current-dev-v3 sh scripts/eval.sh` 完成 3 个 seed；`python3 -m balatro_agent summarize-eval --log-dir runs/eval/live-20260606-current-dev-v3` 输出 `run_count: 3`、`win_count: 0`、`loss_count: 3`、`error_count: 0`、`rejected_count: 0`、`max_ante: 6`。AGENT1 终局为 ante 6 round 17 的 25960/30000；AGENT2 为 ante 3 round 9 的 3130/4000；AGENT3 为 ante 3 round 9 的 3796/4000。
- 来源（Source）：`runs/eval/live-20260606-current-dev-v3/AGENT1.jsonl`、`runs/eval/live-20260606-current-dev-v3/AGENT2.jsonl`、`runs/eval/live-20260606-current-dev-v3/AGENT3.jsonl`、本次 `eval` 和 `summarize-eval` 命令输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：当前候选不能晋升为已通关策略；下一轮应保留 AGENT1 的正向信号，同时优先修复 AGENT3 的退化和 AGENT2 的 ante 3 构筑不足。
- 关联问题（Related question）：AGENT2 为什么稳定卡在 ante 3 round 9？AGENT3 修正 `The Psychic` 和 `PLAY_TAROT` 后能否恢复到 ante 5+？

- 日期（Date）：2026-06-06
- 发现（Finding）：AGENT3 本轮 ante 3 失败的直接策略原因是 Boss `The Psychic` 要求出 5 张牌，而旧手牌选择会打出 4 张两对并得 0 分。
- 证据（Evidence）：`runs/eval/live-20260606-current-dev-v3/AGENT3.jsonl` 在 ante 3 round 9 boss 局多次选择 4 张牌两对，最终 3796/4000 失败；同局 Lovely 日志显示正在选择 Boss `The Psychic`，其效果是必须出 5 张牌；修正 `GameState.blind_name` 解析并让 `HandAgent` 在 `The Psychic` 枚举 5 张出牌后，`runs/eval/live-20260606-psychic-agent3-v2/AGENT3.jsonl` 已记录到 `blind_name` 并推进到 ante 4。
- 来源（Source）：`runs/eval/live-20260606-current-dev-v3/AGENT3.jsonl`、`runs/eval/live-20260606-psychic-agent3-v2/AGENT3.jsonl`、本地 Balatro/Lovely 控制台日志、`balatro_agent/model.py`、`balatro_agent/agents.py`、`tests/test_model.py`、`tests/test_orchestrator.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：Boss 条件必须进入手牌选择的硬约束，不能只靠普通牌型启发式；该修正需要在稳定 live 服务上重跑 AGENT3 和完整 `dev` cohort。
- 关联问题（Related question）：哪些 Boss blind 条件还没有进入手牌、弃牌或商店决策的硬约束？

- 日期（Date）：2026-06-06
- 发现（Finding）：使用星球牌后出现的 `PLAY_TAROT` 阶段会让旧 runner 进入 fallback 循环，随后可能退回 `MENU` 并导致 live run 不可判读。
- 证据（Evidence）：`runs/eval/live-20260606-psychic-agent3-v2/AGENT3.jsonl` 在 ante 4 shop 使用 `Jupiter` 后连续记录 `PLAY_TAROT` fallback，之后进入 `MENU` fallback；新增 `tests/test_runner.py::test_run_waits_through_play_tarot_transition` 先复现旧 runner 不继续动作，随后把 `PLAY_TAROT` 加入 `TRANSIENT_PHASES` 后通过。
- 来源（Source）：`runs/eval/live-20260606-psychic-agent3-v2/AGENT3.jsonl`、`balatro_agent/runner.py`、`tests/test_runner.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：星球牌/塔罗牌使用后的阶段转换应被视为控制流可靠性问题；在没有这类 transient 处理前，策略失败和 runner 失败会混在一起。
- 关联问题（Related question）：Runner 还应把哪些 BalatroBot phase 作为 transient 处理？

- 日期（Date）：2026-06-06
- 发现（Finding）：BalatroBot live 启动状态会影响评估可靠性：Steam 未就绪或已经处于 `MENU` 但菜单 UI 未稳定时，`menu`/`start` 调用可能超时或返回 502。
- 证据（Evidence）：本次早期 live 评估中 `menu` 端点在 `phase: MENU` 时超时；启动 Steam 并重启 Balatro 后同一评估可完成；新增 `tests/test_evolution.py::test_live_run_factory_skips_menu_call_when_already_on_menu` 覆盖 `make_live_run_factory` 在已处于 `MENU` 时跳过 `menu` 调用。
- 来源（Source）：本次本地 BalatroBot `doctor`、`gamestate`、`eval` 命令输出；`balatro_agent/evolution.py`；`tests/test_evolution.py`。
- 置信度（Confidence level）：Medium（中）。现象由本机 live 集成直接观察到，但 `MENU` UI 细节来自运行时行为，仍需更多重启样本确认。
- 影响（Impact）：后续 live 评估应先确认 Steam/BalatroBot 健康，再把结果用于策略结论；runner 或 eval 工具应更明确地区分基础设施失败和游戏内失败。
- 关联问题（Related question）：当前评估循环在固定 seed 上是否能产生可复现结果？

- 日期（Date）：2026-06-06
- 发现（Finding）：降低低即时战力或纯经济 Joker 的静态评分没有带来 dev 通关；最终可判读结果为 AGENT1 25960/30000、AGENT2 3506/4000、AGENT3 17413/22000。
- 证据（Evidence）：新增测试覆盖 `Red Card` 不应在无补充包计划时压过直接得分 Joker，`Rocket` 不应压过行星牌或存钱；`python3 -m unittest discover -s tests` 通过 104 个测试。live 验证中，`runs/eval/live-20260606-2304-shop-discipline/AGENT1.jsonl` 终局为 ante 6 的 25960/30000；`runs/eval/live-20260606-2320-shop-discipline-retry/AGENT2.jsonl` 为 ante 3 的 3506/4000；`runs/eval/live-20260606-2332-shop-discipline-final-agent3/AGENT3.jsonl` 为 ante 5 的 17413/22000。
- 来源（Source）：`balatro_agent/agents.py`、`tests/test_orchestrator.py`、上述本地 JSONL 日志和 `summarize-eval` 输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：低价值占槽牌防护可以保留为局部约束，但不能视为策略晋升；当前主要瓶颈仍是 AGENT2 弱 Joker 满槽和 AGENT1/AGENT3 中后期倍率不足。
- 关联问题（Related question）：AGENT2 为什么稳定卡在 ante 3 round 9？哪些低价值占槽 Joker 应显式降权？

- 日期（Date）：2026-06-06
- 发现（Finding）：无明确目标的晚期满槽重掷不是可靠改进；在 AGENT3 上没有恢复或超过 `live-20260606-dev-banner-gros` 的 17928/22000。
- 证据（Evidence）：测试过“ante 4+ 满 Joker 槽、高现金、当前商店无收益时提高 reroll”的候选；`runs/eval/live-20260606-2320-shop-discipline-retry/AGENT3.jsonl` 和最终 `runs/eval/live-20260606-2332-shop-discipline-final-agent3/AGENT3.jsonl` 均停在 ante 5 round 15 的 17413/22000，低于 `runs/eval/live-20260606-dev-banner-gros/AGENT3.jsonl` 的 17928/22000。该候选已从代码和测试中撤回。
- 来源（Source）：上述本地 JSONL 日志、`balatro_agent/agents.py`、`tests/test_orchestrator.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：后续 reroll 策略需要以目标牌类、替换对象和资金下限为条件，不能只用现金和“无可买项”推动。
- 关联问题（Related question）：哪些商店决策对后续 ante 的负面影响最大？策略晋升门槛应使用哪些阈值？

- 日期（Date）：2026-06-06
- 发现（Finding）：本机代理环境会干扰 BalatroBot 本地请求；未设置 `NO_PROXY` 时 `doctor` 可表现为 502，而绕过代理后真实状态是端口未监听或健康正常。
- 证据（Evidence）：环境中存在 `http_proxy=http://127.0.0.1:7897`、`https_proxy=http://127.0.0.1:7897`、`all_proxy=socks5://127.0.0.1:7897`；未设置 `NO_PROXY` 的 `python3 -m balatro_agent --timeout 3 doctor` 返回 HTTP 502；`curl --noproxy '*' http://127.0.0.1:12346` 显示 connection refused；启动 BalatroBot 后用 `NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost python3 -m balatro_agent --timeout 5 doctor` 返回 `{"status": "ok"}`。
- 来源（Source）：本次本地命令输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：后续 live 评估命令应显式绕过本地代理，或在客户端实现 loopback 代理绕过，避免把代理 502 误判为 BalatroBot 崩溃。
- 关联问题（Related question）：当前评估循环在固定 seed 上是否能产生可复现结果？

- 日期（Date）：2026-06-06
- 发现（Finding）：live eval 中仍存在 Balatro/Lovely 崩溃路径；AGENT2 重跑时商店过渡触发 `attempt to index field 'shop' (a nil value)`，导致该次 eval 中断。
- 证据（Evidence）：`runs/eval/live-20260606-2304-shop-discipline/AGENT2.jsonl` 在 ante 1 shop 记录 `cash_out` 和 `next_round` 连接错误后变为 incomplete；Lovely 日志 `/Users/suriness/Library/Application Support/Balatro/Mods/lovely/log/lovely-2026.06.06-23.03.42.log` 记录 `attempt to index field 'shop' (a nil value)`；重启 BalatroBot 并用 30 秒 timeout 重跑 AGENT2/AGENT3 后 `runs/eval/live-20260606-2320-shop-discipline-retry` 无 error。
- 来源（Source）：上述本地 JSONL 日志、Lovely 日志和 `summarize-eval` 输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：策略评估报告必须标注基础设施中断；runner 仍需更明确地记录 active run 的基础设施失败，避免与游戏内失败混淆。
- 关联问题（Related question）：`Runner.run` 是否应把意外回到 `MENU` 的 active run 记录为基础设施失败？当前评估循环在固定 seed 上是否能产生可复现结果？

### 2026-06-07

- 日期（Date）：2026-06-07
- 发现（Finding）：当前工作区候选的 AGENT2 手动等待 run 不可作为通关或失败判读；它在 ante 3 small blind 达到 2790/2000 后，于 `cash_out` 触发 Lovely `round_eval` nil 崩溃并中断。
- 证据（Evidence）：`python3 -m balatro_agent summarize-eval --log-dir runs/eval/live-20260607-agent2-manual-wait` 输出 `run_count: 1`、`status: "incomplete"`、`error_count: 2`、`failure_phase: "ROUND_EVAL"`、`final_ante: 3`、`final_score: 2790`、`final_required_score: 0`；`runs/eval/live-20260607-agent2-manual-wait/AGENT2.jsonl` 最后一条为 `cash_out` 连接超时；Lovely 日志 `/Users/suriness/Library/Application Support/Balatro/Mods/lovely/log/lovely-2026.06.07-09.39.33.log` 记录 `functions/common_events.lua:1220: attempt to index field 'round_eval' (a nil value)`。
- 来源（Source）：上述本地 JSONL 日志、`summarize-eval` 输出和 Lovely 日志。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：本轮不能声明 AGENT2 策略已改善到 4000 分关口；下一轮应先加固 live eval 的基础设施错误判定，或在稳定重启后重跑 AGENT2。
- 关联问题（Related question）：`Runner.run` 是否应把 live 过程中的连续 `gamestate` 超时、`Remote end closed connection` 和 Lovely 崩溃记录为 `infra_error`？

- 日期（Date）：2026-06-07
- 发现（Finding）：AGENT2 的当前候选仍带着 5 张牌型限定/低倍率 Joker 满槽进入 ante 3；即使能过 2000 分 small blind，也没有证据说明它已解决 4000 分关口的倍率不足。
- 证据（Evidence）：`runs/eval/live-20260607-agent2-manual-wait/AGENT2.jsonl` 在 ante 3 round 7 记录 Joker 组合为 `j_clever`、`j_hack`、`j_mystic_summit`、`j_sly`、`j_droll`，资金为 6；同局 shop 在 ante 3 前买入并使用 `Uranus` 后直接 `next_round`，未获得 X 倍率或稳定倍率 Joker。run 在 2790/2000 后崩溃，未到 AGENT2 既有失败点 4000 分。
- 来源（Source）：`runs/eval/live-20260607-agent2-manual-wait/AGENT2.jsonl`。
- 置信度（Confidence level）：Medium（中）。该观察来自不可完整判读 run，但崩溃前的状态和商店路径是直接日志证据。
- 影响（Impact）：下一轮策略仍应围绕“弱 chip Joker 满槽时保留现金/寻找倍率或 X 倍率”设计最小规则，而不是把本轮候选视为已晋升。
- 关联问题（Related question）：AGENT2 在 ante 3 前把现金用于低等级星球牌后，是否错过了替换弱满槽小丑牌的机会？

- 日期（Date）：2026-06-07
- 发现（Finding）：当前工作区候选在完整 `dev` cohort 上仍未通关，且整体不能视为相对 2026-06-06 最佳可判读结果的晋升。
- 证据（Evidence）：`COHORT=dev MAX_STEPS=500 LOG_DIR=runs/eval/live-20260607-current-candidate-dev sh scripts/eval.sh` 完成 3 个 seed；`python3 -m balatro_agent summarize-eval --log-dir runs/eval/live-20260607-current-candidate-dev` 输出 `run_count: 3`、`win_count: 0`、`loss_count: 3`、`max_ante: 6`、`error_count: 0`、`rejected_count: 0`。AGENT1 为 25960/30000，AGENT2 为 3506/4000，AGENT3 为 17413/22000；对照 `runs/eval/live-20260606-dev-banner-gros/AGENT3.jsonl` 的 17928/22000，AGENT3 仍低于最佳可判读路径。
- 来源（Source）：`runs/eval/live-20260607-current-candidate-dev/*.jsonl`、`strategy/runs/live-2026-06-07-current-candidate-dev-replay.jsonl`、本次 `eval` 和 `summarize-eval` 输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：当前候选可作为失败证据保留，但不应晋升为通关策略；下一轮应回到更窄的 AGENT2 构筑规则或 AGENT1/AGENT3 中后期倍率来源，而不是继续扩大当前混合启发式。
- 关联问题（Related question）：当前 baseline agent 的决策日志中有哪些常见失败模式？策略晋升门槛应使用哪些阈值？

- 日期（Date）：2026-06-07
- 发现（Finding）：live runner 在 `ROUND_EVAL` 过早 `cash_out` 和 `NEW_ROUND` 过渡上不够稳；加入结算等待和 `NEW_ROUND` transient 后，本轮后续 AGENT2 策略 run 不再复现 `round_eval` nil 中断。
- 证据（Evidence）：`runs/eval/live-20260607-half-wall-agent2-retry/AGENT2.jsonl` 在越过 4000 分后因 `ROUND_EVAL`/`NEW_ROUND` 附近的 `round_eval` nil 路径中断；随后 `balatro_agent/runner.py` 增加 `ROUND_EVAL_SETTLE_SECONDS = 2.0` 并把 `NEW_ROUND` 加入 `TRANSIENT_PHASES`，`python3 -m unittest discover -s tests` 通过 119 个测试；`runs/eval/live-20260607-protect-abstract-core-agent2/AGENT2.jsonl` 完整到 `GAME_OVER`，error 0、rejected 0。
- 来源（Source）：上述本地 JSONL 日志；`balatro_agent/runner.py`；`tests/test_runner.py`；本次单元测试输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：策略评估更可判读，但后续仍需要把 Lovely/Balatro 崩溃显式标成基础设施错误，避免与游戏内失败混淆。
- 关联问题（Related question）：Runner 还应把哪些 BalatroBot phase 作为 transient 处理？`Runner.run` 是否应把 live 过程中的连续连接错误记录为 `infra_error`？

- 日期（Date）：2026-06-07
- 发现（Finding）：AGENT2 的 `The Wall` 改善来自商店路线收敛，而不是手牌微调：跳过 Business/Droll 类低收益占槽、保护 `Sly`/`Scary Face`/`Half` 核心、延后 `Popcorn` 后，Supernova 分支最高到 19074/20000，但仍未过墙。
- 证据（Evidence）：`runs/eval/live-20260607-skip-droll-agent2/AGENT2.jsonl` 和 `runs/eval/live-20260607-preserve-popcorn-agent2/AGENT2.jsonl` 分别停在 15570/20000、17322/20000；`runs/eval/live-20260607-delay-popcorn-agent2/AGENT2.jsonl` 达到 19074/20000，score gap 缩小到 926。后续测试的最后弃牌、开局成型对子和 face pair 保护分别未提高该 19074 结果，且开局成型对子退化到 15232/20000。
- 来源（Source）：上述本地 JSONL 日志和对应 `summarize-eval` 输出；`balatro_agent/agents.py`；`tests/test_orchestrator.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：AGENT2 的主要收益来自商店构筑，而不是当前手牌规则微调；后续应继续围绕可解释的 Joker 替换和 Boss 前目标牌设计。
- 关联问题（Related question）：哪些商店决策对后续 ante 的负面影响最大？哪些手牌选择启发式最常错过更高分方案？

- 日期（Date）：2026-06-07
- 发现（Finding）：在 AGENT2 小牌型构筑中，`Hanging Chad` 可以替换 `Supernova` 而不是 `Sly Joker`，该路线首次稳定越过 `The Wall`；但如果后续卖掉 `Scary Face` 或 `Sly Joker`，ante 5 会明显退化。
- 证据（Evidence）：`runs/eval/live-20260607-chad-supernova-agent2/AGENT2.jsonl` 在 ante 4 shop 卖出 `Supernova` 买入 `Hanging Chad`，`The Wall` 分数序列推进到 4485、13650、17979 后越过 20000，随后在 ante 5 `The Needle` 以 2730/11000 失败；`runs/eval/live-20260607-protect-chad-core-agent2/AGENT2.jsonl` 保护 `Sly`/`Scary Face` 后推进到 ante 5 Big Blind 的 13696/16500；`runs/eval/live-20260607-abstract-chad-core-agent2/AGENT2.jsonl` 虽替换 `Popcorn` 为 `Abstract Joker`，但卖掉 `Scary Face` 后仍只到 14633/16500。
- 来源（Source）：上述本地 JSONL 日志和对应 `summarize-eval` 输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：`Sly`/`Scary Face`/`Half`/`Hanging Chad` 是该分支的核心，不应被 `Scholar` 或泛用倍率牌轻易替换；后续替换对象应优先是衰减或非核心牌。
- 关联问题（Related question）：在什么组合下 `Hanging Chad` 才能作为 Boss 前替换目标？AGENT2 当前主要失败点是否已转为 The Needle 单手爆发不足？

- 日期（Date）：2026-06-07
- 发现（Finding）：当前最佳 AGENT2 分支为 `Sly Joker`、`Scary Face`、`Half Joker`、`Hanging Chad`、`Abstract Joker`，已能越过 `The Wall` 和 ante 5 Big Blind，但在 `The Needle` 以 8930/11000 失败。
- 证据（Evidence）：`runs/eval/live-20260607-protect-abstract-core-agent2/AGENT2.jsonl` 完整到 `GAME_OVER`，error 0、rejected 0，终局为 ante 5 `The Needle`、8930/11000、score gap 2070，Joker 为 `j_sly`、`j_scary_face`、`j_half`、`j_hanging_chad`、`j_abstract`。同局 `The Needle` 起手为 `H_Q`、`D_Q`、`H_8`、`C_8`、`S_7`、`H_3`、`C_3`、`H_2`，弃掉低牌后最终一手得 8930。
- 来源（Source）：`runs/eval/live-20260607-protect-abstract-core-agent2/AGENT2.jsonl`；本次 `summarize-eval` 输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：当前 AGENT2 瓶颈已从 ante 3/4 推进到 ante 5 Boss 单手得分；下一轮应聚焦 The Needle 前的 X 倍率/消耗牌/牌型等级或专用出牌策略。
- 关联问题（Related question）：AGENT2 在 The Needle 前应优先寻找一次性 X 倍率、目标重掷、消耗牌，还是调整单手 Boss 出牌策略？

- 日期（Date）：2026-06-07
- 发现（Finding）：The Needle 前额外无目标重掷不是有效改进；找到 Scholar/Card Sharp 线索后仍未提高最佳 8930/11000 结果。
- 证据（Evidence）：`runs/eval/live-20260607-needle-reroll-agent2/AGENT2.jsonl` 终局同样为 ante 5 `The Needle`、8930/11000、score gap 2070，且现金从最佳分支的 34 降到 18；该重掷规则已从代码和测试中撤回。
- 来源（Source）：`runs/eval/live-20260607-needle-reroll-agent2/AGENT2.jsonl`；本次 `summarize-eval` 输出；`balatro_agent/agents.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：后续 reroll 仍必须绑定明确可买目标和替换对象；不能仅因接近 Boss 且有现金就扩大重掷。
- 关联问题（Related question）：策略晋升门槛应使用哪些阈值？哪些商店决策对后续 ante 的负面影响最大？

- 日期（Date）：2026-06-07
- 发现（Finding）：AGENT2 的“弱 chip Joker 满槽且 15 金时重掷”不是有效改进；它触发了一次 reroll，但最终仍以同样的 3506/4000 失败。
- 证据（Evidence）：`runs/eval/live-20260607-agent2-current-candidate/AGENT2.jsonl` 和 `runs/eval/live-20260607-current-candidate-dev/AGENT2.jsonl` 均显示 ante 3 round 8 时持有 `j_clever`、`j_mystic_summit`、`j_sly`、`j_droll`、`j_zany` 且 money=15，商店为 `Scary Face`/`Splash`，当前候选执行 `reroll`；随后未买到倍率或 X 倍率 Joker，最终 ante 3 Boss `The Goad` 为 3506/4000。对照 `runs/eval/live-20260606-2320-shop-discipline-retry/AGENT2.jsonl`，旧路径在同一商店选择 `next_round` 也同样 3506/4000。
- 来源（Source）：上述本地 JSONL 日志和本次 `jq` 抽取的 SHOP / SELECTING_HAND 决策路径。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：后续 reroll 不能只由“弱满槽 + 15 金 + 当前无可买项”触发；更有价值的下一步是提前避免 `Clever`/`Mystic Summit`/`Sly`/`Droll`/`Zany` 这类牌型限定 chip Joker 堆满槽，或在 ante 2 前优先选择倍率/X 倍率 Joker。
- 关联问题（Related question）：AGENT2 在 ante 3 前把现金用于低等级星球牌后，是否错过了替换弱满槽小丑牌的机会？AGENT2 在 ante 2 前是否应降低牌型限定 chip Joker 的堆叠价值？

- 日期（Date）：2026-06-07
- 发现（Finding）：降低第三张窄条件 Joker 的购买价值让 AGENT2 越过长期卡住的 4000 分关口，但完整 `dev` 仍未通关。
- 证据（Evidence）：新增 `tests/test_orchestrator.py::test_shop_prefers_misprint_over_third_chip_joker_in_agent2_shape` 固定已有 `Clever`/`Hack` 时优先买 `Misprint` 而不是第三张窄条件 Joker `Mystic Summit`；`python3 -m unittest discover -s tests` 通过 106 个测试。`runs/eval/live-20260607-agent2-early-misprint/AGENT2.jsonl` 显示 AGENT2 在 ante 2 round 3 买入 `Misprint`，最终到 ante 4 `The Wall` 的 17865/20000。完整 `runs/eval/live-20260607-early-conditional-dev` 为 AGENT1 25960/30000、AGENT2 17865/20000、AGENT3 17413/22000，`win_count: 0`。
- 来源（Source）：`balatro_agent/agents.py`、`tests/test_orchestrator.py`、`runs/eval/live-20260607-agent2-early-misprint/AGENT2.jsonl`、`runs/eval/live-20260607-early-conditional-dev/*.jsonl`、`strategy/runs/live-2026-06-07-early-conditional-dev-replay.jsonl`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：早期构筑规则应保留为局部正向约束；下一步重点从 AGENT2 的 ante 3 弱满槽转移到 ante 4 `The Wall` 大盲需求、Boss 前商店替换和中后期倍率/X 倍率来源。
- 关联问题（Related question）：AGENT2 在 ante 2 前是否应降低牌型限定 chip Joker 的堆叠价值？AGENT2 在越过 4000 后如何补足 `The Wall` 的 2135 分缺口？

- 日期（Date）：2026-06-07
- 发现（Finding）：在 AGENT2 `Half Joker`/`Scary Face` 构筑里静态提高 `Hanging Chad` 价值并替换 `Sly Joker` 是负向改动。
- 证据（Evidence）：临时候选通过测试强制 Boss 前商店用 `Hanging Chad` 替换 `Sly Joker`，`runs/eval/live-20260607-agent2-chad-wall/AGENT2.jsonl` 最终持有 `j_scary_face`、`j_half`、`j_supernova`、`j_popcorn`、`j_hanging_chad`，在 ante 4 `The Wall` 只到 15573/20000；撤回该规则后 `runs/eval/live-20260607-agent2-early-misprint/AGENT2.jsonl` 与完整 `dev` 复测均为 17865/20000。
- 来源（Source）：`runs/eval/live-20260607-agent2-chad-wall/AGENT2.jsonl`、`runs/eval/live-20260607-agent2-early-misprint/AGENT2.jsonl`、本轮撤回后的 `balatro_agent/agents.py` 和 `tests/test_orchestrator.py`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：不要把 `Hanging Chad` 作为 `Half Joker`/`Scary Face` 牌组的静态替换目标；后续应只在有 `Photograph`、足够 face card 质量或直接日志收益时再测试。
- 关联问题（Related question）：AGENT2 在越过 4000 后如何补足 `The Wall` 的 2135 分缺口？

### 2026-06-11

- 日期（Date）：2026-06-11
- 发现（Finding）：AGENT1 的固定 seed 路线可通过 `Campfire` 消耗牌循环、`Supernova` 持久倍率和 Pair 训练，从原先 ante 6 的 25960/30000 推进到 ante 8 Small Blind；但仍未通关。
- 证据（Evidence）：`runs/eval/live-20260611-baseline-recheck/AGENT1.jsonl` 复现 ante 6 Big Blind 25960/30000；`runs/eval/live-20260611-agent1-campfire-gros/AGENT1.jsonl` 首次推进到 ante 7；`runs/eval/live-20260611-agent1-campfire-chaos-free-retry2/AGENT1.jsonl` 通过 ante 7 Boss `The Wheel`，以 73069/70000 进入 ante 8，最终在 Small Blind 18785/50000 失败；`runs/eval/live-20260611-agent1-matador-carry/AGENT1.jsonl` 的 ante 8 最佳为 21128/50000。
- 来源（Source）：上述本地 JSONL 决策日志及对应 `summarize-eval` 输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：AGENT1 的首要瓶颈已从 ante 5/6 中期倍率不足转为 ante 8 重置后的持久战力和首店经济；Campfire 路线可继续作为实验基线，但尚不应晋升为通关策略。
- 关联问题（Related question）：AGENT1 在 ante 8 Campfire 重置后，应依靠持久 X 倍率、更多跨 ante 现金，还是替换 Campfire？

- 日期（Date）：2026-06-11
- 发现（Finding）：AGENT1/红牌组/白注固定 seed 的“保留 Delayed 经济 + Stencil 空槽 + Campfire 分段投入”路线已从全新游戏状态独立复现 `game_over_win`；跨 Boss 现金可重复解决 ante 8 Campfire 重置后的首战缺口。
- 证据（Evidence）：首轮在 ante 2 卖 `Gluttonous Joker` 而不是 `Delayed Gratification`，随后用 `Joker Stencil` 保持空槽、卖 Delayed 换 `Egg`，并在 ante 5/6 保护 68 金、ante 7 保护 63 金。独立复现从 `MENU` 启动并完整运行 264 步；`runs/eval/live-20260611-agent1-delayed-bank-repro/AGENT1.jsonl` 记录 ante 7 Boss 90508/70000、ante 8 Small Blind 55264/50000、Big Blind 83556/75000，终局 `phase: GAME_OVER`、`won: true`。`summarize-eval` 返回 `win_count: 1`、error/rejected 均为 0，与首轮胜局一致。
- 来源（Source）：`runs/eval/live-20260611-agent1-delayed-bank/AGENT1.jsonl`、`runs/eval/live-20260611-agent1-delayed-bank-resume/AGENT1.jsonl`、`runs/eval/live-20260611-agent1-delayed-bank-repro/AGENT1.jsonl` 及对应 `summarize-eval` 输出。
- 置信度（Confidence level）：High（高）。路线已在一次续跑胜局和一次全新状态完整胜局中成立；跨 seed 泛化仍未验证。
- 影响（Impact）：AGENT1 的 fixed-seed 研究基线应切换为 Delayed/Stencil/Campfire 经济路线；下一步把固定金额阈值改成动态预算并做 regression/heldout 验证，不能直接把 seed 特定规则写入生产策略。
- 关联问题（Related question）：如何把固定金额阈值改成基于 Boss 所需得分和预期商店成本的动态预算，并推广到其他 seed？

- 日期（Date）：2026-06-11
- 发现（Finding）：本地 BalatroBot 对 AGENT1 的 Amber Acorn 胜局可重复返回 `won: true`，同时终局摘要仍为 17680/100000；该字段组合不是一次性续跑异常。
- 证据（Evidence）：`live-20260611-agent1-delayed-bank-resume` 和从全新状态运行的 `live-20260611-agent1-delayed-bank-repro` 都以 `phase: GAME_OVER`、`won: true`、`score: 17680`、`required_score: 100000` 结束；后者前两盲分别明确记录 55264/50000 和 83556/75000。
- 来源（Source）：上述两个本地 JSONL 日志和 `summarize-eval` 输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：当前安装版本的胜负判定必须以 `GAME_OVER.won` 为准，不能用终局 `score >= required_score` 重新推断；仍需核对 Amber Acorn 终局分数字段的上游语义。
- 关联问题（Related question）：真实 BalatroBot 结束局是否稳定返回 `won` 字段，并与本地胜负契约一致？

- 日期（Date）：2026-06-11
- 发现（Finding）：AGENT1 之前的跨 ante 经济实验没有生效，原因是默认商店代理在 ante 2 为购买 `Half Joker` 提前卖掉了 `Delayed Gratification`；只在拿到 Stencil 后写“保留 Delayed”规则无法改变这条早期路径。
- 证据（Evidence）：旧日志 `runs/eval/live-20260611-agent1-stencil-delayed-reserve/AGENT1.jsonl` 在 ante 2 round 5 的初始 Joker 包含 `j_delayed_grat`，卖出动作后该 key 消失；新日志 `runs/eval/live-20260611-agent1-delayed-bank/AGENT1.jsonl` 改卖 `j_gluttenous_joker`，并在 ante 3--4 持续保留 `j_delayed_grat`，资金在 ante 4 round 10 达到 95。
- 来源（Source）：上述本地 JSONL 日志。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：经济 Joker 的研究必须检查其首次出售时点，不能只检查最终构筑；早期槽位替换可能在目标策略分支生效前就删除关键资源。
- 关联问题（Related question）：哪些商店决策对后续 ante 的负面影响最大？

- 日期（Date）：2026-06-11
- 发现（Finding）：AGENT1 中不能用 additive Mult Joker 替换 `Blue Joker`；`Blue Joker` 的筹码供给是 `Half Joker`/Campfire 小牌型核心的一部分。`Photograph` 与 `Hanging Chad` 的组合也不足以补偿丢失的稳定筹码或后置倍率。
- 证据（Evidence）：`runs/eval/live-20260611-agent1-supernova-swap/AGENT1.jsonl` 在卖 `Blue Joker` 买 `Supernova` 后退化到 ante 6 的 14040/30000；`runs/eval/live-20260611-agent1-photograph-swap/AGENT1.jsonl` 为 14816/22000；保留 Blue 但用 Photograph 替换 Abstract 的 `runs/eval/live-20260611-agent1-photo-for-abstract/AGENT1.jsonl` 仍只有 18922/22000。
- 来源（Source）：上述本地 JSONL 日志。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：后续 AGENT1 Joker 替换应优先卖 `Scholar`、衰减牌或低贡献槽位，不应静态卖出 `Blue Joker`。
- 关联问题（Related question）：哪些 Joker 能在保留 Blue/Half 核心的前提下提供跨 ante X 倍率？

- 日期（Date）：2026-06-11
- 发现（Finding）：Pair 训练和 Boss 专用弃牌是本轮最有效的手牌调整；全局无条件改写会在 ante 5 `The Arm` 失败，但避开该 Boss 的早期爆发后，可以让 `Supernova` 的 Pair 累计帮助通过 ante 7 Big Blind，并把 `The Wheel` 从 56809/70000 提高到 68843/70000，后续路线完成过关。
- 证据（Evidence）：`runs/eval/live-20260611-agent1-campfire-pair-training/AGENT1.jsonl` 因在 `The Arm` 强制 Pair 退化到 19096/22000；`runs/eval/live-20260611-agent1-campfire-pair-training-safe/AGENT1.jsonl` 推进到 `The Wheel` 56809/70000；`runs/eval/live-20260611-agent1-campfire-wheel-discard/AGENT1.jsonl` 在无对子时使用两次五张弃牌追 Pair，达到 68843/70000；随后 Chaos 免费重掷分支通过该 Boss。
- 来源（Source）：上述本地 JSONL 日志。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：手牌策略应按 Boss 和构筑限定，而不是全局提高 Pair 优先级；`The Wheel` 等高门槛 Boss 在有弃牌时不应直接打弱 High Card。
- 关联问题（Related question）：哪些 Boss/构筑组合值得使用专用弃牌搜索，而不破坏早期生存？

- 日期（Date）：2026-06-11
- 发现（Finding）：Campfire 每次出售只增加 X0.25，且击败 Boss 后重置；ante 7 为过关累计 18--19 次出售后，ante 8 首店只有 6--9 金，最多完成 2--3 次出售，无法覆盖 50000 分 Small Blind。
- 证据（Evidence）：终局 `gamestate` 显示 `Campfire` 文本为“每卖出一张牌 X0.25，Boss 盲注被击败时重置”；`runs/eval/live-20260611-agent1-campfire-chaos-free-retry2/AGENT1.jsonl` 在 ante 7 有 19 次出售、通过 70000 分 Boss，ante 8 仅 2 次出售并得到 18785/50000；`runs/eval/live-20260611-agent1-matador-carry/AGENT1.jsonl` 保留 Matador 后 ante 8 仅 3 次出售，得到 21128/50000，且 Matador 未在 `The Wheel` 产生现金。
- 来源（Source）：本地 BalatroBot `gamestate` 与上述 JSONL 日志。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：下一轮不能只继续增加 ante 7 Campfire 销售；必须在进入 ante 8 前保留持久倍率或显著现金，或者选择不依赖 Boss 重置倍率的构筑。
- 关联问题（Related question）：AGENT1 在 ante 8 Campfire 重置后，应依靠持久 X 倍率、更多跨 ante 现金，还是替换 Campfire？

### 2026-06-13

- 日期（Date）：2026-06-13
- 发现（Finding）：`evolvedv2` 到 `evolvedv8` 的完整三 seed 结果总体向上但不单调；v8 是相对 v7 的局部 Pareto 改善，却仍不是稳健收敛或通关趋势。
- 证据（Evidence）：`summarize-eval` 显示 v6 为 AGENT1 15011/22000、AGENT2 17804/20000、AGENT3 17694/22000；v7 将 AGENT1 提高到 ante 6 的 27950/30000，AGENT2/3 不变；v8 保持 AGENT1 27950/30000、AGENT2 17804/20000，并将 AGENT3 提高到 19984/22000。v2、v3、v5、v6、v7、v8 的完整 cohort 均为 `win_count: 0`，且中间存在 v5 到 v6 的明显回退。
- 来源（Source）：`runs/eval/live-20260612-095200-evolvedv2`、`live-20260612-100400-evolvedv3`、`live-20260612-104000-evolvedv5`、`live-20260612-214300-evolvedv6`、`live-20260613-151500-evolvedv7`、`live-20260613-194200-evolvedv8` 及本轮 `summarize-eval` 输出。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：短期可确认选择压力对 AGENT1/3 有效，但不能只按版本号或单一 aggregate 指标判断进化成功；必须保留 per-seed elite，并补 regression/heldout 晋升门禁。
- 关联问题（Related question）：如何比较多代 genome 权重，才能避免过拟合到很小的 seed 集？策略晋升门槛应使用哪些阈值？

- 日期（Date）：2026-06-13
- 发现（Finding）：当前自动候选没有保留项目已知的最佳单 seed 能力，说明研究策略知识到生产进化目标之间仍有断层。
- 证据（Evidence）：2026-06-11 的定制 Delayed/Stencil/Campfire 路线在 AGENT1 两次返回 `won: true`；2026-06-07 的 AGENT2 最佳路线到 ante 5 `The Needle` 的 8930/11000。相比之下，v8 的 AGENT1 在 ante 6 以 27950/30000 失败，AGENT2 在 ante 4 以 17804/20000 失败。
- 来源（Source）：`runs/eval/live-20260611-agent1-delayed-bank-repro/AGENT1.jsonl`、`runs/eval/live-20260607-protect-abstract-core-agent2/AGENT2.jsonl`、`runs/eval/live-20260613-194200-evolvedv8/*.jsonl`。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：下一轮进化不应只继续叠加启发式；应先让 fitness/promotion gate 显式保护已知胜局和每个 seed 的最佳进度，否则会把局部改善误判为整体学习。
- 关联问题（Related question）：当前进化选择是否应维护 per-seed elite/Pareto archive？

### 2026-06-14

- 日期（Date）：2026-06-14
- 发现（Finding）：本机 BalatroBot 的 `save`/`load` checkpoint 能在 `SELECTING_HAND` 和 `SHOP` 稳定恢复根状态，并复现相同动作分支。
- 证据（Evidence）：已安装 BalatroBot 官方 `docs/api.md` 与 `src/lua/endpoints/save.lua`/`load.lua` 均声明 `path` 参数；真实 smoke 在 AGENT1 Big Blind 的 `SELECTING_HAND` checkpoint 中两次执行同一 `play [1,2,3,4]`，都得到 112/450、相同后续 8 张手牌和相同剩余牌数；SHOP checkpoint 中两次购买 `Gluttonous Joker`，都得到 4 金、1 Joker、商店只剩 `Burglar`。两次最终恢复的状态摘要均与根状态一致。
- 来源（Source）：`/Users/suriness/Library/Application Support/Balatro/Mods/balatrobot/docs/api.md`、同目录 `src/lua/endpoints/save.lua` 与 `load.lua`、2026-06-14 本机 `127.0.0.1:12346` 直接观察。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：Checkpoint Beam 的核心基础设施假设成立；后续问题集中在搜索成本、价值函数和跨 seed 晋升，而不是 save/load 可用性。
- 关联问题（Related question）：如何降低真实 checkpoint rollout 成本，同时保持分支可比性？

- 日期（Date）：2026-06-14
- 发现（Finding）：默认 6/12 分支与 4/6 步 rollout 在当前 BalatroBot 上成本过高，且高频动作会出现“动作已生效但 HTTP 响应关闭”的可恢复传输告警。
- 证据（Evidence）：真实手牌 Planner smoke 的 2 分支、0 rollout 耗时 11.0 秒，商店为 3.3 秒；完整配置的 AGENT1 部分 run 中，6 分支手牌决策分别耗时约 35.4--85.0 秒，3 候选商店决策耗时约 50.3 秒。`runs/eval/live-20260614-checkpoint-dev/AGENT1.jsonl` 7 分钟只完成 10 个动作，并出现 2 次 `Remote end closed connection without response`，但后续状态检查确认动作已生效；该 run 在完成 dev 前主动终止。
- 来源（Source）：`runs/eval/live-20260614-checkpoint-dev/AGENT1.jsonl`、2026-06-14 live smoke 输出、`balatro_agent/runner.py` 的状态变化确认逻辑。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：当前实现功能正确但尚未达到完整分层进化的可承受吞吐；需要缓存、缩短场景 rollout、减少高成本分支或并行独立实例。动作已生效的断连应记为 warning，不能误算新增策略 error。
- 关联问题（Related question）：Checkpoint 场景评估应采用哪些成本预算，才能在不削弱防遗忘门禁的前提下完成 8×3 进化？

### 2026-06-18

- 日期（Date）：2026-06-18
- 发现（Finding）：当前策略代码已补充两个顺序控制能力：`HandAgent` 会在重触发增强牌或 `Photograph` 首张人头牌收益依赖物理手牌顺序时先提出 `rearrange hand`；新增 `JokerOrderAgent` 会在商店阶段、已持有 X 倍率 Joker 且顺序不佳时提出 `rearrange jokers`，把筹码、加倍率、X 倍率类 Joker 排成更合理的结算顺序。
- 证据（Evidence）：新增 `tests/test_orchestrator.py::test_selecting_hand_rearranges_trigger_card_before_playing_with_hanging_chad`，旧代码返回 `play`，实现后返回 `rearrange {"hand": [2, 0, 1, 3]}`；新增 `tests/test_orchestrator.py::test_shop_rearranges_jokers_chip_mult_xmult_order_before_next_round`，旧代码返回 `next_round`，实现后返回 `rearrange {"jokers": [1, 2, 0]}`。`python3 -m unittest tests.test_orchestrator` 通过 75 个测试。
- 来源（Source）：`balatro_agent/agents.py`、`tests/test_orchestrator.py`、本次单元测试输出。
- 置信度（Confidence level）：High（高）用于代码行为；Medium（中）用于策略收益，因为尚未运行真实 BalatroBot `dev`/`regression` 对照。
- 影响（Impact）：后续 live run 不再只能靠 `play` 参数顺序表达计分顺序，可以显式调用 BalatroBot `rearrange`；但排序动作会消耗一步，需要用固定 seed 对照确认收益大于动作成本。
- 关联问题（Related question）：哪些手牌选择启发式最常错过更高分方案？当前 baseline agent 的决策日志中有哪些常见失败模式？

- 日期（Date）：2026-06-18
- 发现（Finding）：Ice Cream 衰减评分（ante-based decay）单独不足以解决 AGENT3 空槽问题。即使 ante 4 时 Ice Cream 评分从 34 降至 24，joker_replacement_margin (15) 仍要求商店 joker 评分达到 39+ 才能触发替换，大多数非 X-mult joker 达不到此门槛。AGENT3 的瓶颈不是 Joker 评分问题，而是商店中缺乏可替换 joker。
- 证据（Evidence）：5 轮 dev cohort 评估中，AGENT3 始终保持 19984/22000、4/5 joker 槽。Ice Cream 在 ante 5 过期后留空槽，但此前商店 reroll 未出现可替换 joker。v4 安全参数下该改动不引起任何 seed 退化但也不改善结果。
- 来源（Source）：runs/eval/live-20260618-093000 ~ live-20260618-102000-v5、balatro_agent/agents.py。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：后续空槽修复应从商店 joker 可用性和替换门槛两方面同时入手，不能只依赖评分微调。
- 关联问题（Related question）：空槽填充应通过提升 joker 购买评分、降低 cash_reserve、还是动态降低 replacement_margin 实现？

- 日期（Date）：2026-06-18
- 发现（Finding）：AGENT1 固定 seed 的重复 live run 中存在显著分数波动。相同代码、相同 seed、最终相同 Joker 组合 [Blue/Chad/Half/Abstract/Scholar] 在 ante 6 Big Blind 可产生 27950 或 20606 两种结果（差 7344 分）。这可能与 Lucky Card 现金触发波动有关（研究已记录约 20 金波动）。
- 证据（Evidence）：v1 基线为 27950/30000，v2/v3/v5 为 20606/30000，v4 恢复 27950/30000。所有 run 的最终 Joker 组合相同。
- 来源（Source）：runs/eval/live-20260618-093000 ~ live-20260618-102000-v5 的 AGENT1.jsonl。
- 置信度（Confidence level）：Medium（中）。波动模式与 Lucky Card 假设一致但尚未逐手对账现金变化。
- 影响（Impact）：单次 AGENT1 评估的分数变化不应直接归因于策略改动；需要多次复测或用 cash_out 日志对账 Lucky Card 触发。
- 关联问题（Related question）：AGENT1 重复 live run 中 Lucky Card 是否会产生不可复现的 ~20 金波动？

- 日期（Date）：2026-06-18
- 发现（Finding）：Popcorn 评分改动（加入 key_scores 或改变衰减参数）会破坏 AGENT2 的固定构筑路径。将 Popcorn 从默认 14 分提升到 24 分导致 AGENT2 最终构筑从 [Sly/Supernova/Half/Popcorn/Raised Fist] 变为 [Sly/Supernova/Half/Raised Fist/Erosion]，终局分数从 17804 降到 14916-15014。
- 证据（Evidence）：v2/v3 包含 Popcorn 改动时 AGENT2 分数为 14916/15014；v4 回滚后恢复 17804。
- 来源（Source）：runs/eval/live-20260618-094500-v2、live-20260618-100000-v3、live-20260618-101200-v4 的 AGENT2.jsonl。
- 置信度（Confidence level）：High（高）
- 影响（Impact）：AGENT2 的构筑路径对评分参数高度敏感；后续改动需单 seed 验证后再全 cohort 运行。
- 关联问题（Related question）：AGENT2 是否应在 ante 2 前降低牌型限定 chip Joker 的堆叠价值？
