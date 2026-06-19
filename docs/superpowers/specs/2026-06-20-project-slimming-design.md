# 项目瘦身设计

日期：2026-06-20
目标：在保持功能完整的前提下，大幅精简仓库规模，提升代码可维护性和迭代速度。

## 背景

项目当前总计 ~40MB，包含：
- 核心 Python 代码 5,861 行（`agents.py` 单文件 2,513 行）
- 测试代码 4,621 行
- 162 个评估运行目录（28MB）
- 12 个 Shell 脚本
- 12MB 输出资产（PPT 演示文稿）
- 830 行研究文档
- 各种临时产物（`.superpowers/`, `package.json`, `.DS_Store`）

痛点：代码过于集中导致难以修改、历史运行目录干扰视线、薄封装脚本多余、测试膨胀。

## 1. agents.py 拆分为 agents/ 包

### 目标
将 2,513 行的单体文件拆分为职责清晰的模块，每个文件 < 500 行（`hand.py` 除外，~1200 行）。

### 拆分方案

```
balatro_agent/agents/
├── __init__.py          # 重新导出 Agent, default_agents()
├── base.py              # Agent 基类
├── constants.py         # 共享常量（_CHIP_JOKERS, _XMULT_JOKERS, _MULT_JOKERS, _BOSS_* 等）
├── utils.py             # 共享纯函数（_is_flush, _is_straight, _longest_run, _rank_chip_value 等）
├── round.py             # RoundAgent — blind 选择
├── booster.py           # BoosterAgent — booster pack 打开
├── consumable.py        # ConsumableAgent — 塔罗/星球/光谱牌使用
├── hand.py              # HandAgent — 出牌选择、弃牌计划、算分（最复杂）
├── joker_order.py       # JokerOrderAgent — 小丑牌排序
├── shop.py              # ShopAgent — 商店购买/卖出决策
└── economy.py           # EconomyAgent — 现金管理
```

### 接口兼容
- 唯一外部消费者 `orchestrator.py` 依赖 `Agent` 和 `default_agents()`
- `__init__.py` 重新导出这两个符号，外部 import 路径不变
- `default_agents()` 从各模块组装 agent 列表

## 2. 文件清理

### 直接删除

注意：`outputs/`、`.superpowers/`、`.DS_Store` 已在 `.gitignore` 中，这些是本地文件系统清理。

| 路径 | 原因 |
|------|------|
| `runs/eval/` 中除最近 5 个以外的所有目录（~157 个） | 迭代遗留，无重放价值 |
| `outputs/` | PPT 资产，不属于求解器（已在 .gitignore） |
| `package.json` | Python 项目不需要 Node 配置，需确认无实际用途 |
| `.superpowers/` | 临时 brainstorm 产物（已在 .gitignore） |
| `.DS_Store` | macOS 系统文件（已在 .gitignore） |

### 需同步更新的引用
- `README.md` 中的 `scripts/doctor.sh`、`scripts/eval.sh`、`scripts/summarize-eval.sh`、`scripts/seed-cohorts.sh` 引用 → 替换为对应的 `python3 -m balatro_agent` 命令
- `research/` 目录中对该等脚本的引用属于历史记录，保持不动

### 保留不动
- `config/` — 轻量配置文件
- `examples/` — 状态快照 JSON
- `strategy/` — 策略文档
- `research/` — 研究文档（后续单独精简）

### 预期效果
仓库从 ~40MB 降到 ~3MB。

## 3. Shell 脚本合并

原则：核心逻辑只是一行 Python 调用的脚本，直接删除（功能已由 `cli.py` 覆盖）。

### 删除（4 个）
- `eval.sh` → `python3 -m balatro_agent eval` 已支持
- `doctor.sh` → `python3 -m balatro_agent doctor` 已支持
- `summarize-eval.sh` → `python3 -m balatro_agent summarize-eval` 已支持
- `seed-cohorts.sh` → 一行 Python 调用，无包装价值

### 保留（8 个）
- `start.sh` — 启动游戏
- `step.sh` — 交互式单步调试
- `record-human-start.sh` / `record-human-stop.sh` — 录制功能
- `research-run.sh` — 研究工作流
- `promotion-gate.sh` — 评估门禁
- `build-replay.sh` — 构建
- `subagent-task.sh` — 子代理任务

## 4. 测试重组

### 精简 test_orchestrator.py
- 当前 2,259 行，测试的 orchestrator.py 仅 74 行
- 删除重复测试（同场景多 seed 重复）
- 删除对 agent 内部逻辑的穷举验证
- 保留端到端流程、状态管理、错误恢复测试
- 目标：~300 行

### 新增测试
- 新建 `test_agents/` 目录（或 `test_hand.py`, `test_shop.py` 等），为拆分后的各 agent 补充轻量单元测试，验证关键决策点

### 不动
- 其余测试文件行数合理，暂不调整

## 5. 研究文档精简（轻量）

- `findings.md`（451 行）：去重合并，移除已被后续运行否定的过时发现
- `research/memory.md`、`decisions.md`、`questions.md`：保持，它们是当前项目状态的关键记录

## 实施顺序

1. 本地文件清理（`outputs/`, `.superpowers/`, `.DS_Store`）
2. 删除 4 个薄封装脚本
3. 更新 `README.md` 中的脚本引用 → Python CLI 命令
4. 删除 `package.json`（确认无用途后）
5. 清理 `runs/eval/` 旧目录，保留最近 5 个
6. 拆分 `agents.py` → `agents/` 包，运行测试确认无回归
7. 精简 `test_orchestrator.py`，新增 agent 单元测试
8. 研究文档去重（`findings.md`）
9. Commit
