# Agent 决策与记忆说明页设计

## 目标

创建 `research/agent-decision-memory-overview.html`，用一份离线可读、单文件的中文 HTML，准确说明当前小丑牌 agent：

1. 已经怎样取得可复现的 fixed-seed 胜局，以及该证据的边界；
2. 游戏状态如何被转换为候选动作、合法动作和实际执行动作；
3. 研究与策略记忆如何从日志中积累；
4. 这些记忆当前怎样影响策略，以及没有怎样影响策略。

页面面向任意读者；术语以准确和可审计优先，不假定读者阅读过代码。

## 事实与边界

- 已确认的胜局是 AGENT1、红牌组、白注上的 fixed-seed 路线。它两次返回 `GAME_OVER` / `won: true`；独立复现的前两盲为 55264/50000 与 83556/75000。来源：`research/findings.md`、`research/runs/2026-06-11.md`。
- 此胜局依赖 Delayed Gratification、保留 Joker Stencil 空槽、Campfire 与跨 Boss 现金保留。它是研究基线，而不是已泛化的生产策略。来源：`research/decisions.md`。
- 完整 dev cohort 和进化候选都尚无胜局，且没有 regression / heldout 晋升证据。页面必须明确禁止把 fixed-seed 复现表述为稳定通关。来源：`research/findings.md`、`research/memory.md`。
- Markdown 记忆不在 Python 运行时加载。当前作用路径是：人或研究 agent 读取日志与 Markdown，提出/实现启发式或 genome 调整，用测试和 cohort 评估验证。来源：`README.md`、`strategy/runs/README.md`，以及对 `balatro_agent/` 中 Markdown I/O 的代码搜索。

## 页面结构

1. **结论横幅**：一句话区分“已复现 fixed-seed 胜局”和“未验证稳定通关”，包含截至日期和证据标签。
2. **胜局路线**：以短时间线展示 Delayed、Stencil、Campfire 和跨 Boss 现金的作用；同时列出固定 seed、过拟合和终局字段的限制。
3. **运行时决策链**：使用 HTML/CSS 流程图展示 `gamestate → GameState → 五类 phase agents → ActionProposal → validate_action → 分数/置信度选择 → Runner → JSONL`。应标注每个节点的代码位置。
4. **可选 checkpoint beam**：独立展示存档、候选分支、rollout 和 `StateValue` 的字典序评估；说明存档失败会回退到普通启发式，且当前真实运行成本过高。
5. **记忆闭环**：展示“运行证据 → research/ 与 strategy/ 分层沉淀 → 人工/研究分析 → 代码或 genome 变更 → 单测与分层 cohort → 新日志”的闭环。
6. **记忆如何生效**：用对照卡片清晰区分“当前直接影响（已转入 Python / genome 的规则）”“间接影响（指导下一次实验）”“当前不具备（Markdown 自动检索或自动在线学习）”。
7. **证据索引与下一步**：列关键仓库文件、已知不确定性和当前评估门槛，不复制完整日志。

## 视觉与交互

- 采用深色牌桌和黄铜档案标签风格，避免使用外部字体、图片和网络请求。
- 使用系统字体回退、语义化标题、足够的前景对比、键盘可操作的折叠证据区，以及 `prefers-reduced-motion` 支持。
- 宽屏以关系图和双列卡片呈现；小屏退化为单列；提供打印样式。
- 仅加入用于折叠“证据/来源”的最小原生 JavaScript；没有数据请求、游戏控制或自动推论。

## 非目标

- 不改动 `balatro_agent/`、策略评分、genome 或测试逻辑。
- 不把研究假设伪装成稳定事实，不新增或重写现有研究结论。
- 不把这份说明页实现成 Markdown 检索器或运行时策略模块。

## 验收与验证

1. 页面可直接以本地文件打开，且无外部依赖。
2. 关键事实与上述来源、代码实现一致；特别是记忆的间接作用和 fixed-seed 证据边界。
3. HTML 通过结构检查，浏览器桌面/窄屏均可读，折叠交互可用。
4. 完整运行 `python3 -m unittest discover -s tests`，确认文档工作没有影响应用测试。
5. 只提交本任务生成的文档和本次所需研究运行记录，不包含已有的未提交工作区改动。
