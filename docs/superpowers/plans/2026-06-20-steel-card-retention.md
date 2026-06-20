# Steel Card Retention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make The Chariot create Steel cards that are retained in hand for their held-card multiplier instead of being selected as normal scoring cards.

**Architecture:** Give `c_chariot` a dedicated low-value target selector. In `HandAgent`, score each candidate play with the multiplier from Steel cards left unplayed, and penalize playing Steel except when it is the final no-discard attempt. No test files are added per the user's standing instruction.

**Tech Stack:** Python 3, existing `GameState`, card enhancement helpers, and unittest suite.

---

### Task 1: Select a non-core target for The Chariot

**Files:**
- Modify: `balatro_agent/agents/tarot_targets.py:55-90`

- [x] **Step 1: Dispatch `c_chariot` before generic enhancements**

```python
if key == "c_chariot":
    return _steel_targets(state)
```

- [x] **Step 2: Add `_steel_targets`**

Select one unenhanced card with the lowest removal score and return an explicit retained-in-hand reason.

### Task 2: Score the held Steel multiplier in play selection

**Files:**
- Modify: `balatro_agent/agents/hand.py:599-644`

- [x] **Step 1: Add held-Steel multiplier to each candidate play**

```python
held_steel = sum(
    1 for index, card in enumerate(hand)
    if index not in indices and card_enhancement(card) == "STEEL"
)
score *= 1.5 ** held_steel
```

- [x] **Step 2: Penalize playing Steel unless the existing all-in condition applies**

Apply the penalty to `base_score` before candidate comparison; the final hand with no discard remains allowed to spend Steel.

### Task 3: Verify and commit

**Files:**
- Modify: `docs/superpowers/plans/2026-06-20-steel-card-retention.md`

- [x] **Step 1: Run syntax and the existing full suite**

Run: `python3 -m py_compile balatro_agent/agents/tarot_targets.py balatro_agent/agents/hand.py && python3 -m unittest discover -s tests`

Expected: exit status 0; no new or modified test files.

- [ ] **Step 2: Commit only the selector, HandAgent, and this plan**

Run: `git add balatro_agent/agents/tarot_targets.py balatro_agent/agents/hand.py docs/superpowers/plans/2026-06-20-steel-card-retention.md && git commit -m "fix: retain steel cards for held multiplier"`
