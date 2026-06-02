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
