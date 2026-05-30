# 盲注阶段策略记忆

## 范围

记录选盲、跳盲和 Boss blind 风险处理。当前 baseline 默认选择盲注，尚未建立跳盲收益模型。

### 基线：默认选择盲注

- 适用局面：没有明确跳盲收益规则时。
- 决策规则：优先 `select`，保持流程稳定并收集可比较日志。
- 证据来源：`balatro_agent/agents.py` 中 `RoundAgent.propose`；`tests/test_runner.py` 覆盖 `BLIND_SELECT` 阶段执行 `select`。
- 失败案例：可能错过高价值跳盲奖励。
- 待验证问题：哪些跳盲奖励值得牺牲商店和回合收益？

### 待补充：Boss blind 应对

- 适用局面：进入 Boss blind 前或 Boss blind 生效时。
- 决策规则：记录 Boss blind 效果、当前小丑牌和手牌策略是否受影响，再决定是否调整购买或出牌优先级。
- 证据来源：待从本地日志、BalatroBot 状态字段和运行观察补充。
- 失败案例：未知。
- 待验证问题：BalatroBot 当前 gamestate 是否稳定暴露 Boss blind 名称和效果？
