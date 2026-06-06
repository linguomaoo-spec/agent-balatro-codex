# 商店阶段策略记忆

## 范围

记录 `SHOP` 阶段的购买、重掷、跳过和资源保留策略。商店策略是长期提升通关率的
核心记忆区。

### 基线：优先买得起的小丑牌

- 适用局面：商店中出现可购买小丑牌，且没有更具体的协同规则。
- 决策规则：小丑牌优先级高于普通消耗牌和补充包；保留一定现金，避免因为过度消费影响后续回合。
- 证据来源：`balatro_agent/agents.py` 中 `ShopAgent.propose`；`tests/test_orchestrator.py` 覆盖可购买小丑牌优先于消耗牌。
- 失败案例：未区分弱小丑牌、重复收益、经济牌和过渡牌，可能买到低价值牌。
- 待验证问题：在不同 ante 和 stake 下，现金保留线应如何调整？

### 工作假设：重掷需要明确目标

- 适用局面：金钱高于保留线，当前商店没有明显收益。
- 决策规则：只有在需要关键小丑牌、关键补充包或经济充足时才重掷；否则优先进入下一回合。
- 证据来源：当前仅为策略假设；现有 `EconomyAgent` 只用简单现金阈值。
- 失败案例：连续重掷可能降低利息和购买力。
- 待验证问题：重掷成功带来的收益能否覆盖现金损失？

### 规则：早期避免低价值占槽牌，优先生存 Joker

- 适用局面：ante 1-3，Joker 槽位有限，当前构筑仍需要稳定过盲分数。
- 决策规则：`Credit Card`、`Red Card`、`Rocket`、`Hallucination`、纯经济 Joker 这类缺少直接得分收益或需要未实现配套计划的牌，不应仅因为便宜或文字里包含 mult/money 就填槽；`Ice Cream` 这类早期高筹码生存牌应优先于低收益占槽牌，槽满时可以卖出低价值牌腾槽。
- 证据来源：`runs/eval/live-20260601-last-hand-dev/AGENT3.jsonl` 中买入 `Credit Card` 后错过 `Ice Cream` 并在 ante 2 失败；`runs/eval/live-20260601-icecream-dev/AGENT3.jsonl` 显示显式升权 `Ice Cream` 后推进到 ante 5 的 10524/11000。2026-06-06 后续测试用 `tests/test_orchestrator.py` 固定 `Red Card` 不压过直接得分 Joker、`Rocket` 不压过行星牌/存钱；但 live 结果仍无通关，最终 AGENT1 25960/30000、AGENT2 3506/4000、AGENT3 17413/22000。
- 失败案例：`Ice Cream` 会递减并最终耗尽，不能当作长期倍率核心；AGENT3 最终仍在 ante 5 失败。
- 待验证问题：还应显式降权哪些占槽牌，显式升权哪些早期生存牌？

### 规则：中后期用 Banner/Gros Michel 替换 plain Joker

- 适用局面：ante 4+，Joker 槽已满，当前槽位里有 plain `Joker` 这类低成长倍率牌，商店出现 `Banner` 或 `Gros Michel`。
- 决策规则：允许卖出 plain `Joker` 腾槽购买 `Banner` 或 `Gros Michel`；`Banner` 在剩余弃牌较多时可视为强生存筹码来源。
- 证据来源：`runs/eval/live-20260606-agent3-banner-gros/AGENT3.jsonl` 在 ante 4 round 10 卖出 plain `Joker` 买入 `Banner`，最终推进到 ante 5 round 15 的 17928/22000；完整 `runs/eval/live-20260606-dev-banner-gros` 也复现该结果。
- 失败案例：仅靠该替换仍未通关；AGENT3 最终差 4072 分。
- 待验证问题：`Banner` 之后是否还应替换 `Mad Joker`、`Raised Fist` 或递减后的 `Ice Cream`，需要看累计价值和具体局面，不能只靠静态分数表。

### 反例：不要静态强推 Gros Michel 替换 Mad Joker

- 适用局面：已拥有 `Banner`、`Supernova`、`Mad Joker`、`Ice Cream` 和其他过渡 Joker，商店出现 `Gros Michel`。
- 决策规则：不要仅凭静态评分强制卖 `Mad Joker` 换 `Gros Michel`；应先判断已有 Joker 的累计收益、当前牌型偏好和后续商店路径。
- 证据来源：`runs/eval/live-20260606-agent3-gros-replace/AGENT3.jsonl` 中强推该假设后退化到 ante 4 round 11 的 6936/7500。
- 失败案例：该反例不代表 `Gros Michel` 总是低价值，只说明当前静态替换规则过粗。
- 待验证问题：如何估算 `Supernova`、`Mad Joker`、`Ride the Bus` 等累计或条件倍率 Joker 的当前真实价值？

### 反例：不要只因高现金和满槽就晚期重掷

- 适用局面：ante 4+，Joker 槽已满，现金较高，当前商店没有明显可买项。
- 决策规则：不要仅凭“钱多 + 无可买项”提高 reroll；必须有明确目标，例如可替换的弱 Joker、需要找 X 倍率、或当前构筑无法过下一盲且现金仍足够购买。
- 证据来源：2026-06-06 测试过晚期满槽高现金 reroll 加成后，`runs/eval/live-20260606-2320-shop-discipline-retry/AGENT3.jsonl` 和最终 `runs/eval/live-20260606-2332-shop-discipline-final-agent3/AGENT3.jsonl` 均为 17413/22000，低于 `runs/eval/live-20260606-dev-banner-gros/AGENT3.jsonl` 的 17928/22000；该规则已撤回。
- 失败案例：无目标重掷会消耗利息和购买力，还可能改变商店路径但没有补足倍率。
- 待验证问题：后续 reroll 是否应由“目标牌类别 + 最弱 Joker + 资金下限 + 当前分数缺口”共同触发？

### 待补充：补充包和优惠券选择

- 适用局面：商店出现补充包或优惠券。
- 决策规则：先记录每类补充包在当前 deck、stake、ante、已有小丑牌下的收益，再设定优先级。
- 证据来源：待从评估日志和具体失败案例补充。
- 失败案例：未知。
- 待验证问题：哪些补充包在早期最容易提高通关稳定性？
