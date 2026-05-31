# 研究问题

## 高优先级问题（High-Priority Questions）

- 自动运行应该跟踪哪些基线指标，例如胜率、到达 ante、金钱、小丑牌数量或分数差距？
- 真实 BalatroBot 结束局是否稳定返回 `won` 字段，并与本地 `game_over_win`、`game_over_loss` 契约一致？
- 当前 `dev`、`regression`、`heldout` seed 分组是否足够区分策略收益、旧能力退化和过拟合？
- 当前 baseline agent 的决策日志中有哪些常见失败模式？
- 在 round、hand、shop、booster 阶段，所有被选中的动作是否都合法，并正确映射到 BalatroBot 端点？
- 当前评估循环在固定 seed 上是否能产生可复现结果？
- 策略晋升门槛应使用哪些阈值，例如 regression 最高 ante 不下降、heldout 胜率不下降、错误动作数不增加或成本不过高？

## 中优先级问题（Medium-Priority Questions）

- 哪些手牌选择启发式最常错过更高分方案？
- 哪些商店决策对后续 ante 的负面影响最大？
- replay 经验库应保存哪些最小字段，才能让子 agent 在不读取全量日志的情况下复用成功/失败案例？
- replay 经验库应如何按阶段、ante、deck、stake、小丑牌标签、失败类型和相似动作做 top-k 检索？
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
