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
- 2026-06-06 live `dev` 迭代显示，修正 Psychic Boss 必须打 5 张牌、提高中后期 `Banner`/`Gros Michel` 对 plain `Joker` 的替换价值、并保留更谨慎的商店重掷策略后，完整 `dev` 仍无胜局：AGENT1 到 ante 6 的 25960/30000，AGENT2 到 ante 3 的 3130/4000，AGENT3 到 ante 5 的 17928/22000。AGENT3 相比 `live-20260606-current-dev-v3` 的 3796/4000 有明显进步，但仍缺中后期倍率/经济构筑。
- 2026-06-06 反例：在 AGENT3 已拥有 `Banner` 后，继续提高 `Supernova` 保护并强推 `Gros Michel` 替换 `Mad Joker` 会退化到 ante 4 的 6936/7500；后续不要直接保留该假设，应先分析替换时机和已有 Joker 的真实累计价值。
- 2026-06-06 后续商店纪律迭代降低 `Red Card`、`Rocket`、`Hallucination`、纯经济 Joker 等低即时战力牌的静态评分，并用测试覆盖 `Red Card` 不压过直接得分 Joker、`Rocket` 不压过行星牌/存钱。live 验证仍无通关：AGENT1 保持 25960/30000，AGENT2 为 3506/4000，AGENT3 为 17413/22000；该改动不能视为完整晋升，只能作为低价值占槽牌防护的一部分。
- 2026-06-06 反例：晚期满 Joker 槽时，仅因高现金和当前商店无明显收益就提高 reroll 意愿，没有改善 AGENT3，最终仍为 17413/22000，低于 `live-20260606-dev-banner-gros` 的 17928/22000；后续重掷策略应加入更明确的目标和退化门槛。
- 2026-06-07 手动等待后重跑 AGENT2 的当前工作区候选，因 Lovely `round_eval` nil 在 `cash_out` 时崩溃而不可判读；日志只证明该候选能用 `j_clever`、`j_hack`、`j_mystic_summit`、`j_sly`、`j_droll` 组合越过 ante 3 small blind 的 2000 分（2790/2000），尚未证明能越过 AGENT2 关键的 4000 分关口或提升通关率。
- 2026-06-07 完整 `dev` 复测当前工作区候选仍为 0 胜：AGENT1 25960/30000，AGENT2 3506/4000，AGENT3 17413/22000，且 error/rejected 均为 0。AGENT2 的 15 金弱满槽重掷只把 ante 3 round 8 的 `Scary Face`/`Splash` 商店改为 reroll，最终仍失败；该候选不能晋升。下一轮应优先验证 ante 2 前降低牌型限定 chip Joker 堆叠价值、让倍率/X 倍率 Joker 或现金保留优先于第三/第四张 chip Joker。
- 2026-06-07 早期条件 Joker 降权是 AGENT2 的正向但未通关改动：已有 `Clever`/`Hack` 后把第三张窄条件 Joker（如 `Mystic Summit`）降权，使 AGENT2 在 ante 2 round 3 改买 `Misprint`，完整 `dev` 仍 0 胜但 AGENT2 从 3506/4000 推进到 ante 4 `The Wall` 的 17865/20000。AGENT1 持平 25960/30000，AGENT3 仍 17413/22000；下一步应聚焦 AGENT2 `The Wall` 的 2135 分缺口和 AGENT1/AGENT3 中后期倍率/X 倍率来源。
- 2026-06-07 反例：在 AGENT2 的 `Half Joker`/`Scary Face`/`Supernova`/`Popcorn` 构筑中，提高 `Hanging Chad` 协同并替换 `Sly Joker` 会让 `The Wall` 结果从 17865/20000 退到 15573/20000；该规则已撤回，后续不要静态强推该替换。
- 2026-06-07 当前最佳 AGENT2 小牌型路线已能越过 `The Wall`：保留 `Sly Joker`/`Scary Face`/`Half Joker` 核心，延后购买 `Popcorn`，用 `Hanging Chad` 替换 `Supernova` 而不是替换 `Sly Joker`，随后用 `Abstract Joker` 替换衰减后的 `Popcorn` 并保护 `Sly`/`Scary`/`Half`/`Hanging Chad`。最佳 live 结果推进到 ante 5 `The Needle`，以 8930/11000 失败；下一轮瓶颈是单手 Boss 的约 2070 分缺口。
- 2026-06-07 live runner 加固后更稳定：`ROUND_EVAL` 后等待 2 秒，并把 `NEW_ROUND` 作为 transient phase 处理，避免 `cash_out` 太早触发 Lovely `round_eval` nil 路径；后续仍应区分基础设施崩溃和策略失败。
- 2026-06-11 AGENT1 固定 seed 的真实 `game_over_win` 已从全新游戏状态独立复现：保留 `Blue Joker`/`Half Joker`，用 `Joker Stencil` 保持一个空槽，再建立 `Campfire`；ante 2 不卖 `Delayed Gratification`，而是卖 `Gluttonous Joker` 买 Half，随后卖 `Walkie Talkie`/`Hanging Chad` 保持 Stencil X2。Delayed 在 ante 4 Big Blind 前把资金提高约 47 金，再换入 `Egg`，并用跨 Boss 现金下限把资金带到 ante 8。复现局 ante 8 Small/Big Blind 分别为 55264/50000、83556/75000，终局返回 `won: true`。
- 2026-06-11 Campfire 的 Boss 重置瓶颈可由跨 ante 经济缓解，而不必先找到持久 X 倍率：两次 winning run 都在 ante 5/6 保护 68 金、ante 7 保护 63 金，只把超出部分用于 Campfire，进入 ante 8 后再释放现金重建倍率。该结论已在 AGENT1/白注/红牌组重复成立，尚未通过 regression/heldout 验证。
- 2026-06-11 反例：不要卖 `Blue Joker` 换 `Supernova`/`Photograph`；该核心依赖 Blue 的稳定筹码。Pair 训练也不能无条件覆盖 ante 5 `The Arm` 的 Scholar/A 爆发，应使用阶段和 Boss 条件。

## 重要未知项（Important Unknowns）

- 决策日志中的哪些字段最能预测失败 run。
- 当前手牌和商店启发式失败的主要原因是打分缺口、合法动作缺失，还是状态解析不完整。
- 本地运行时使用的是哪个 BalatroBot 版本或 schema 修订。
- 应该用哪些基线指标定义“有意义的改进”。
- 如何定义小丑牌项目里的“遗忘”：旧 seed 最高 ante 下降、已解决失败模式复现、原有胜局丢失，还是阶段错误率上升。
- 真实 BalatroBot 结束局是否稳定返回 `won` 字段，并与本地胜负状态契约一致。
- 当前 live runner 返回值能看到终局状态，但 JSONL 决策日志只记录动作前状态；终局状态缺失会让 `summarize-eval` 和 `build-replay` 在真实失败局上失真。
- 初始 seed cohort 是否覆盖足够多的失败模式、deck/stake 差异和局型变化。
- AGENT3 当前主要失败点已从 ante 3 Psychic 失分推进到 ante 5 round 15 的 17928/22000；下一步需要判断应优先补稳定倍率 Joker、X 倍率来源、牌型等级，还是减少后期无效重掷。
- 人类游玩状态日志如何可靠映射为 replay 案例和可学习的人类操作意图。
- BalatroBot live 评估的基础设施稳定性仍需加固：Steam 未就绪或菜单状态异常时，`menu`/`start` 可能超时或返回 502，导致策略结果不可判读。
- 本机 shell 设置了 `http_proxy`/`https_proxy` 时，访问 `127.0.0.1:12346` 可能被代理干扰并表现为 502；后续 live 命令应显式设置 `NO_PROXY=127.0.0.1,localhost` 或在客户端层绕过本地代理。
- BalatroBot live 运行中仍可能在商店过渡崩溃，例如 2026-06-06 观察到 Lua `attempt to index field 'shop' (a nil value)`；需要区分这类基础设施失败和策略失败。
- BalatroBot live 运行中还可能在 `cash_out` 后的结算 UI 崩溃，例如 2026-06-07 观察到 Lua `attempt to index field 'round_eval' (a nil value)`；这会把已过盲的 run 截断为 `incomplete`。
- AGENT2 当前已从 ante 3/4 瓶颈推进到 ante 5 `The Needle`：需要判断应优先补一次性 X 倍率、Boss 前目标重掷、消耗牌/牌型等级，还是 The Needle 专用的弃牌/出牌策略。
- AGENT1 的 Delayed/Stencil/Campfire fixed-seed winning route 已完成一次全新状态复现；仍未知能否推广到 regression/heldout，以及固定 68/63 金现金下限能否改成基于剩余 Boss、商店重掷成本和得分余量的动态预算。
- 固定 seed `AGENT1` 的 Lucky Card 金钱触发在重复 live run 中会造成约 20 金波动；需要判断这是上游随机语义、状态重置不完整，还是实验动作消耗随机序列造成的差异。
- AGENT1 两次 winning run 的 Amber Acorn 终局都同时返回 `game_over_win`/`won: true` 和 17680/100000；`won` 契约已重复成立，但仍需核对 BalatroBot 对最终 Boss 分数字段的报告语义。

## 最后更新（Last Updated）

2026-06-11
