# 研究记忆

## 项目目标（Project Goal）

打造一个尽可能强的小丑牌（Balatro）策略项目：通过 Markdown 策略记忆、周期性研究和可重复评估，持续提升自动化 agent 的策略质量、通关稳定性、得分能力、BalatroBot 集成行为和决策日志分析能力，长期目标是通关所有难度的小丑牌。

## 当前理解（Current Understanding）

- 本仓库包含一个 Python 多 agent Balatro 自动化层，用于连接本地 BalatroBot JSON-RPC 服务。
- 现有代码优先关注稳定、可检查的控制流程，然后再逐步增强游戏策略。
- 项目目标已从基础自动化框架明确升级为长期追求强 Balatro 求解器；短期仍需要用可靠评估和日志分析支撑策略增强。
- 决策日志是分析失败、改进打分逻辑或调整 genome 权重的主要反馈循环。
- 本项目现在面向中文开发者维护：文档、研究工作流和开发者可见说明优先使用中文；协议字段、命令名、JSON key 和 BalatroBot 枚举值保持英文。
- 本项目统一把 Balatro 称为“小丑牌”；策略知识优先沉淀在 `strategy/` 和 `research/` 的 Markdown 文件中。
- Python 层应保持为最小工具适配层，流程编排优先放在 `scripts/*.sh` 中。

## 稳定事实（Stable Facts）

- Python 包名是 `balatro_agent`。
- 根据 `README.md`，项目除 Python 3.9+ 外没有运行时依赖。
- 测试命令是 `python3 -m unittest discover -s tests`。
- BalatroBot 通常应在 `http://127.0.0.1:12346` 提供本地 JSON-RPC 服务。
- 仓库已有 client、runner、orchestrator、actions、evolution 相关测试和示例数据。
- 策略记忆入口是 `strategy/index.md`。
- 只读评估日志汇总入口是 `python3 -m balatro_agent summarize-eval --log-dir runs/eval` 或 `sh scripts/summarize-eval.sh`。
- 固定 seed 分组入口是 `config/eval-seeds.json`；`dev`、`regression`、`heldout` 分别用于快速迭代、回归检查和过拟合检查。
- replay 案例抽取入口是 `python3 -m balatro_agent build-replay --log-dir runs/eval --output strategy/runs/replay.jsonl` 或 `sh scripts/build-replay.sh`。
- 策略晋升门槛入口是 `python3 -m balatro_agent promotion-gate --baseline BASELINE.json --candidate CANDIDATE.json --cohort regression` 或 `sh scripts/promotion-gate.sh`。
- replay 案例查询入口是 `python3 -m balatro_agent replay-query --replay strategy/runs/replay.jsonl --phase SHOP --limit 5`。
- 本机真实 Balatro 可通过 Steam 安装目录中的 `run_lovely_macos.sh` 加载 Lovely 和 BalatroBot；2026-05-31 观察到 BalatroBot mod 版本为 `1.4.0`，并能在 `127.0.0.1:12346` 响应 `health`。
- 人工游玩状态记录入口是 `python3 -m balatro_agent record --output runs/human/manual.jsonl --interval 1`；后台启动/停止脚本是 `scripts/record-human-start.sh` 和 `scripts/record-human-stop.sh`。该 recorder 只读 BalatroBot `gamestate`，不记录系统键鼠或屏幕，也不执行游戏动作。

## 工作假设（Working Assumptions）

- 最高价值的研究循环是：对比决策日志和游戏结果，识别弱决策，再在后续实现工作中调整策略代码或 genome 权重。
- BalatroBot 的 schema 和行为可能随上游变化，因此集成假设需要定期复查。
- 早期研究应优先关注评估可靠性和动作合法性，再推进高级策略优化。
- 子 agent 应只接收窄任务上下文，并把结论回写为研究发现或策略记忆候选，避免主上下文膨胀。
- 受持续学习方法论启发，后续策略自我迭代应把 BalatroBot 结果和固定 seed 回归作为外部验证锚点，并用 replay 经验库防止策略漂移或旧 seed 退化。
- 2026-06-01 用户提供新的策略 know-how：手牌阶段尽量优先追求顺子和同花；商店阶段优先选择成长型小丑牌；已有成长型小丑牌后，后续操作应优先增强或触发其成长条件。该条目前是工作假设，需用真实 run 和固定 seed 回归验证。
- 2026-06-01 `dev` cohort 通关尝试的失败更像策略强度和构筑质量不足，而不是动作执行错误：本次 3 个 seed 均无执行错误或 rejected 动作，但最高只到 AGENT1 的 ante 5、13224/22000。下一轮应优先检查早期手牌资源管理和中后期成长/倍率构筑。
- 2026-06-01 后续 live `dev` 迭代显示，保护 `Scholar`/`Photograph` 触发牌、无小丑最后一手用弃牌追顺/同花、降低 `Credit Card` 价值并提高 `Ice Cream` 早期价值，能显著提升固定 seed 进度：AGENT1 从 13224/22000 到 14816/22000；AGENT3 从 ante 1 的 240/300 推进到 ante 5 的 10875/11000。但 `dev` 仍无胜局，AGENT2 仍卡在 ante 3 的 2908/4000。
- 2026-06-06 当前候选策略在 `dev` cohort 仍无胜局，但显示了不同失败面：AGENT1 推进到 ante 6 的 25960/30000，AGENT2 小幅提升到 3130/4000，AGENT3 退回 ante 3 的 3796/4000。AGENT3 的主要新增失败原因是 Boss `The Psychic` 要求出 5 张牌而旧手牌选择会出 4 张两对，随后修正还暴露 `PLAY_TAROT` 应作为 transient phase 处理。

## 重要未知项（Important Unknowns）

- 决策日志中的哪些字段最能预测失败 run。
- 当前手牌和商店启发式失败的主要原因是打分缺口、合法动作缺失，还是状态解析不完整。
- 本地运行时使用的是哪个 BalatroBot 版本或 schema 修订。
- 应该用哪些基线指标定义“有意义的改进”。
- 如何定义小丑牌项目里的“遗忘”：旧 seed 最高 ante 下降、已解决失败模式复现、原有胜局丢失，还是阶段错误率上升。
- 真实 BalatroBot 结束局是否稳定返回 `won` 字段，并与本地胜负状态契约一致。
- 当前 live runner 返回值能看到终局状态，但 JSONL 决策日志只记录动作前状态；终局状态缺失会让 `summarize-eval` 和 `build-replay` 在真实失败局上失真。
- 初始 seed cohort 是否覆盖足够多的失败模式、deck/stake 差异和局型变化。
- AGENT3 的 125 分近失误不再是当前候选的最小失败点；下一步应先复测 `The Psychic` 五张出牌和 `PLAY_TAROT` transient 修正后，AGENT3 是否能恢复到 ante 5+，再继续判断 ante 5 round 13 的早期弃牌、`Madness` 破坏小丑牌、或 `Banner`/`Smiley Face` 置换影响。
- 人类游玩状态日志如何可靠映射为 replay 案例和可学习的人类操作意图。
- BalatroBot live 评估的基础设施稳定性仍需加固：Steam 未就绪或菜单状态异常时，`menu`/`start` 可能超时或返回 502，导致策略结果不可判读。

## 最后更新（Last Updated）

2026-06-06
