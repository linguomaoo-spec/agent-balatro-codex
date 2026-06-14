# 研究问题

## 高优先级问题（High-Priority Questions）

- 自动运行应该跟踪哪些基线指标，例如胜率、到达 ante、金钱、小丑牌数量或分数差距？
- 真实 BalatroBot 结束局是否稳定返回 `won` 字段，并与本地 `game_over_win`、`game_over_loss` 契约一致？
- `Runner.run` 是否应在检测到 `GAME_OVER` 时向 JSONL 写入终局记录，避免 `summarize-eval` 和 `build-replay` 把真实失败局误判为 `incomplete`？
- 当前 `dev`、`regression`、`heldout` seed 分组是否足够区分策略收益、旧能力退化和过拟合？
- 当前 baseline agent 的决策日志中有哪些常见失败模式？
- AGENT3 在 `runs/eval/live-20260606-dev-banner-gros/AGENT3.jsonl` 中 ante 5 round 15 以 17928/22000 失败时，主要瓶颈是稳定倍率、X 倍率来源、牌型等级、后期无效重掷，还是满槽 Joker 替换时机？
- 在修正 `The Psychic` 五张出牌和 `PLAY_TAROT` transient 后，AGENT3 是否能恢复到 ante 5+，并重新接近或超过 2026-06-01 的 10875/11000？
- AGENT2 为什么稳定卡在 ante 3 round 9 的 2908/4000，主要是小丑牌强度不足、出牌顺序不足，还是商店替换规则不足？
- AGENT2 在 ante 3 前把现金用于低等级星球牌后，是否错过了替换弱满槽小丑牌的机会？是否应在弱小丑牌满槽时提高现金保留和 reroll 优先级？
- AGENT2 在 `runs/eval/live-20260606-2320-shop-discipline-retry/AGENT2.jsonl` 中仍以 `j_clever`、`j_mystic_summit`、`j_sly`、`j_droll`、`j_zany` 满槽卡在 3506/4000；是否应在 ante 2 前降低牌型限定 chip Joker 的堆叠价值，或者优先保留现金找倍率/X 倍率 Joker？
- AGENT2 在 ante 2 round 3 同时看到 `Misprint` 和 `Mystic Summit` 时，是否应优先拿稳定/随机倍率来源 `Misprint`，而不是第三张牌型限定 chip Joker？这是否能越过 ante 3 的 4000 分关口？
- AGENT2 在早期条件 Joker 降权后已推进到 ante 4 `The Wall` 的 17865/20000；下一步应优先通过 Boss 前目标 reroll、保留 `Misprint`、避免买递减 `Popcorn`、还是更强手牌选择来补足 2135 分缺口？
- AGENT2 当前最佳小牌型路线已推进到 ante 5 `The Needle` 的 8930/11000；下一步应优先寻找一次性 X 倍率、Boss 前可控重掷目标、消耗牌/牌型等级，还是 The Needle 专用弃牌/出牌策略来补足约 2070 分？
- AGENT3 在 `runs/eval/live-20260606-2332-shop-discipline-final-agent3/AGENT3.jsonl` 中从 17928/22000 退到 17413/22000；主要差异是 reroll 路径、牌型选择、`Ice Cream` 消耗，还是 final boss `The House` 的首手信息隐藏影响？
- `Runner.run` 是否应把意外回到 `MENU` 的 active run 记录为基础设施失败，而不是继续 fallback 到 `max_steps`？
- `Runner.run` 是否应把 live 过程中的连续 `gamestate` 超时、`Remote end closed connection` 和 Lovely `shop nil` 崩溃记录为 `infra_error`，并终止该 seed 而不是让 eval 结果混入策略失败？
- `Runner.run` 或 live eval 是否应把 `cash_out` 后的 Lovely `round_eval nil` 崩溃记录为 `infra_error`，并保留崩溃前已过盲进度，避免误读为策略失败或成功？
- Runner 还应把哪些 BalatroBot phase 作为 transient 处理，例如使用消耗牌后的 `PLAY_TAROT` 之外是否还有 `OPENING_BOOSTER` 变体？
- 在 round、hand、shop、booster 阶段，所有被选中的动作是否都合法，并正确映射到 BalatroBot 端点？
- 当前评估循环在固定 seed 上是否能产生可复现结果？
- 策略晋升门槛应使用哪些阈值，例如 regression 最高 ante 不下降、heldout 胜率不下降、错误动作数不增加或成本不过高？
- AGENT1 的 Delayed/Stencil/Campfire fixed-seed winning route 已从全新游戏状态复现；它能否推广到 regression/heldout seed？固定 68/63 金阈值应如何改成动态预算？
- `AGENT1` 重复 live run 中 Lucky Card 是否会产生不可复现的 20 金波动；固定 seed 复现性是否还受动作顺序或上游随机状态影响？
- 当前进化选择是否应维护 per-seed elite/Pareto archive，避免 aggregate 改善掩盖 AGENT1/AGENT2 已知能力回退？
- `evolvedv8` 在 regression/heldout 上是否仍保持 v7 的 AGENT1 结果和 v8 的 AGENT3 改善，还是只拟合 `dev` 三个固定 seed？
- 默认 6/12 分支、4/6 步 checkpoint rollout 在单决策 35--85 秒的成本下，应该通过分支缓存、状态价值截断、动态预算还是多实例并行降低总评估时间？
- 动作已生效但 BalatroBot 关闭 HTTP 响应的频率是否随 checkpoint 压力增加；`transport_warning` 与真正执行失败应如何分别纳入 promotion gate？

## 中优先级问题（Medium-Priority Questions）

- 哪些手牌选择启发式最常错过更高分方案？
- 提高顺子/同花优先级是否能提升真实 run 的中后期得分，同时不降低前期通过率？
- 哪些商店决策对后续 ante 的负面影响最大？
- 哪些具体小丑牌应进入“成长型优先名单”，以及每张成长型小丑牌对应的最佳增强操作是什么？
- 早期商店中哪些低价值占槽 Joker 应显式降权，哪些生存型 Joker（例如 `Ice Cream`）应显式升权？
- replay 经验库应保存哪些最小字段，才能让子 agent 在不读取全量日志的情况下复用成功/失败案例？
- replay 经验库应如何按阶段、ante、deck、stake、小丑牌标签、失败类型和相似动作做 top-k 检索？
- 人类游玩状态日志应如何映射成可复用的 replay 案例，尤其是从连续状态变化中推断买牌、出牌、弃牌和跳盲意图？
- 如何比较多代 genome 权重，才能避免过拟合到很小的 seed 集？
- 当前使用的本地 BalatroBot schema 版本是什么，是否匹配仓库假设？

## 低优先级问题（Low-Priority Questions）

- 收集一手证据后，哪些二手 Balatro 策略资源值得持续关注？
- 哪些更丰富的分析视图能让决策日志更容易检查？
- 是否需要为策略迭代定义 Balatro 版 BWT/FWT/遗忘率指标，例如旧 seed 最高 ante 回退、旧阶段错误率上升或原有胜局丢失？
- 哪些策略部分最终应该使用搜索、rollout 模拟或学习到的价值估计？

## 已解决问题（Resolved Questions）

- 2026-05-30：`Runner.run` 与 `EvalResult.score` 的本地胜负状态契约已统一；`GAME_OVER` 且 `won == true` 记为 `game_over_win`，`won == false` 记为 `game_over_loss`，评分兼容旧的 `status: game_over` 加 `state.won: true` 日志。仍需真实 BalatroBot 运行验证安装版本行为。
- 2026-05-30：建立初始 seed cohort：`dev = AGENT1..AGENT3`，`regression = AGENT4..AGENT6`，`heldout = AGENT7..AGENT9`。这是工程起点，仍需真实评估后调整覆盖面。
- 2026-06-07：AGENT2 ante 3 的 4000 分关口已由早期条件 Joker 降权越过；后续瓶颈从弱 chip Joker 满槽转为 ante 4/5 的 Boss 得分爆发。
- 2026-06-07：AGENT2 `The Wall` 2135 分缺口已由小牌型核心路线部分解决：保留 `Sly`/`Scary Face`/`Half`，用 `Hanging Chad` 替换 `Supernova` 后可越过 `The Wall`；后续首要问题转为 `The Needle`。
- 2026-06-11：AGENT1 ante 5/6 的中期倍率瓶颈已由 Campfire + Supernova + 条件 Pair 训练路线越过；当前首要问题转为 ante 8 Boss 重置后的持久战力和经济。
- 2026-06-11：AGENT1 的 ante 8 Campfire 重置缺口已在一次 fixed-seed run 中由跨 ante 经济解决：保留 `Delayed Gratification`、维持 `Joker Stencil` 空槽，并保护现金到 ante 8 后，结果返回 `game_over_win`。后续问题转为复现、终局契约核对和跨 seed 泛化。
- 2026-06-11：AGENT1 的 Delayed/Stencil/Campfire 路线已从全新 `MENU` 状态完整复现；两次胜局均返回 `won: true` 和 17680/100000。fixed-seed 可复现性问题已解决，后续转为动态预算、跨 seed 泛化和终局分数字段语义。
