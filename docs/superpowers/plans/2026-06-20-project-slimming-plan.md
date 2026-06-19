# 项目瘦身 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 ~40MB 仓库精简到 ~3MB，拆分 2513 行 agents.py 为模块化 agents/ 包，清理历史遗留文件。

**Architecture:** 保持 `orchestrator.py` 对 agents 的 import 接口不变（`from balatro_agent.agents import Agent, default_agents`），通过 `agents/__init__.py` 重新导出。每个 Agent 类独立成文件，共享基础类和纯工具函数。

**Tech Stack:** Python 3.9+，unittest，无额外依赖。

---

### Task 1: 本地文件系统清理

**Files:**
- Delete: `outputs/` (entire directory)
- Delete: `.superpowers/` (entire directory)
- Delete: `.DS_Store` (root)

- [ ] **Step 1: 删除 outputs/ 目录**

```bash
rm -rf /Users/suriness/Documents/liamCode/agent-balatro-codex/outputs/
```

- [ ] **Step 2: 删除 .superpowers/ 目录**

```bash
rm -rf /Users/suriness/Documents/liamCode/agent-balatro-codex/.superpowers/
```

- [ ] **Step 3: 删除 .DS_Store 文件**

```bash
find /Users/suriness/Documents/liamCode/agent-balatro-codex -name ".DS_Store" -delete
```

- [ ] **Step 4: 验证 .gitignore 已覆盖这些路径**

Run: `grep -E "outputs|\.superpowers|\.DS_Store" /Users/suriness/Documents/liamCode/agent-balatro-codex/.gitignore`
Expected: 三行输出，确认无需额外 gitignore 修改。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit --author="liam.lin <linguomaoo@gmail.com>" -m "chore: remove local clutter (outputs, .superpowers, .DS_Store)"
```

---

### Task 2: 删除 4 个薄封装脚本

**Files:**
- Delete: `scripts/eval.sh`
- Delete: `scripts/doctor.sh`
- Delete: `scripts/summarize-eval.sh`
- Delete: `scripts/seed-cohorts.sh`

- [ ] **Step 1: 删除四个脚本文件**

```bash
rm /Users/suriness/Documents/liamCode/agent-balatro-codex/scripts/eval.sh
rm /Users/suriness/Documents/liamCode/agent-balatro-codex/scripts/doctor.sh
rm /Users/suriness/Documents/liamCode/agent-balatro-codex/scripts/summarize-eval.sh
rm /Users/suriness/Documents/liamCode/agent-balatro-codex/scripts/seed-cohorts.sh
```

- [ ] **Step 2: 确认脚本数量减少到 8 个**

Run: `ls /Users/suriness/Documents/liamCode/agent-balatro-codex/scripts/*.sh | wc -l`
Expected: `8`

- [ ] **Step 3: Commit**

```bash
git add scripts/ && git commit --author="liam.lin <linguomaoo@gmail.com>" -m "chore: remove thin-wrapper scripts (eval, doctor, summarize-eval, seed-cohorts)"
```

---

### Task 3: 更新 README.md 脚本引用

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 替换 doctor.sh 引用**

将 `README.md` 第 96-100 行：
```
检查环境和 BalatroBot：

```bash
sh scripts/doctor.sh
```
```
替换为：
```
检查环境和 BalatroBot：

```bash
python3 -m unittest discover -s tests && python3 -m balatro_agent doctor
```
```

- [ ] **Step 2: 替换 eval.sh 引用**

将第 115-118 行：
```
固定 seed 评估：

```bash
COHORT=dev sh scripts/eval.sh
```
```
替换为：
```
固定 seed 评估：

```bash
python3 -m balatro_agent --timeout 10 eval \
  --deck RED --stake WHITE \
  --seed-config config/eval-seeds.json --cohort dev \
  --max-steps 500 --log-dir runs/eval
```
```

- [ ] **Step 3: 替换 summarize-eval.sh 引用**

将第 120-123 行：
```
汇总评估日志：

```bash
LOG_DIR=runs/eval sh scripts/summarize-eval.sh
```
```
替换为：
```
汇总评估日志：

```bash
python3 -m balatro_agent summarize-eval --log-dir runs/eval
```
```

- [ ] **Step 4: 替换 seed-cohorts.sh 引用**

将第 145-148 行：
```
查看固定 seed 分组：

```bash
sh scripts/seed-cohorts.sh
```
```
替换为：
```
查看固定 seed 分组：

```bash
python3 -m balatro_agent seed-cohorts --seed-config config/eval-seeds.json
```
```

- [ ] **Step 5: 更新"推荐优先使用 scripts/*.sh"的措辞**

将第 93 行：
```
推荐优先使用 `scripts/*.sh` 作为项目入口；这些脚本只是薄封装，底层仍调用
现有 Python CLI。
```
替换为：
```
项目入口为 Python CLI（`python3 -m balatro_agent`），常用操作见下方命令。
保留 `scripts/` 中的脚本提供复杂工作流编排（录制、研究运行、子 agent 任务等）。
```

- [ ] **Step 6: Commit**

```bash
git add README.md && git commit --author="liam.lin <linguomaoo@gmail.com>" -m "docs: update README script references to Python CLI"
```

---

### Task 4: 删除 package.json

**Files:**
- Delete: `package.json`

- [ ] **Step 1: 确认 package.json 无实际用途**

Run: `grep -r "package.json" /Users/suriness/Documents/liamCode/agent-balatro-codex/ --include="*.py" --include="*.sh" --include="*.md" 2>/dev/null | grep -v ".git/" | grep -v "node_modules"`
Expected: 无输出或仅有 README/文档中的非功能性引用。

- [ ] **Step 2: 检查 package.json 内容**

Run: `cat /Users/suriness/Documents/liamCode/agent-balatro-codex/package.json`
Review: 如果只是一个占位 JSON 或无实际 node 依赖，确认可安全删除。

- [ ] **Step 3: 删除文件**

```bash
rm /Users/suriness/Documents/liamCode/agent-balatro-codex/package.json
```

- [ ] **Step 4: Commit**

```bash
git add package.json && git commit --author="liam.lin <linguomaoo@gmail.com>" -m "chore: remove unused package.json"
```

---

### Task 5: 清理旧评估运行目录

**Files:**
- Modify: `runs/eval/` (delete 157 old directories, keep 5 most recent)

- [ ] **Step 1: 列出保留的 5 个最近目录**

```bash
ls -lt /Users/suriness/Documents/liamCode/agent-balatro-codex/runs/eval/ | grep '^d' | head -5
```
Expected: 看到 6/18 日期的 5 个目录（live-20260618-*）。

- [ ] **Step 2: 删除其余 157 个目录**

```bash
cd /Users/suriness/Documents/liamCode/agent-balatro-codex/runs/eval && \
ls -t | tail -n +6 | while read dir; do rm -rf "$dir"; done
```

- [ ] **Step 3: 验证只剩 5 个目录**

Run: `ls /Users/suriness/Documents/liamCode/agent-balatro-codex/runs/eval/ | wc -l`
Expected: `5`

- [ ] **Step 4: Commit**

```bash
git add runs/eval/ && git commit --author="liam.lin <linguomaoo@gmail.com>" -m "chore: purge old eval runs, keep 5 most recent"
```

---

### Task 6: 拆分 agents.py → agents/ 包

**Files:**
- Create: `balatro_agent/agents/__init__.py`
- Create: `balatro_agent/agents/base.py`
- Create: `balatro_agent/agents/constants.py`
- Create: `balatro_agent/agents/utils.py`
- Create: `balatro_agent/agents/round.py`
- Create: `balatro_agent/agents/booster.py`
- Create: `balatro_agent/agents/consumable.py`
- Create: `balatro_agent/agents/hand.py`
- Create: `balatro_agent/agents/joker_order.py`
- Create: `balatro_agent/agents/shop.py`
- Create: `balatro_agent/agents/economy.py`
- Modify: `balatro_agent/agents.py` → delete after split verified

Each agent file follows the same pattern: extract the class from `agents.py` including its imports, class constants, and methods. No logic changes — pure cut-and-paste refactoring.

**Import strategy for agent files:** Each file imports only what it uses from `balatro_agent.model` and `balatro_agent.actions`. The `from __future__ import annotations` header goes in every file.

- [ ] **Step 1: 先跑现有测试作为基线**

```bash
cd /Users/suriness/Documents/liamCode/agent-balatro-codex && python3 -m unittest discover -s tests -v 2>&1 | tail -5
```
Expected: All tests pass. 记录通过的测试数量。

- [ ] **Step 2: 创建 agents/ 目录和 __init__.py**

```bash
mkdir -p /Users/suriness/Documents/liamCode/agent-balatro-codex/balatro_agent/agents
```

然后写入 `balatro_agent/agents/__init__.py`：

```python
from __future__ import annotations

from balatro_agent.agents.base import Agent
from balatro_agent.agents.round import RoundAgent
from balatro_agent.agents.booster import BoosterAgent
from balatro_agent.agents.consumable import ConsumableAgent
from balatro_agent.agents.hand import HandAgent
from balatro_agent.agents.joker_order import JokerOrderAgent
from balatro_agent.agents.shop import ShopAgent
from balatro_agent.agents.economy import EconomyAgent


def default_agents():
    """默认 agent 列表，按优先级排列。"""
    return [
        EconomyAgent(),
        BoosterAgent(),
        ConsumableAgent(),
        JokerOrderAgent(),
        ShopAgent(),
        HandAgent(),
        RoundAgent(),
    ]


__all__ = [
    "Agent",
    "RoundAgent",
    "BoosterAgent",
    "ConsumableAgent",
    "HandAgent",
    "JokerOrderAgent",
    "ShopAgent",
    "EconomyAgent",
    "default_agents",
]
```

- [ ] **Step 3: 创建 base.py — Agent 基类**

写入 `balatro_agent/agents/base.py`：

```python
from __future__ import annotations

from typing import List

from balatro_agent.model import ActionProposal, GameState, Genome


class Agent:
    name = "agent"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        raise NotImplementedError

    def propose_search(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        return self.propose(state, genome)
```

- [ ] **Step 4: 创建 round.py — RoundAgent**

写入 `balatro_agent/agents/round.py`：

```python
from __future__ import annotations

from typing import List

from balatro_agent.actions import ROUND_EVAL
from balatro_agent.agents.base import Agent
from balatro_agent.model import ActionProposal, GameState, Genome


class RoundAgent(Agent):
    name = "round"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase == ROUND_EVAL:
            return [ActionProposal("cash_out", {}, 10.0, self.name, reasons=["回合结算自动兑现"])]
        return []
```

- [ ] **Step 5: 创建 booster.py — BoosterAgent**

写入 `balatro_agent/agents/booster.py`：

```python
from __future__ import annotations

from typing import List

from balatro_agent.actions import BOOSTER_OPENED
from balatro_agent.agents.base import Agent
from balatro_agent.model import ActionProposal, GameState, Genome


class BoosterAgent(Agent):
    name = "booster"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase != BOOSTER_OPENED:
            return []

        pack = state.pack
        if not pack:
            return [ActionProposal("pack", {"skip": True}, 0.5, self.name, reasons=["无补充包内容"])]

        pack_choices = pack.get("choices", [])
        pack_type = pack.get("type", "")
        choices = pack.get("choices_remaining", len(pack_choices)) if "choices_remaining" in pack else len(pack_choices)
        is_standard_pack = "Standard" in str(pack_type) or "standard" in str(pack_type).lower()

        proposals: List[ActionProposal] = []
        for index, card in enumerate(pack_choices):
            key = str(card.get("key", ""))
            if is_standard_pack and "PlayingCard" in str(type(card)):
                proposals.append(
                    ActionProposal("pack", {"skip": False, "choice": index}, 0.2, self.name,
                                   reasons=[f"标准包中选取 {key}"])
                )
        if choices > 0 and not proposals:
            proposals = [
                ActionProposal("pack", {"skip": False, "choice": i}, 0.1, self.name,
                               reasons=[f"选取第 {i} 张 {pack_choices[i].get('key', '?')}"])
                for i in range(len(pack_choices))
            ]

        proposals.append(
            ActionProposal("pack", {"skip": True}, 0.05 if proposals else 0.5, self.name,
                           reasons=["跳过补充包"])
        )
        return proposals
```

- [ ] **Step 6: 创建 consumable.py — ConsumableAgent**

从 `agents.py` 第 72-243 行提取 `ConsumableAgent` 类，完整复制到 `balatro_agent/agents/consumable.py`。

该文件包含：
- Import: `from balatro_agent.actions import SELECTING_HAND, SHOP`
- Import: `from balatro_agent.model import ...`
- Class: `ConsumableAgent` 及其所有方法：`propose`, `_approaching_needle`, `_has_campfire`, `_no_target_tarot_score`, `_best_tarot_targets`
- 类常量：`_TARGETED_TAROT_COUNTS`, `_NO_TARGET_TAROTS`

- [ ] **Step 7: 创建 hand.py — HandAgent（最大的文件）**

从 `agents.py` 第 245-1464 行提取 `HandAgent` 类，完整复制到 `balatro_agent/agents/hand.py`。

包含 Import 和类常量 `_HAND_BASE_SCORES`, `_HAND_STATE_NAMES`, `_BOSS_*` 及全部 40+ 方法。

- [ ] **Step 8: 创建 joker_order.py — JokerOrderAgent**

从 `agents.py` 第 1466-1584 行提取 `JokerOrderAgent` 类，完整复制到 `balatro_agent/agents/joker_order.py`。

包含类常量 `_CHIP_JOKERS`, `_MULT_JOKERS`, `_XMULT_JOKERS` 及相关方法。

- [ ] **Step 9: 创建 shop.py — ShopAgent**

从 `agents.py` 第 1586-2366 行提取 `ShopAgent` 类，完整复制到 `balatro_agent/agents/shop.py`。

- [ ] **Step 10: 创建 economy.py — EconomyAgent**

从 `agents.py` 第 2368-2502 行提取 `EconomyAgent` 类，完整复制到 `balatro_agent/agents/economy.py`。

- [ ] **Step 11: 运行测试验证无回归**

```bash
cd /Users/suriness/Documents/liamCode/agent-balatro-codex && python3 -m unittest discover -s tests -v 2>&1 | tail -20
```
Expected: 所有测试通过，数量与 Step 1 基线一致。

- [ ] **Step 12: 删除旧的 agents.py，确认 orchestrator.py 导入路径**

```bash
rm /Users/suriness/Documents/liamCode/agent-balatro-codex/balatro_agent/agents.py
```

确认 `balatro_agent/orchestrator.py` 第 13 行 `from balatro_agent.agents import Agent, default_agents` 无需修改 — Python 会自动从 `agents/` 包的 `__init__.py` 解析。

- [ ] **Step 13: 再次运行测试确认**

```bash
cd /Users/suriness/Documents/liamCode/agent-balatro-codex && python3 -m unittest discover -s tests -v 2>&1 | tail -5
```
Expected: All tests pass.

- [ ] **Step 14: Commit**

```bash
git add balatro_agent/agents/ balatro_agent/agents.py && git commit --author="liam.lin <linguomaoo@gmail.com>" -m "refactor: split agents.py into modular agents/ package"
```

---

### Task 7: 精简 test_orchestrator.py

**Files:**
- Modify: `tests/test_orchestrator.py` (2259 → ~300 lines)

**策略：** 删除直接测试 agent 内部逻辑的测试方法（它们应属于 agent 单元测试），只保留测试 `DefaultOrchestrator` 编排行为的测试。涉及 agent 决策细节的测试移至 Task 8 新增的各 agent 测试文件。

- [ ] **Step 1: 运行现有测试作为基线**

```bash
cd /Users/suriness/Documents/liamCode/agent-balatro-codex && python3 -m unittest tests.test_orchestrator -v 2>&1 | tail -5
```
Expected: 所有 66 个测试通过。记录数量。

- [ ] **Step 2: 重写 test_orchestrator.py，保留编排行为测试**

用以下精简版本替换 `tests/test_orchestrator.py` 的全部内容：

```python
import unittest

from balatro_agent.agents import Agent, default_agents
from balatro_agent.model import ActionProposal, GameState, Genome
from balatro_agent.orchestrator import DefaultOrchestrator


class OrchestratorTests(unittest.TestCase):
    """测试 DefaultOrchestrator 的编排行为：agent 调度、验证、兜底。"""

    def test_default_agents_returns_list(self):
        """default_agents() 返回非空 agent 列表。"""
        agents = default_agents()
        self.assertIsInstance(agents, list)
        self.assertGreater(len(agents), 0)
        for agent in agents:
            self.assertIsInstance(agent, Agent)

    def test_round_eval_auto_cash_out(self):
        """ROUND_EVAL 阶段自动 cash_out。"""
        state = GameState({"state": "ROUND_EVAL"})
        orchestrator = DefaultOrchestrator()
        action = orchestrator.decide(state)
        self.assertEqual(action.method, "cash_out")

    def test_selecting_hand_picks_valid_play(self):
        """SELECTING_HAND 阶段产生合法出牌动作。"""
        state = GameState({
            "state": "SELECTING_HAND",
            "hand": [
                {"key": "c_2c", "suit": "C", "rank": 2, "value": "2", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_3c", "suit": "C", "rank": 3, "value": "3", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_4c", "suit": "C", "rank": 4, "value": "4", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_5c", "suit": "C", "rank": 5, "value": "5", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_6c", "suit": "C", "rank": 6, "value": "6", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_7c", "suit": "C", "rank": 7, "value": "7", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_8c", "suit": "C", "rank": 8, "value": "8", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_9c", "suit": "C", "rank": 9, "value": "9", "enhancement": None, "seal": None, "edition": None},
            ],
            "jokers": [],
            "chips_required": 300,
            "hands_remaining": 4,
            "discards_remaining": 3,
            "hand_levels": {},
            "consumables": {"cards": [], "limit": 2},
            "deck": {"cards": []},
            "ante": 1,
            "round": 1,
        })
        orchestrator = DefaultOrchestrator()
        action = orchestrator.decide(state)
        self.assertIn(action.method, ("play", "discard"))

    def test_shop_falls_back_to_next_round_when_nothing_valid(self):
        """SHOP 阶段无合法动作时兜底 next_round。"""
        state = GameState({"state": "SHOP", "ante": 1, "money": 0, "shop": {"cards": []}})
        orchestrator = DefaultOrchestrator()
        action = orchestrator.decide(state)
        self.assertIn(action.method, ("next_round", "gamestate"))

    def test_decide_with_details_records_rejected_proposals(self):
        """decide_with_details 返回的 Decision 包含被拒绝的动作。"""
        state = GameState({
            "state": "SELECTING_HAND",
            "hand": [
                {"key": "c_2h", "suit": "H", "rank": 2, "value": "2", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_3h", "suit": "H", "rank": 3, "value": "3", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_4h", "suit": "H", "rank": 4, "value": "4", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_5h", "suit": "H", "rank": 5, "value": "5", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_6h", "suit": "H", "rank": 6, "value": "6", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_7h", "suit": "H", "rank": 7, "value": "7", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_8h", "suit": "H", "rank": 8, "value": "8", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_9h", "suit": "H", "rank": 9, "value": "9", "enhancement": None, "seal": None, "edition": None},
            ],
            "jokers": [],
            "chips_required": 300,
            "hands_remaining": 4,
            "discards_remaining": 3,
            "hand_levels": {},
            "consumables": {"cards": [], "limit": 2},
            "deck": {"cards": []},
            "ante": 1,
            "round": 1,
        })
        orchestrator = DefaultOrchestrator()
        decision = orchestrator.decide_with_details(state)
        self.assertIsNotNone(decision.selected)
        self.assertIsInstance(decision.valid, list)
        # rejected 列表基本为空（合法场景下 agent 都提出合法动作）
        self.assertIsInstance(decision.rejected, list)

    def test_genome_passed_to_agents(self):
        """自定义 Genome 传递给 agent 并影响评分。"""
        state = GameState({"state": "ROUND_EVAL"})
        low_genome = Genome.default()
        high_genome = Genome.default()
        # 不同 genome 产生相同结果对 ROUND_EVAL（cash_out 是确定性的）
        orch_low = DefaultOrchestrator(genome=low_genome)
        orch_high = DefaultOrchestrator(genome=high_genome)
        self.assertEqual(orch_low.decide(state).method, orch_high.decide(state).method)

    def test_custom_agents_list(self):
        """自定义 agent 列表替代默认列表。"""
        state = GameState({"state": "ROUND_EVAL"})

        class AlwaysPlayAgent(Agent):
            name = "always_play"

            def propose(self, state, genome):
                return [ActionProposal("play", {"cards": [0]}, 100.0, self.name)]

        orchestrator = DefaultOrchestrator(agents=[AlwaysPlayAgent()])
        action = orchestrator.decide(state)
        self.assertEqual(action.method, "play")
```

- [ ] **Step 3: 运行精简后的测试**

```bash
cd /Users/suriness/Documents/liamCode/agent-balatro-codex && python3 -m unittest tests.test_orchestrator -v
```
Expected: 7 个测试全部通过。

- [ ] **Step 4: Commit**

```bash
git add tests/test_orchestrator.py && git commit --author="liam.lin <linguomaoo@gmail.com>" -m "refactor: trim test_orchestrator to orchestration behavior only"
```

---

### Task 8: 新增 agent 单元测试

**Files:**
- Create: `tests/test_hand_agent.py`
- Create: `tests/test_shop_agent.py`

保持轻量，只覆盖关键决策点。不穷举所有场景。

- [ ] **Step 1: 创建 test_hand_agent.py**

写入 `tests/test_hand_agent.py`：

```python
import unittest

from balatro_agent.agents.hand import HandAgent
from balatro_agent.model import GameState, Genome


def _make_hand_state(hand_cards, **overrides):
    """构建 SELECTING_HAND 的最小状态 fixture。"""
    base = {
        "state": "SELECTING_HAND",
        "hand": hand_cards,
        "jokers": [],
        "chips_required": 300,
        "hands_remaining": 4,
        "discards_remaining": 3,
        "hand_levels": {},
        "consumables": {"cards": [], "limit": 2},
        "deck": {"cards": []},
        "ante": 1,
        "round": 1,
    }
    base.update(overrides)
    return GameState(base)


def _card(key, suit="S", rank=2, value="2"):
    return {
        "key": key,
        "suit": suit,
        "rank": rank,
        "value": value,
        "enhancement": None,
        "seal": None,
        "edition": None,
    }


class HandAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = HandAgent()
        self.genome = Genome.default()

    def test_produces_play_or_discard_proposals(self):
        """基本场景：手牌足够时产生 play 或 discard 动作。"""
        hand = [
            _card("c_2s", "S", 2, "2"),
            _card("c_3s", "S", 3, "3"),
            _card("c_4s", "S", 4, "4"),
            _card("c_5s", "S", 5, "5"),
            _card("c_6s", "S", 6, "6"),
            _card("c_7s", "S", 7, "7"),
            _card("c_8s", "S", 8, "8"),
            _card("c_9s", "S", 9, "9"),
        ]
        state = _make_hand_state(hand)
        proposals = self.agent.propose(state, self.genome)
        self.assertGreater(len(proposals), 0)
        methods = {p.method for p in proposals}
        self.assertTrue({"play", "discard"} & methods,
                        f"Expected play or discard in methods: {methods}")

    def test_scores_play_proposals(self):
        """play 类型的 proposal 都有正分数。"""
        hand = [
            _card("c_2h", "H", 2, "2"),
            _card("c_3h", "H", 3, "3"),
            _card("c_4h", "H", 4, "4"),
            _card("c_5h", "H", 5, "5"),
            _card("c_6h", "H", 6, "6"),
            _card("c_7h", "H", 7, "7"),
            _card("c_8h", "H", 8, "8"),
            _card("c_9h", "H", 9, "9"),
        ]
        state = _make_hand_state(hand)
        proposals = self.agent.propose(state, self.genome)
        play_proposals = [p for p in proposals if p.method == "play"]
        self.assertGreater(len(play_proposals), 0)
        for p in play_proposals:
            self.assertGreater(p.score, 0, f"Play proposal should have positive score: {p}")

    def test_flush_detected_with_same_suit_cards(self):
        """五张同花牌被识别为 flush。"""
        from balatro_agent.agents.hand import HandAgent as HA
        agent = HA()
        cards = [
            _card("c_2h", "H", 2, "2"),
            _card("c_5h", "H", 5, "5"),
            _card("c_7h", "H", 7, "7"),
            _card("c_9h", "H", 9, "9"),
            _card("c_Kh", "H", 13, "K"),
        ]
        self.assertTrue(agent._is_flush(cards))

    def test_flush_not_detected_with_mixed_suits(self):
        """混合花色不被识别为 flush。"""
        from balatro_agent.agents.hand import HandAgent as HA
        agent = HA()
        cards = [
            _card("c_2h", "H", 2, "2"),
            _card("c_5s", "S", 5, "5"),
            _card("c_7h", "H", 7, "7"),
        ]
        self.assertFalse(agent._is_flush(cards))

    def test_straight_detected_with_consecutive_ranks(self):
        """连续 rank 被识别为 straight。"""
        from balatro_agent.agents.hand import HandAgent as HA
        agent = HA()
        self.assertTrue(agent._is_straight([2, 3, 4, 5, 6]))

    def test_straight_not_detected_with_gaps(self):
        """有间隔的 rank 不被识别为 straight。"""
        from balatro_agent.agents.hand import HandAgent as HA
        agent = HA()
        self.assertFalse(agent._is_straight([2, 4, 6, 8, 10]))

    def test_last_hand_produces_play_when_close(self):
        """最后一手且分数接近时，仍产生出牌动作。"""
        hand = [
            _card("c_Ah", "H", 14, "A"),
            _card("c_Kh", "H", 13, "K"),
            _card("c_Qh", "H", 12, "Q"),
            _card("c_Jh", "H", 11, "J"),
            _card("c_10h", "H", 10, "10"),
            _card("c_9h", "H", 9, "9"),
            _card("c_8h", "H", 8, "8"),
            _card("c_7h", "H", 7, "7"),
        ]
        state = _make_hand_state(
            hand,
            hands_remaining=1,
            chips_required=100,
        )
        proposals = self.agent.propose(state, self.genome)
        play_methods = [p for p in proposals if p.method == "play"]
        self.assertGreater(len(play_methods), 0,
                           "Should have play proposals on last hand when score is close")
```

- [ ] **Step 2: 运行 hand agent 测试**

```bash
cd /Users/suriness/Documents/liamCode/agent-balatro-codex && python3 -m unittest tests.test_hand_agent -v
```
Expected: 所有测试通过。

- [ ] **Step 3: 创建 test_shop_agent.py**

写入 `tests/test_shop_agent.py`：

```python
import unittest

from balatro_agent.agents.shop import ShopAgent
from balatro_agent.model import GameState, Genome


def _make_shop_state(**overrides):
    """构建 SHOP 的最小状态 fixture。"""
    base = {
        "state": "SHOP",
        "ante": 1,
        "money": 10,
        "shop": {"cards": []},
        "jokers": [],
        "consumables": {"cards": [], "limit": 2},
    }
    base.update(overrides)
    return GameState(base)


class ShopAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = ShopAgent()
        self.genome = Genome.default()

    def test_produces_next_round_when_empty_shop(self):
        """空商店时产生 next_round。"""
        state = _make_shop_state()
        proposals = self.agent.propose(state, self.genome)
        methods = {p.method for p in proposals}
        self.assertIn("next_round", methods)

    def test_produces_buy_for_affordable_joker(self):
        """有可负担的小丑牌时产生 buy 动作。"""
        state = _make_shop_state(
            money=10,
            shop={
                "cards": [
                    {"key": "j_joker", "name": "Joker", "cost": 2, "type": "Joker"}
                ]
            },
        )
        proposals = self.agent.propose(state, self.genome)
        methods = {p.method for p in proposals}
        self.assertIn("buy", methods)

    def test_does_not_buy_when_broke(self):
        """没钱时不产生 buy 动作。"""
        state = _make_shop_state(
            money=0,
            shop={
                "cards": [
                    {"key": "j_joker", "name": "Joker", "cost": 2, "type": "Joker"}
                ]
            },
        )
        proposals = self.agent.propose(state, self.genome)
        buy_proposals = [p for p in proposals if p.method == "buy"]
        self.assertEqual(len(buy_proposals), 0,
                         "Should not propose buying with no money")

    def test_joker_strength_positive_for_known_joker(self):
        """已知小丑牌的强度评估为正值。"""
        state = _make_shop_state(ante=1)
        score = self.agent._joker_strength(
            {"key": "j_gros_michel", "name": "Gros Michel", "type": "Joker"},
            state,
        )
        self.assertGreater(score, 0)

    def test_joker_strength_zero_for_unknown_key(self):
        """未知 key 的小丑牌强度为 0。"""
        state = _make_shop_state(ante=1)
        score = self.agent._joker_strength(
            {"key": "j_nonexistent_xyz", "name": "???", "type": "Joker"},
            state,
        )
        self.assertEqual(score, 0)
```

- [ ] **Step 4: 运行 shop agent 测试**

```bash
cd /Users/suriness/Documents/liamCode/agent-balatro-codex && python3 -m unittest tests.test_shop_agent -v
```
Expected: 所有测试通过。

- [ ] **Step 5: 确认全部测试套件通过**

```bash
cd /Users/suriness/Documents/liamCode/agent-balatro-codex && python3 -m unittest discover -s tests -v 2>&1 | tail -10
```
Expected: 所有测试通过。

- [ ] **Step 6: Commit**

```bash
git add tests/test_hand_agent.py tests/test_shop_agent.py && git commit --author="liam.lin <linguomaoo@gmail.com>" -m "test: add focused unit tests for HandAgent and ShopAgent"
```

---

### Task 9: 研究文档去重

**Files:**
- Modify: `research/findings.md`

- [ ] **Step 1: 查看 findings.md 当前结构**

Run: `grep "^## \|^### " /Users/suriness/Documents/liamCode/agent-balatro-codex/research/findings.md`
Expected: 列出所有章节标题。

- [ ] **Step 2: 识别并删除明显过时的发现**

Review `research/findings.md`，删除满足以下条件的条目：
- 被后续运行明确否定的结论（如 "AGENT1 无法通过 ante 3" 当后续已记录 ante 8 通过时）
- 完全重复的内容（同一发现不同措辞出现两次）
- 引用已删除脚本路径的纯操作记录（不是发现本身）

保留原则：有证据支撑、对理解当前 agent 行为仍有参考价值的发现。

- [ ] **Step 3: Commit**

```bash
git add research/findings.md && git commit --author="liam.lin <linguomaoo@gmail.com>" -m "docs: deduplicate and trim stale findings"
```

---

### Task 10: 最终验证与总结

- [ ] **Step 1: 运行完整测试套件**

```bash
cd /Users/suriness/Documents/liamCode/agent-balatro-codex && python3 -m unittest discover -s tests -v 2>&1 | tail -5
```
Expected: 所有测试通过。

- [ ] **Step 2: 验证仓库大小**

```bash
du -sh /Users/suriness/Documents/liamCode/agent-balatro-codex/ --exclude=.git
```
Expected: ~3-5MB（相比原来 ~40MB）。

- [ ] **Step 3: 验证文件数量**

```bash
find /Users/suriness/Documents/liamCode/agent-balatro-codex/balatro_agent/agents -type f | wc -l
```
Expected: `9`（`__init__.py` + `base.py` + 6 个 agent + 空 `constants.py` 和 `utils.py` 预留）。

- [ ] **Step 4: 最终 Commit**

```bash
git add -A && git status
# 确认变更范围后 commit
git commit --author="liam.lin <linguomaoo@gmail.com>" -m "chore: finalize project slimming - verify all tests pass"
```
