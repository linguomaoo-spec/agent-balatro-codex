# Shared Tarot Targeting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the duplicated highest-rank Tarot target heuristic with one effect-aware target selector used by both pack and consumable actions.

**Architecture:** Add a pure `tarot_targets` module that maps each supported Tarot key to an effect-specific selector. `BoosterAgent` and `ConsumableAgent` retain their own action scoring but obtain target indices and explanations from that module. No new tests are added at the user's request; the existing suite is the regression gate.

**Tech Stack:** Python 3, dataclasses, existing `GameState` and card helper functions.

---

### Task 1: Add shared Tarot target selector

**Files:**
- Create: `balatro_agent/agents/tarot_targets.py`

- [x] **Step 1: Add `TarotTargetChoice` and `choose_tarot_targets`**

```python
@dataclass(frozen=True)
class TarotTargetChoice:
    cards: List[int]
    reasons: List[str]

def choose_tarot_targets(tarot_key: str, state: GameState) -> Optional[TarotTargetChoice]:
    # dispatch to enhancement, Strength, Death, suit-conversion, or Hanged Man selectors
```

- [x] **Step 2: Implement only effect-aware selectors**

Use a main-hand-type resolver based on Joker signals and hand structure. Return no choice for suit conversion without flush/suit-Joker support, and for any action with no strategically valid target. Use low-value non-core cards for Hanged Man; choose a low-value destination plus high-value source for Death, with the API order isolated in one named helper.

### Task 2: Route both action paths through the selector

**Files:**
- Modify: `balatro_agent/agents/booster.py:22-104,260-280`
- Modify: `balatro_agent/agents/consumable.py:35-141,274-288`

- [x] **Step 1: Replace local target-count and target-ranking calls**

```python
choice = choose_tarot_targets(key, state)
if choice is None:
    continue
params["cards"] = choice.cards
reasons.extend(choice.reasons)
```

- [x] **Step 2: Remove duplicated `_best_tarot_targets` methods and unused card-ranking imports**

Keep each agent's non-target Tarot and card-value scoring unchanged.

### Task 3: Verify existing behavior is not regressed

**Files:**
- Modify: none

- [x] **Step 1: Run the full existing suite**

Run: `python3 -m unittest discover -s tests`

Expected: exit status 0. No test files are added or modified.

- [ ] **Step 2: Inspect the staged diff and commit only implementation files**

Run: `git diff --check && git diff -- balatro_agent/agents/tarot_targets.py balatro_agent/agents/booster.py balatro_agent/agents/consumable.py`

Commit: `git add balatro_agent/agents/tarot_targets.py balatro_agent/agents/booster.py balatro_agent/agents/consumable.py && git commit -m "fix: specialize tarot target selection"`
