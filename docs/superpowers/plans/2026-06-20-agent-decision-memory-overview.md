# Agent Decision and Memory Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a standalone Chinese HTML report that explains the current Balatro agent's verified fixed-seed win, runtime decision chain, and evidence-driven memory loop without overstating strategy maturity.

**Architecture:** One self-contained HTML file will contain semantic sections, responsive CSS, inline SVG/CSS flow diagrams, native `<details>` evidence panels, and no external dependencies. A companion research-run log will record the documentation audit, source boundary, and unchanged project memory; it will not make new empirical strategy claims.

**Tech Stack:** HTML5, CSS3 custom properties, inline SVG, native `<details>`, Python 3 standard-library `html.parser` validation, existing `unittest` suite.

---

## File structure

- Create: `research/agent-decision-memory-overview.html` — the offline report.
- Create: `research/runs/2026-06-20.md` — research audit for this documentation run.
- Create: `docs/superpowers/plans/2026-06-20-agent-decision-memory-overview.md` — this implementation plan.
- Do not modify: `balatro_agent/`, `tests/`, `strategy/`, or existing research conclusions.

### Task 1: Define an evidence-oriented HTML contract

**Files:**
- Create: `research/agent-decision-memory-overview.html`

- [ ] **Step 1: Write the failing document-contract check**

Run this command before the page exists. It must fail because the target file does not yet exist:

```bash
python3 -c 'from pathlib import Path; assert Path("research/agent-decision-memory-overview.html").is_file(), "overview HTML missing"'
```

Expected: non-zero exit and `overview HTML missing`.

- [ ] **Step 2: Implement the semantic document shell**

Create an HTML5 document with this top-level structure, replacing each section body with sourced Chinese copy in Task 2:

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>小丑牌 Agent：决策、通关与记忆闭环</title>
</head>
<body>
  <main id="top">
    <header>…已证实 / 未证实的结论横幅…</header>
    <nav aria-label="页面目录">…</nav>
    <section id="win-route">…</section>
    <section id="decision-chain">…</section>
    <section id="checkpoint-search">…</section>
    <section id="memory-loop">…</section>
    <section id="memory-effect">…</section>
    <section id="evidence">…</section>
  </main>
</body>
</html>
```

- [ ] **Step 3: Run the contract check**

Run:

```bash
python3 -c 'from pathlib import Path; assert Path("research/agent-decision-memory-overview.html").is_file(), "overview HTML missing"'
```

Expected: exit 0.

### Task 2: Populate the report with source-bounded content and diagrams

**Files:**
- Modify: `research/agent-decision-memory-overview.html`

- [ ] **Step 1: Add the verified-win section and its limits**

State that AGENT1's Delayed/Stencil/Campfire route has two `won: true` fixed-seed runs, including the independent-reproduction scores 55264/50000 and 83556/75000. In a visually distinct warning card, state that no dev/regression/heldout stable-win conclusion exists. Cite the internal paths `research/findings.md`, `research/runs/2026-06-11.md`, and `research/decisions.md`.

- [ ] **Step 2: Add the runtime decision diagram**

Use accessible HTML labels and an inline SVG connector to show:

```text
BalatroBot gamestate
  → GameState
  → Round / Hand / Shop / Economy / Booster proposal agents
  → validate_action
  → max(score, confidence)
  → Runner execute + state-change confirmation
  → JSONL decision record
```

Attribute the implementation to `balatro_agent/agents.py`, `orchestrator.py`, `actions.py`, `runner.py`, and `model.py`. Explain that a proposal carries `method`, `params`, `score`, `confidence`, and `agent`.

- [ ] **Step 3: Add the optional search diagram**

Show the checkpoint path as a side branch: save root checkpoint, load one candidate branch at a time, execute bounded rollouts, compare with `StateValue`, restore the root. State the value priority exactly as `outcome → ante → round → blind completion → resources`, and state that checkpoint failures or disabled search return the base heuristic action. Cite `balatro_agent/search.py` and the 2026-06-14 research evidence about runtime cost.

- [ ] **Step 4: Add the memory loop and non-RAG boundary**

Use a closed flow diagram with:

```text
JSONL / terminal state / fixed-seed evaluation / replay / human gamestate record
  → research/ (facts, questions, decisions, run logs) + strategy/ (phase, Joker, case rules)
  → human or research-agent analysis
  → Python heuristic or genome adjustment
  → unit tests + dev / regression / heldout evaluation
  → new evidence
```

Add a three-column comparison: direct effect (rules already implemented in Python/genome), indirect effect (evidence informs future changes), and absent capability (no runtime Markdown parser, RAG retrieval, or autonomous online learning). Cite `README.md`, `strategy/README.md`, `strategy/runs/README.md`, and `research/README.md`.

- [ ] **Step 5: Implement the visual system and native evidence disclosure**

Define CSS custom properties for a deep table green background, warm ivory paper panels, brass accent, dark ink, warning orange, and success green. Use `max-width: 1180px`, CSS grid that collapses below `760px`, visible keyboard focus, `@media (prefers-reduced-motion: reduce)`, and `@media print`. Use native `<details><summary>证据与来源</summary>…</details>` elements rather than JavaScript; this makes disclosure keyboard-accessible and keeps the page dependency-free.

- [ ] **Step 6: Run content and parse validation**

Run this standard-library check:

```bash
python3 -c 'from html.parser import HTMLParser; from pathlib import Path; p=Path("research/agent-decision-memory-overview.html"); s=p.read_text(encoding="utf-8"); HTMLParser().feed(s); required=["won: true","55264/50000","83556/75000","validate_action","StateValue","Markdown","dev / regression / heldout"]; missing=[x for x in required if x not in s]; assert not missing, missing; assert "<html" in s.lower() and "</html>" in s.lower()'
```

Expected: exit 0.

### Task 3: Record the research audit without changing research conclusions

**Files:**
- Create: `research/runs/2026-06-20.md`

- [ ] **Step 1: Write the run log**

Record the documentation objective, documents and code inspected, the distinction between the verified fixed-seed win and unproven generality, and the absence of new gameplay observations. State that `research/memory.md`, `research/findings.md`, `research/questions.md`, `research/decisions.md`, and `research/sources.md` did not need substantive updates because this run only consolidates already-recorded evidence.

Include the next fixed-seed AGENT1 success estimate as `75%–90%`, explicitly scoped to the already-reproduced route and based on the two historical `won: true` results; state that it is not a cohort-level estimate. Recommend regression/heldout evaluation and repeated-run analysis before any promotion.

- [ ] **Step 2: Verify the research-run record**

Run:

```bash
rg -n "75%–90%|不更新|fixed-seed|regression|heldout" research/runs/2026-06-20.md
```

Expected: five matching concepts, each present in the run log.

### Task 4: Perform visual and repository verification

**Files:**
- Verify: `research/agent-decision-memory-overview.html`
- Verify: `research/runs/2026-06-20.md`

- [ ] **Step 1: Inspect desktop and narrow layouts in the in-app browser**

Open the generated HTML in the local browser. Confirm that the main flow is not clipped at desktop width, navigation anchors work, `<details>` opens with keyboard/mouse, and the 760px layout stacks cards in reading order. Capture a screenshot for visual evidence.

- [ ] **Step 2: Run project tests and whitespace checks**

Run:

```bash
python3 -m unittest discover -s tests
git diff --check
```

Expected: all existing tests pass; no whitespace errors for the task files.

- [ ] **Step 3: Review task-only changes and commit**

Run:

```bash
git status --short
git diff -- research/agent-decision-memory-overview.html research/runs/2026-06-20.md docs/superpowers/plans/2026-06-20-agent-decision-memory-overview.md
git add -- research/agent-decision-memory-overview.html research/runs/2026-06-20.md docs/superpowers/plans/2026-06-20-agent-decision-memory-overview.md
git commit -m "docs: explain agent decisions and memory"
```

Expected: only the three listed task files are staged and committed; pre-existing worktree changes remain untouched.
