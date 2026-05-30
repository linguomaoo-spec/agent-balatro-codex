# 策略记忆索引

## 项目定位

本项目把 Balatro 统一称为小丑牌。策略记忆的目标是把局型、阶段、难度、
小丑牌协同和失败案例沉淀为 Markdown 文件，再由这些记忆驱动研究和决策。

## 阶段入口

- `phases/hand.md`：选择出牌、弃牌、保留手牌。
- `phases/shop.md`：购买小丑牌、优惠券、补充包、重掷和离店。
- `phases/blind.md`：选择盲注、跳过盲注、处理 Boss blind 风险。

## 主题入口

- `jokers/README.md`：小丑牌价值、协同和反例。
- `runs/README.md`：从运行日志提取策略记忆。
- `../research/questions.md`：仍需要调查或验证的问题。
- `../research/findings.md`：已经有来源支撑的观察。
- `../research/decisions.md`：会影响后续策略方向的决策。

## 当前优先级

1. 定义固定 seed 评估指标：胜率、最高 ante、失败阶段、金钱、小丑牌数量和错误动作。
2. 从决策日志中识别手牌和商店阶段的常见失败模式。
3. 把稳定失败模式转成 Markdown 策略，再决定是否转成 Python 规则。
4. 保持 Python 最小化，优先用 `scripts/*.sh` 编排评估和子 agent 任务。
