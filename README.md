# 小丑牌策略 Agent（Balatro Agent）

Balatro 在本项目中统一称为小丑牌。协议字段、包名、命令名、上游项目名和
BalatroBot 枚举值保留英文，方便和工具、日志、JSON-RPC schema 对齐。

本项目是小丑牌策略项目：目标是把不同局型、阶段、难度和失败案例沉淀成
可复用的 Markdown 记忆系统，再用这些记忆驱动自动化决策、研究分析和后续
策略实现。长期目标是在可重复评估的基础上逐步通关所有难度的小丑牌。

Python 代码只作为底层适配层：连接 BalatroBot、校验动作、执行动作、记录日志
和提供最小评估能力。策略知识优先沉淀在 `strategy/` 和 `research/` 的 Markdown
文件中；编排优先使用 `scripts/*.sh`，减少把流程逻辑继续写进 Python。

面向 Balatro 的 Python 多 agent 自动化层，用来驱动本地
[BalatroBot](https://github.com/coder/balatrobot) JSON-RPC 服务。
如果口语或草稿里写到 `baraltrobot`，本项目默认按 BalatroBot 理解；除非后续
确认它是另一个独立工具名。

项目沿用了 [BalatroLLM](https://github.com/coder/balatrollm) 中实用的职责拆分：
BalatroBot 负责访问游戏，本仓库负责策略、日志、评估和 genome 进化。

## 功能概览

- 读取 BalatroBot 的 `gamestate`。
- 按游戏阶段生成候选动作。
- 通过多个小型 agent 给候选动作打分。
- 执行分数最高且合法的 BalatroBot 动作。
- 将每次决策记录为 JSONL，便于回放和外部分析工具分析。
- 在固定 seed 上变异策略权重，做简单进化。

当前 agent：

- `RoundAgent`：自动 `cash_out`，并在默认情况下执行盲注 `select`。
- `HandAgent`：基于解析到的牌面点数提出基础出牌/弃牌方案。
- `ShopAgent`：提出小丑牌、优惠券、补充包、卡牌购买方案。
- `EconomyAgent`：控制 `next_round` 和重掷预算。
- `BoosterAgent`：兼容旧版 `pack` 端点的处理路径。

## 策略记忆系统

策略记忆位于 `strategy/`，研究记忆位于 `research/`。

- `strategy/index.md`：策略记忆总索引。
- `strategy/phases/`：按游戏阶段组织的决策规则，例如出牌、商店、选盲。
- `strategy/jokers/`：小丑牌协同、优先级、反例和待验证规则。
- `strategy/runs/`：从评估日志、失败 run 和子 agent 产出中提炼出的策略摘要。
- `research/`：长期项目记忆、来源、问题、发现、决策和研究运行日志。

策略文件应尽量使用固定结构：适用局面、决策规则、证据来源、失败案例、
待验证问题。没有日志、测试或上游资料支撑的判断只能作为工作假设，不能写成
稳定事实。

## 子 agent 与上下文隔离

主 agent 负责拆分任务、合并结论和更新长期记忆。子 agent 只处理窄任务，例如：

- 分析最近几个失败日志中的商店错误。
- 针对某个局型补充出牌或弃牌策略。
- 对比某次 genome 评估结果，提出下一轮待验证假设。

子 agent 的输入应只包含相关策略文件、研究问题、日志片段和明确产出格式，避免
把整个项目塞进上下文。`scripts/subagent-task.sh` 用来生成这种小任务包。

## 安装与检查

本仓库除 Python 3.9+ 外没有运行时依赖。

```bash
python3 -m unittest discover -s tests
```

可选的可编辑安装：

```bash
python3 -m pip install -e .
```

## BalatroBot 假设

BalatroBot 应在本机运行，并通过 HTTP 提供 JSON-RPC 服务，通常地址为：

```text
http://127.0.0.1:12346
```

当前公开的 BalatroBot OpenRPC schema 包含这些端点：
`gamestate`、`start`、`play`、`discard`、`buy`、`sell`、`reroll`、
`next_round`、`cash_out`、`select`、`skip`、`use`、`save`、`load`。牌组/赌注常量使用
`RED`、`WHITE` 等值。

## 常用命令

项目入口为 Python CLI（`python3 -m balatro_agent`），常用操作见下方命令。
保留 `scripts/` 中的脚本提供复杂工作流编排（录制、研究运行、子 agent 任务等）。

检查环境和 BalatroBot：

```bash
python3 -m unittest discover -s tests && python3 -m balatro_agent doctor
```

启动一局：

```bash
DECK=RED STAKE=WHITE sh scripts/start.sh
```

实际启动禁止传入 `SEED` 或 `start --seed`；固定 seed 仅用于下方的评估流程。

执行一次决策：

```bash
LOG_PATH=runs/decisions.jsonl sh scripts/step.sh
```

固定 seed 评估：

```bash
python3 -m balatro_agent --timeout 10 eval \
  --deck RED --stake WHITE \
  --seed-config config/eval-seeds.json --cohort dev \
  --max-steps 500 --log-dir runs/eval
```

汇总评估日志：

```bash
python3 -m balatro_agent summarize-eval --log-dir runs/eval
```

抽取 replay 经验案例：

```bash
LOG_DIR=runs/eval OUTPUT=strategy/runs/replay.jsonl sh scripts/build-replay.sh
```

比较 baseline 和候选评估摘要：

```bash
BASELINE=runs/baseline-summary.json CANDIDATE=runs/candidate-summary.json COHORT=regression \
  sh scripts/promotion-gate.sh
```

查询 replay 案例：

```bash
python3 -m balatro_agent replay-query --replay strategy/runs/replay.jsonl --phase SHOP --limit 5
```

查看固定 seed 分组：

```bash
python3 -m balatro_agent seed-cohorts --seed-config config/eval-seeds.json
```

生成子 agent 小任务包：

```bash
sh scripts/subagent-task.sh "分析最近失败日志里的商店决策"
```

检查 API：

```bash
python3 -m balatro_agent doctor
```

开始一局：

```bash
python3 -m balatro_agent start --deck RED --stake WHITE --seed AGENT1
```

执行一次决策：

```bash
python3 -m balatro_agent step --log runs/decisions.jsonl
```

运行自动循环：

```bash
python3 -m balatro_agent run --max-steps 500 --log runs/decisions.jsonl
```

启用 checkpoint beam 搜索：

```bash
python3 -m balatro_agent run --search --search-config config/search.json \
  --max-steps 500 --log runs/search-decisions.jsonl
```

记录人工游玩状态变化：

```bash
sh scripts/record-human-start.sh
# 玩完后停止
sh scripts/record-human-stop.sh
```

该 recorder 只读 BalatroBot 的 `gamestate`，默认只在状态变化时写入
`runs/human/live-YYYYMMDD-HHMMSS.jsonl`。它不记录系统键盘、鼠标或屏幕，
也不会执行任何游戏动作。前台运行可直接使用：

```bash
python3 -m balatro_agent record --output runs/human/manual.jsonl --interval 1
```

写入默认 genome：

```bash
python3 -m balatro_agent write-default-genome config/default-genome.json
```

评估一个 genome：

```bash
python3 -m balatro_agent --genome config/default-genome.json eval \
  --deck RED \
  --stake WHITE \
  --seed-config config/eval-seeds.json \
  --cohort dev \
  --max-steps 500 \
  --log-dir runs/eval
```

汇总 JSONL 评估日志：

```bash
python3 -m balatro_agent summarize-eval --log-dir runs/eval
```

从 JSONL 评估日志抽取 replay 案例：

```bash
python3 -m balatro_agent build-replay \
  --log-dir runs/eval \
  --output strategy/runs/replay.jsonl
```

运行分层 checkpoint 进化：

```bash
python3 -m balatro_agent --genome config/default-genome.json evolve \
  --deck RED \
  --stake WHITE \
  --search \
  --seed-config config/eval-seeds.json \
  --generations 3 \
  --population 8 \
  --output-dir runs/evolution
```

该流程先用 baseline dev run 收集最多 18 个分类 checkpoint 场景，每代前 3 名
进入完整 dev，最终前 2 名进入 regression，冠军才运行 heldout。输出目录包含
`elite_archive.json`、`fitness.json`、`regression-gate.json`、`heldout.json` 和场景 manifest。

基于历史决策日志进行不连接 BalatroBot 的模拟进化：

```bash
python3 -m balatro_agent evolve \
  --sim --sim-log-dir runs/eval \
  --seed-config config/eval-seeds.json \
  --generations 3 --population 8 \
  --output-dir runs/sim-evolution
```

`--sim-log-dir` 必须包含 `SELECTING_HAND` 状态的 JSONL 日志。要让已保存的 per-seed
elite 先验参与真实运行，可传入 `--elite-archive PATH`；直接运行时还须以
`run --seed SEED` 指定当前 seed。

## 无人审核自动进化

`auto-evolve` 在当前分支执行单轮“修改 → 测试 → `dev`/`regression`/`heldout` 评估 → 自动提交或回滚”。变更命令可修改任意文件；`dev` 必须提升，且三个 cohort 都不能退化，才会产生提交。开始前，已跟踪文件必须没有未提交改动。

```bash
python3 -m balatro_agent auto-evolve \
  --mutator-command 'claude -p "改进小丑牌策略；直接修改仓库文件"' \
  --evaluator scripts/auto-evolve-evaluate.sh
```

评估器接收 `COHORT LOG_DIR` 两个参数。默认脚本支持 `BALATROBOT_URL`、`BALATROBOT_TIMEOUT`、`DECK`、`STAKE`、`SEED_CONFIG` 和 `MAX_STEPS` 环境变量。失败候选会恢复到本轮开始的提交；评估产物保留在 `runs/auto-evolve/`。

## 决策日志

日志中每一行都是一个 JSON 记录，包含：

- 状态摘要
- 被选中的动作
- 实际执行的动作
- 合法候选动作
- 被拒绝候选动作及其校验原因
- 可选的 BalatroBot 错误详情

这是主要反馈循环：使用任意合适的分析工具或模型检查失败 run，调整 agent 打分或 genome 权重，然后重新运行 eval。例如，可使用 Claude Code 或本地脚本。

人工游玩 recorder 的 JSONL 每一行是 `human_state_snapshot`，包含时间戳、
状态摘要、状态哈希和可选的原始 BalatroBot 状态。它用于复盘人类操作造成的
状态变化；如果需要精确到点击或按键，需要后续接入显式授权的窗口级录制或
Balatro mod 事件日志。

## 说明

当前项目是基础自动化框架，还不是强 Balatro 求解器。重要的第一个里程碑是稳定、可检查的控制流程。等日志可信后，可以用更强的规则、Monte Carlo rollout 或学习到的价值估计升级手牌评估器和商店打分器。
