# 研究决策

用这个文件记录会指导未来研究运行或实现工作的决策。

## 决策（Decisions）

### 2026-05-30

- 日期（Date）：2026-05-30
- 决策（Decision）：将决策日志和固定 seed 评估作为改进 Balatro agent 的主要研究反馈循环。
- 背景（Context）：项目 README 将决策日志描述为 Codex 分析的主要反馈循环，并说明第一个里程碑是稳定、可检查的控制流程。
- 推理（Reasoning）：本地日志和可复现评估是一手证据，可以把策略变化与观察到的行为连接起来。
- 后果（Consequences）：后续研究运行应优先收集、比较和解释运行日志，然后再提出策略变化。
- 被取代于（Superseded by）：无

### 2026-05-30

- 日期（Date）：2026-05-30
- 决策（Decision）：统一把 Balatro 称为“小丑牌”，并将项目方向明确为 Markdown 策略记忆优先、Python 最小化、shell 脚本驱动的策略项目。
- 背景（Context）：用户要求把术语沉淀到 README，并说明项目目标是根据小丑牌不同局型维护策略记忆，长期通关所有难度，同时减少 Python 代码、更多使用 `sh` 文件驱动和子 agent 拆分任务。
- 推理（Reasoning）：Markdown 记忆便于长期累积证据和策略，shell 脚本适合作为轻量编排入口，Python 保持在 BalatroBot 适配和动作执行层可以降低维护复杂度。
- 后果（Consequences）：新增策略记忆应优先写入 `strategy/`；新增流程优先写成 `scripts/*.sh`；只有经过日志或测试验证的稳定策略才考虑转成 Python。
- 被取代于（Superseded by）：无

### 2026-05-30

- 日期（Date）：2026-05-30
- 决策（Decision）：采用“持续学习 + 自我迭代”的保守改造路线：先建设 replay 经验库、固定 seed 回归基准、held-out 验证和策略晋升门槛，再把稳定策略转入 Python 或 genome 权重。
- 背景（Context）：用户提供的持续学习综述强调自我改进需要外部验证、replay、回归评估和稳定性-可塑性权衡；项目当前已把决策日志和固定 seed 评估作为主要反馈循环。
- 推理（Reasoning）：BalatroBot 运行结果、决策日志和固定 seed 是本项目的一手验证信号；先建立回归门槛可以减少策略过拟合、小样本进化漂移和旧能力遗忘。
- 后果（Consequences）：任何 hand/shop/blind 策略增强都应同时报告目标 seed 收益和回归 seed 退化；子 agent 任务包应逐步注入相关 replay 案例，而不是读取全量历史。
- 被取代于（Superseded by）：无

### 2026-06-02

- 日期（Date）：2026-06-02
- 决策（Decision）：人工游玩记录先采用显式启动/停止的 BalatroBot `gamestate` 轮询 recorder，而不是系统级键鼠监听或隐式后台录屏。
- 背景（Context）：用户希望在自己玩小丑牌时由项目后台记录操作；需要避免隐式监听，同时为策略研究保留一手证据。
- 推理（Reasoning）：BalatroBot 状态轮询是项目已有集成路径，能在不执行游戏动作、不读取系统输入的前提下记录游戏状态变化；JSONL 也能复用现有日志分析工作流。
- 后果（Consequences）：短期可以复盘人类操作导致的状态变化，但不能精确还原每次点击或按键；若后续需要更细粒度操作，需要另行实现显式授权的窗口录制、OCR 或 mod 事件日志。
- 被取代于（Superseded by）：无

### 2026-06-06

- 日期（Date）：2026-06-06
- 决策（Decision）：保留中后期 plain `Joker` -> `Banner`/`Gros Michel` 的满槽替换规则；不保留“拥有 `Banner` 后强推 `Gros Michel` 替换 `Mad Joker` 并保护 `Supernova`”的静态规则。
- 背景（Context）：AGENT3 在 `live-20260606-current-dev-v3` 因 Psychic 和中后期构筑不足停在 3796/4000。本轮测试了 Banner/Gros Michel 替换和一个更激进的 Gros Michel 替换假设。
- 推理（Reasoning）：`live-20260606-agent3-banner-gros` 将 AGENT3 推进到 17928/22000；但 `live-20260606-agent3-gros-replace` 退化到 6936/7500，说明后者破坏了更早商店路径或已有 Joker 累计价值。
- 后果（Consequences）：后续替换策略应加入累计价值/局面上下文，而不是继续扩大静态 Joker 分数表。
- 被取代于（Superseded by）：无

### 2026-06-06

- 日期（Date）：2026-06-06
- 决策（Decision）：保留 `Red Card`、`Rocket`、`Hallucination` 和纯经济 Joker 的低即时战力降权；不保留“晚期满槽且高现金就提高 reroll”的宽泛规则。
- 背景（Context）：本轮复盘发现后续候选曾买入 `Red Card`、`Rocket`、`Hallucination` 等低即时战力牌，导致槽位占用；同时测试过晚期满槽高现金 reroll 加成。
- 推理（Reasoning）：低即时战力降权有单元测试固定，符合已有 `Credit Card` 反例；但 live 结果仍无通关，且 AGENT3 最终 17413/22000，低于 `live-20260606-dev-banner-gros` 的 17928/22000，说明宽泛 reroll 加成没有通过外部验证。
- 后果（Consequences）：后续可以继续完善低价值占槽牌名单；reroll 改动必须绑定明确目标、替换对象和资金下限，并通过 dev/regression 对比后再保留。
- 被取代于（Superseded by）：无

### 2026-06-07

- 日期（Date）：2026-06-07
- 决策（Decision）：不晋升“AGENT2 弱 chip Joker 满槽且 15 金时重掷”的当前候选；下一轮 AGENT2 改动应提前到 ante 2 前的 Joker 选择和现金保留，而不是在满槽后做无目标 reroll。
- 背景（Context）：当前工作区候选在 AGENT2 ante 3 round 8 对 `Scary Face`/`Splash` 商店执行了一次 reroll，但完整 `dev` 复测仍 0 胜，AGENT2 仍为 3506/4000。
- 推理（Reasoning）：这次 reroll 只改变了商店路径和现金余额，没有带来倍率或 X 倍率来源，也没有改变终局分数。AGENT2 更早在 ante 2 round 3 选择 `Mystic Summit` 而不是 `Misprint`，随后继续堆 `Sly`、`Droll`、`Zany`，说明问题发生在满槽之前。
- 后果（Consequences）：后续候选应优先测试“降低第三/第四张牌型限定 chip Joker 价值、提高早期稳定倍率/X 倍率 Joker 或现金保留”的单一改动；若再测试 reroll，必须指定目标牌类、替换对象和资金下限。
- 被取代于（Superseded by）：无

### 2026-06-07

- 日期（Date）：2026-06-07
- 决策（Decision）：保留“已有两张窄条件 Joker 后，ante 2+ 降低第三张同类 Joker 价值”的 AGENT2 早期构筑规则；不保留 `Half Joker`/`Scary Face` 构筑中静态强推 `Hanging Chad` 替换 `Sly Joker` 的候选。
- 背景（Context）：上一轮证明满槽后 15 金无目标 reroll 无效，本轮把干预提前到 AGENT2 ante 2 round 3 的 `Misprint` / `Mystic Summit` 商店，并另外测试 Boss 前 `Hanging Chad` 替换。
- 推理（Reasoning）：早期降权让 AGENT2 从 3506/4000 推进到 ante 4 `The Wall` 的 17865/20000；完整 `dev` 仍 0 胜但 AGENT1 持平、AGENT2 明显改善、AGENT3 持平当前候选。相反，`Hanging Chad` 替换候选让 AGENT2 退到 15573/20000，低于保留候选。
- 后果（Consequences）：后续 AGENT2 研究重点转向 `The Wall` 大盲缺口、Boss 前商店目标和中后期倍率/X 倍率；不要把 `Hanging Chad` 静态升权为该构筑的默认替换。
- 被取代于（Superseded by）：无

### 2026-06-07

- 日期（Date）：2026-06-07
- 决策（Decision）：保留 live runner 的 `ROUND_EVAL` 结算等待和 `NEW_ROUND` transient 处理。
- 背景（Context）：本轮 AGENT2 早期重跑在越过 4000 分后曾因 `cash_out` 后 Lovely `round_eval` nil 中断，导致 run 不可判读。
- 推理（Reasoning）：等待结算和跳过短暂 `NEW_ROUND` 能避免过早执行下一步；后续可判读 run 完整到 `GAME_OVER`，且 `python3 -m unittest discover -s tests` 通过 119 个测试。
- 后果（Consequences）：保留该基础设施加固；后续若再遇到 Lovely/Balatro 崩溃，应新增显式 `infra_error` 记录，而不是回退该等待。
- 被取代于（Superseded by）：无

### 2026-06-07

- 日期（Date）：2026-06-07
- 决策（Decision）：AGENT2 小牌型路线保留 `Sly Joker`/`Scary Face`/`Half Joker` 核心；`Hanging Chad` 只在该分支中替换 `Supernova`，后续 `Abstract Joker` 可替换衰减后的 `Popcorn`，但不得轻易卖出 `Sly` 或 `Scary Face`。
- 背景（Context）：早期条件 Joker 降权后，AGENT2 卡在 `The Wall`；本轮测试了跳过 Droll、延后 Popcorn、Chad 替换 Supernova、Abstract 替换 Popcorn、保护核心和 Needle 前重掷等分支。
- 推理（Reasoning）：延后 `Popcorn` 的 Supernova 分支最高到 19074/20000；`Hanging Chad` 替换 `Supernova` 后首次越过 `The Wall`；保护 `Sly`/`Scary Face`/`Half`/`Hanging Chad` 并用 `Abstract Joker` 替换 `Popcorn` 后，AGENT2 推进到 ante 5 `The Needle` 的 8930/11000。相反，卖 `Sly`、卖 `Scary Face` 或 Needle 前无目标重掷都没有改善结果。
- 后果（Consequences）：下一轮不再围绕 `The Wall` 作为首要瓶颈，而应针对 ante 5 `The Needle` 的 2070 分缺口寻找单手爆发、X 倍率或消耗牌方案。
- 被取代于（Superseded by）：无

### 2026-06-07

- 日期（Date）：2026-06-07
- 决策（Decision）：不保留本轮无效的手牌微调和 Needle 前无目标重掷实验。
- 背景（Context）：为补足 `The Wall` 缺口，本轮短测过最后弃牌、优先打成型对子、face pair 保护，以及 The Needle 前额外重掷。
- 推理（Reasoning）：最后弃牌和 face pair 保护未改善 19074/20000；开局成型对子退化到 15232/20000；Needle 前额外重掷仍为 8930/11000 且消耗现金。
- 后果（Consequences）：这些实验只作为反例保留在研究记录中；后续手牌策略应基于更具体的 Boss/构筑证据再进入代码。
- 被取代于（Superseded by）：无

### 2026-06-11

- 日期（Date）：2026-06-11
- 决策（Decision）：把 AGENT1 的 `Campfire + Supernova + 条件 Pair 训练 + Chaos 免费重掷` 保留为研究实验基线，但暂不写入生产策略代码或晋升为通关策略。
- 背景（Context）：该路线从基线 ante 6 的 25960/30000 推进到 ante 8，且完整通过 ante 7 Boss；但 ante 8 Campfire 重置后最好只有 21128/50000，尚无胜局。
- 推理（Reasoning）：路线对中后期有显著正收益，并形成可解释的商店和 Boss 规则；但它依赖固定 seed 商店序列、Lucky Card 现金波动和大量定制动作，且未解决最终 ante，直接进入应用代码会过拟合并扩大维护面。
- 后果（Consequences）：下一轮继续使用该路线作为 AGENT1 对照；优先测试持久 X 倍率或跨 ante 经济的单一变化，并在出现真实 `game_over_win` 后再考虑代码化和 regression/heldout 验证。
- 被取代于（Superseded by）：2026-06-11 `Delayed Gratification + Joker Stencil + Campfire` 跨 ante 经济通关基线。

### 2026-06-11

- 日期（Date）：2026-06-11
- 决策（Decision）：AGENT1 实验中保护 `Blue Joker`/`Half Joker`；`Supernova` 应替换 `Scholar` 而不是 `Blue Joker`。Pair 训练必须避开 `The Arm` 的早期 Scholar/A 爆发，`The Wheel` 无对子时使用弃牌追 Pair。
- 背景（Context）：卖 Blue 的 Supernova/Photograph 分支明显退化；全局 Pair 改写在 `The Arm` 失败，而条件 Pair 训练和 Boss 专用弃牌把路线推进到 ante 8。
- 推理（Reasoning）：Blue 提供稳定筹码，Half/Supernova 提供 Mult，职责互补；Boss 专用条件比全局静态偏好更符合日志中的实际收益。
- 后果（Consequences）：后续实验不得静态卖 Blue；手牌策略变化必须带 ante/Boss/构筑条件，并单独记录早期生存和后期收益。
- 被取代于（Superseded by）：无

### 2026-06-11

- 日期（Date）：2026-06-11
- 决策（Decision）：把 `Delayed Gratification + Joker Stencil + Campfire` 设为 AGENT1 可复现的 fixed-seed 实验通关基线，但在动态预算和 regression/heldout 验证前不写入生产策略。
- 背景（Context）：旧 Supernova/Campfire 路线已能到 ante 8，但 Boss 后只剩少量现金；新路线通过 ante 2 保留 Delayed、维持 Stencil 空槽，并把 68/63 金现金下限跨 Boss 带入 ante 8，首次返回 `game_over_win`。
- 推理（Reasoning）：该路线直接解决了 Campfire 重置瓶颈，并已从全新 `MENU` 状态完整复现 264 步胜局；但固定现金阈值、单 seed 和 Amber Acorn 分数报告异常仍说明它是过拟合风险较高的研究候选。
- 后果（Consequences）：下一轮把固定金额改为动态预算，先单跑 AGENT1 保持胜局，再跑 regression/heldout；本轮不修改应用策略代码。
- 被取代于（Superseded by）：无

### 2026-06-13

- 日期（Date）：2026-06-13
- 决策（Decision）：`evolvedv8` 只作为 `dev` 局部 Pareto 候选，不晋升为稳健策略；后续进化比较必须显式保护 per-seed elite，并通过 regression/heldout 门禁。
- 背景（Context）：v7 到 v8 保持 AGENT1/2 并改善 AGENT3，但所有完整 `dev` 版本仍为 0 胜，AGENT2 长期停滞，且自动候选未保留已知 AGENT1 胜局和 AGENT2 ante 5 路线。
- 推理（Reasoning）：锯齿式局部改善符合早期启发式搜索现象，但不满足项目对通关稳定性和防遗忘的长期目标。只看 aggregate 或最高 ante 会掩盖单 seed 能力回退。
- 后果（Consequences）：下一轮应先定义并执行 per-seed 不退化、lost win 为零、错误数不增加的晋升约束，再运行 regression/heldout；未通过前不继续把 v8 规则视为稳定基线。
- 被取代于（Superseded by）：无

### 2026-06-14

- 日期（Date）：2026-06-14
- 决策（Decision）：采用 checkpoint beam、硬优先级 StateValue、per-seed Pareto archive 和 dev/regression/heldout 分层门禁作为下一版进化基础设施，但本轮不把任何新 genome 晋升为 v8 后继版本。
- 背景（Context）：save/load 与真实分支复现已通过 smoke，单元测试覆盖候选预算、horizon、根恢复、基因边界、交叉、Pareto 和逐 seed regression gate；完整默认搜索的 live 吞吐不足以在本轮完成三 seed dev 和 8×3 进化。
- 推理（Reasoning）：架构已解决 v8 只看 aggregate、丢失 per-seed 能力和 heldout 泄漏的问题；但硬验收要求的 dev 胜局、另外两个 seed 不回退和 regression 无新增错误尚无完整证据，不能只凭局部 rollout 或单元测试宣布晋升。
- 后果（Consequences）：后续先做搜索成本基准和场景库压缩，再完成 dev；只有 dev 至少 1 胜且其余 seed 不低于 v8，才运行 regression，冠军最后只报告 heldout。
- 被取代于（Superseded by）：无

### 2026-06-18

- 日期（Date）：2026-06-18
- 决策（Decision）：把“关键计分牌手牌重排”和“已有 X 倍率 Joker 时的小丑牌顺序整理”写入默认策略代码，但暂不扩大到所有无 X 倍率的 chip/mult Joker 构筑。
- 背景（Context）：用户指出自动 agent 没有调整出牌内部顺序，也没有把筹码 Joker、加倍率 Joker 和乘法倍率 Joker 放到合理位置；现有代码只有 `play` 参数排序，没有默认 `rearrange jokers` agent。
- 推理（Reasoning）：BalatroBot 一手文档确认 `rearrange` 接受当前索引的全量新顺序。手牌重排只在重触发增强牌或 `Photograph` 首张人头牌收益明确时触发，能直接对应用户指出的失败模式；小丑牌排序先要求已有 X 倍率 Joker，避免在 AGENT2 等无 X 倍率小牌型路线中把排序动作抢在已验证的买牌、重掷或离店策略前。
- 后果（Consequences）：后续应优先用 fixed seed live 对照验证排序收益；若确认无 X 倍率时 chip/mult 顺序也能稳定增益，再扩大 `JokerOrderAgent` 的触发范围。
- 被取代于（Superseded by）：无
