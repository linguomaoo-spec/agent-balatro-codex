# Continual Learning Feedback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the next reliable continual-learning loop for the Balatro agent: strategy promotion gates, richer replay cases, replay retrieval, and replay-aware subagent task packs.

**Architecture:** Keep Python as the minimal analysis and CLI layer. `balatro_agent.analysis` owns pure JSON summary, comparison, and replay retrieval functions; `balatro_agent.cli` exposes read-only commands; `scripts/*.sh` provide shell entry points; `strategy/runs/README.md` documents the workflow. No game-decision behavior changes in this plan.

**Tech Stack:** Python 3.9 standard library, `unittest`, JSONL logs, shell scripts.

---

## Scope And Success Criteria

This plan implements the immediate P0-P2 loop from the research summary:

- P0: compare a baseline eval summary with a candidate eval summary and decide whether the candidate can be promoted.
- P1: enrich replay cases from JSONL logs beyond terminal/error-only samples.
- P2: retrieve top-k replay cases and inject them into generated subagent task packs.

Out of scope for this plan:

- Changing `HandAgent`, `ShopAgent`, `EconomyAgent`, or genome scoring.
- Running real BalatroBot evals; the plan uses local JSONL fixtures and existing commands.
- Adding external dependencies.

Success criteria:

- `python3 -m unittest tests.test_analysis` passes.
- `python3 -m unittest discover -s tests` passes.
- `sh -n scripts/*.sh` passes.
- `python3 -m balatro_agent promotion-gate --baseline /tmp/balatro-agent-final/baseline.json --candidate /tmp/balatro-agent-final/candidate.json` outputs stable JSON after those fixture files are created in Task 7.
- `python3 -m balatro_agent replay-query --replay /tmp/balatro-agent-final/replay.jsonl --phase SHOP --limit 2` outputs stable JSON after that fixture file is created in Task 7.
- `REPLAY=strategy/runs/replay.jsonl sh scripts/subagent-task.sh "分析商店失败" /tmp/shop-task.md` includes a replay section when cases match.

## File Structure

- Modify: `balatro_agent/analysis.py`
  - Add pure functions for promotion-gate comparison.
  - Enrich replay extraction with `decision` cases.
  - Add replay JSONL loading and top-k filtering.
- Modify: `balatro_agent/cli.py`
  - Add `promotion-gate` and `replay-query` read-only subcommands.
- Modify: `tests/test_analysis.py`
  - Add tests for promotion gate, enriched replay extraction, and replay query behavior.
- Create: `scripts/promotion-gate.sh`
  - Thin shell wrapper around `python3 -m balatro_agent promotion-gate`.
- Modify: `scripts/subagent-task.sh`
  - Optionally include top-k replay cases when `REPLAY`, `PHASE`, and `REPLAY_LIMIT` are set.
- Modify: `strategy/runs/README.md`
  - Document promotion gates, replay query, and replay-aware subagent workflow.

## Task 1: Strategy Promotion Gate Core

**Files:**
- Modify: `balatro_agent/analysis.py`
- Test: `tests/test_analysis.py`

- [ ] **Step 1: Write the failing test**

Append this test method to `AnalysisTests` in `tests/test_analysis.py`:

```python
    def test_compare_eval_summaries_blocks_candidate_with_regression(self):
        from balatro_agent.analysis import compare_eval_summaries

        baseline = {
            "run_count": 3,
            "win_rate": 0.33,
            "error_count": 0,
            "rejected_count": 1,
            "max_ante": 5,
            "runs": [
                {"path": "base/AGENT1.jsonl", "status": "game_over_loss", "max_ante": 5},
                {"path": "base/AGENT2.jsonl", "status": "game_over_win", "max_ante": 9},
                {"path": "base/AGENT3.jsonl", "status": "game_over_loss", "max_ante": 4},
            ],
        }
        candidate = {
            "run_count": 3,
            "win_rate": 0.33,
            "error_count": 1,
            "rejected_count": 2,
            "max_ante": 4,
            "runs": [
                {"path": "cand/AGENT1.jsonl", "status": "game_over_loss", "max_ante": 4},
                {"path": "cand/AGENT2.jsonl", "status": "game_over_loss", "max_ante": 8},
                {"path": "cand/AGENT3.jsonl", "status": "game_over_win", "max_ante": 9},
            ],
        }

        result = compare_eval_summaries(baseline, candidate, cohort="regression")

        self.assertFalse(result["promote"])
        self.assertEqual(result["cohort"], "regression")
        self.assertEqual(result["deltas"]["max_ante"], -1)
        self.assertEqual(result["deltas"]["error_count"], 1)
        self.assertIn("max_ante_regressed", result["failed_checks"])
        self.assertIn("error_count_increased", result["failed_checks"])
        self.assertIn("lost_previous_win", result["failed_checks"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_analysis.AnalysisTests.test_compare_eval_summaries_blocks_candidate_with_regression
```

Expected: FAIL with an import error for `compare_eval_summaries`.

- [ ] **Step 3: Implement the minimal promotion gate**

In `balatro_agent/analysis.py`, add this function below `summarize_jsonl_logs`:

```python
def compare_eval_summaries(
    baseline: Dict[str, Any],
    candidate: Dict[str, Any],
    cohort: str = "dev",
) -> Dict[str, Any]:
    baseline_runs = _runs_by_seed(baseline.get("runs") or [])
    candidate_runs = _runs_by_seed(candidate.get("runs") or [])
    lost_wins = sorted(
        seed
        for seed, run in baseline_runs.items()
        if run.get("status") == "game_over_win"
        and candidate_runs.get(seed, {}).get("status") != "game_over_win"
    )
    deltas = {
        "run_count": _as_int(candidate.get("run_count")) - _as_int(baseline.get("run_count")),
        "win_rate": _as_float(candidate.get("win_rate")) - _as_float(baseline.get("win_rate")),
        "error_count": _as_int(candidate.get("error_count")) - _as_int(baseline.get("error_count")),
        "rejected_count": _as_int(candidate.get("rejected_count")) - _as_int(baseline.get("rejected_count")),
        "max_ante": _as_int(candidate.get("max_ante")) - _as_int(baseline.get("max_ante")),
    }
    failed_checks: List[str] = []
    if deltas["max_ante"] < 0:
        failed_checks.append("max_ante_regressed")
    if deltas["win_rate"] < 0:
        failed_checks.append("win_rate_regressed")
    if deltas["error_count"] > 0:
        failed_checks.append("error_count_increased")
    if lost_wins:
        failed_checks.append("lost_previous_win")
    if cohort == "heldout" and deltas["rejected_count"] > 0:
        failed_checks.append("heldout_rejected_count_increased")
    return {
        "cohort": cohort,
        "promote": not failed_checks,
        "failed_checks": failed_checks,
        "deltas": deltas,
        "lost_wins": lost_wins,
        "baseline": {
            "run_count": _as_int(baseline.get("run_count")),
            "win_rate": _as_float(baseline.get("win_rate")),
            "error_count": _as_int(baseline.get("error_count")),
            "rejected_count": _as_int(baseline.get("rejected_count")),
            "max_ante": _as_int(baseline.get("max_ante")),
        },
        "candidate": {
            "run_count": _as_int(candidate.get("run_count")),
            "win_rate": _as_float(candidate.get("win_rate")),
            "error_count": _as_int(candidate.get("error_count")),
            "rejected_count": _as_int(candidate.get("rejected_count")),
            "max_ante": _as_int(candidate.get("max_ante")),
        },
    }
```

Add these helpers near the existing private helpers:

```python
def _runs_by_seed(runs: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for run in runs:
        seed = _seed_from_path(str(run.get("path") or ""))
        if seed:
            result[seed] = run
    return result


def _seed_from_path(path: str) -> str:
    name = Path(path).stem
    if not name:
        return ""
    return name


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
```

- [ ] **Step 4: Run the focused test**

Run:

```bash
python3 -m unittest tests.test_analysis.AnalysisTests.test_compare_eval_summaries_blocks_candidate_with_regression
```

Expected: PASS.

- [ ] **Step 5: Run the full analysis tests**

Run:

```bash
python3 -m unittest tests.test_analysis
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add balatro_agent/analysis.py tests/test_analysis.py
git commit -m "feat: add strategy promotion gate"
```

If the working tree contains unrelated user changes, stage only the two files above.

## Task 2: Promotion Gate CLI And Shell Wrapper

**Files:**
- Modify: `balatro_agent/cli.py`
- Create: `scripts/promotion-gate.sh`
- Test: `tests/test_analysis.py`

- [ ] **Step 1: Write the failing CLI test**

Append this test method to `AnalysisTests` in `tests/test_analysis.py`:

```python
    def test_promotion_gate_cli_outputs_decision_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            baseline.write_text(
                json.dumps(
                    {
                        "run_count": 1,
                        "win_rate": 0.0,
                        "error_count": 0,
                        "rejected_count": 0,
                        "max_ante": 2,
                        "runs": [{"path": "base/AGENT1.jsonl", "status": "game_over_loss", "max_ante": 2}],
                    }
                )
            )
            candidate.write_text(
                json.dumps(
                    {
                        "run_count": 1,
                        "win_rate": 0.0,
                        "error_count": 0,
                        "rejected_count": 0,
                        "max_ante": 3,
                        "runs": [{"path": "cand/AGENT1.jsonl", "status": "game_over_loss", "max_ante": 3}],
                    }
                )
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = main(
                    [
                        "promotion-gate",
                        "--baseline",
                        str(baseline),
                        "--candidate",
                        str(candidate),
                        "--cohort",
                        "dev",
                    ]
                )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertTrue(payload["promote"])
        self.assertEqual(payload["deltas"]["max_ante"], 1)
```

- [ ] **Step 2: Run the CLI test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_analysis.AnalysisTests.test_promotion_gate_cli_outputs_decision_json
```

Expected: FAIL with argparse rejecting `promotion-gate`.

- [ ] **Step 3: Add CLI parser and handler**

In `balatro_agent/cli.py`, update the import:

```python
from balatro_agent.analysis import compare_eval_summaries, summarize_jsonl_logs, write_replay_cases
```

In `build_parser()`, add this parser after `summarize-eval`:

```python
    promotion_gate = subparsers.add_parser("promotion-gate", help="比较 baseline 和候选评估摘要，输出策略晋升判断")
    promotion_gate.add_argument("--baseline", type=Path, required=True, help="baseline summarize-eval JSON 文件")
    promotion_gate.add_argument("--candidate", type=Path, required=True, help="候选 summarize-eval JSON 文件")
    promotion_gate.add_argument("--cohort", default="dev", help="用于解释门槛的 cohort 名称")
```

In `main()`, add this handler before creating `BalatroBotClient`:

```python
    if args.command == "promotion-gate":
        baseline = json.loads(args.baseline.read_text())
        candidate = json.loads(args.candidate.read_text())
        print(
            json.dumps(
                compare_eval_summaries(baseline, candidate, cohort=args.cohort),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
```

- [ ] **Step 4: Add shell wrapper**

Create `scripts/promotion-gate.sh`:

```sh
#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

BASELINE=${BASELINE:?Set BASELINE to a summarize-eval JSON file}
CANDIDATE=${CANDIDATE:?Set CANDIDATE to a summarize-eval JSON file}
COHORT=${COHORT:-dev}

python3 -m balatro_agent promotion-gate \
  --baseline "$BASELINE" \
  --candidate "$CANDIDATE" \
  --cohort "$COHORT"
```

- [ ] **Step 5: Run focused verification**

Run:

```bash
python3 -m unittest tests.test_analysis.AnalysisTests.test_promotion_gate_cli_outputs_decision_json
sh -n scripts/promotion-gate.sh
```

Expected: both commands pass.

- [ ] **Step 6: Run full verification**

Run:

```bash
python3 -m unittest discover -s tests
sh -n scripts/*.sh
```

Expected: all tests pass and shell syntax checks pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add balatro_agent/cli.py tests/test_analysis.py scripts/promotion-gate.sh
git commit -m "feat: expose strategy promotion gate"
```

## Task 3: Enrich Replay Cases With Decision Samples

**Files:**
- Modify: `balatro_agent/analysis.py`
- Test: `tests/test_analysis.py`

- [ ] **Step 1: Write the failing replay enrichment test**

Append this test method to `AnalysisTests` in `tests/test_analysis.py`:

```python
    def test_extract_replay_cases_includes_high_gap_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "decision.jsonl").write_text(
                json.dumps(
                    {
                        "state": {
                            "phase": "SELECTING_HAND",
                            "ante": 2,
                            "money": 6,
                            "score": 100,
                            "required_score": 600,
                            "jokers": 1,
                            "hands": 1,
                            "discards": 0,
                        },
                        "action": {"method": "play", "params": {"cards": [0, 1]}},
                        "executed": {"method": "play", "params": {"cards": [0, 1]}},
                        "proposals": [
                            {"method": "play", "score": 30.0, "agent": "hand"},
                            {"method": "discard", "score": 15.0, "agent": "hand"},
                        ],
                        "rejected": [{"method": "discard", "reason": "需要 SELECTING_HAND 阶段"}],
                    }
                )
                + "\n"
            )

            cases = extract_replay_cases(root, limit=10)

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["case_type"], "decision")
        self.assertEqual(cases[0]["score_gap"], 500)
        self.assertEqual(cases[0]["proposal_count"], 2)
        self.assertEqual(cases[0]["action_params"], {"cards": [0, 1]})
```

- [ ] **Step 2: Run the replay enrichment test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_analysis.AnalysisTests.test_extract_replay_cases_includes_high_gap_decisions
```

Expected: FAIL because no decision case is extracted.

- [ ] **Step 3: Add decision case detection**

In `balatro_agent/analysis.py`, replace `_case_type` with:

```python
def _case_type(record: Dict[str, Any], index: int, total: int) -> Optional[str]:
    if record.get("error"):
        return "error"
    state = record.get("state") or {}
    if index == total - 1 and str(state.get("phase") or "").upper() == "GAME_OVER":
        if state.get("won") is True:
            return "terminal_win"
        if state.get("won") is False:
            return "terminal_loss"
        return "terminal_unknown"
    if _is_decision_case(record):
        return "decision"
    return None
```

Add this helper near `_case_type`:

```python
def _is_decision_case(record: Dict[str, Any]) -> bool:
    state = record.get("state") or {}
    required_score = _as_int(state.get("required_score"))
    score = _as_int(state.get("score"))
    score_gap = max(0, required_score - score)
    if score_gap > 0 and _as_int(state.get("hands")) <= 1:
        return True
    if record.get("rejected"):
        return True
    return False
```

- [ ] **Step 4: Enrich case payload**

In `extract_replay_cases`, inside the case dictionary, add these keys:

```python
                    "hands": _as_int(state.get("hands")),
                    "discards": _as_int(state.get("discards")),
                    "action_params": _params_dict(record.get("action")),
                    "executed_params": _params_dict(record.get("executed")),
                    "proposal_count": len(record.get("proposals") or []),
                    "agents": _proposal_agents(record.get("proposals") or []),
```

Add these helpers near `_method_name`:

```python
def _params_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get("params"), dict):
        return dict(value["params"])
    return {}


def _proposal_agents(proposals: Iterable[Any]) -> List[str]:
    agents = []
    for proposal in proposals:
        if isinstance(proposal, dict):
            agent = str(proposal.get("agent") or "")
            if agent and agent not in agents:
                agents.append(agent)
    return agents
```

- [ ] **Step 5: Run replay tests**

Run:

```bash
python3 -m unittest tests.test_analysis.AnalysisTests.test_extract_replay_cases_includes_high_gap_decisions
python3 -m unittest tests.test_analysis.AnalysisTests.test_extract_replay_cases_keeps_errors_and_terminal_outcomes
```

Expected: both tests pass.

- [ ] **Step 6: Run full analysis tests**

Run:

```bash
python3 -m unittest tests.test_analysis
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add balatro_agent/analysis.py tests/test_analysis.py
git commit -m "feat: enrich replay decision cases"
```

## Task 4: Replay Top-K Query

**Files:**
- Modify: `balatro_agent/analysis.py`
- Modify: `balatro_agent/cli.py`
- Test: `tests/test_analysis.py`

- [ ] **Step 1: Write the failing replay query test**

Append this test method to `AnalysisTests` in `tests/test_analysis.py`:

```python
    def test_query_replay_cases_filters_and_orders_by_relevance(self):
        from balatro_agent.analysis import query_replay_cases

        cases = [
            {"case_type": "decision", "phase": "SHOP", "ante": 2, "score_gap": 0, "rejected_count": 1, "source": "a"},
            {"case_type": "terminal_loss", "phase": "SELECTING_HAND", "ante": 4, "score_gap": 900, "rejected_count": 0, "source": "b"},
            {"case_type": "error", "phase": "SHOP", "ante": 3, "score_gap": 100, "rejected_count": 2, "source": "c"},
        ]

        result = query_replay_cases(cases, phase="SHOP", limit=2)

        self.assertEqual([case["source"] for case in result], ["c", "a"])
```

- [ ] **Step 2: Run the replay query test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_analysis.AnalysisTests.test_query_replay_cases_filters_and_orders_by_relevance
```

Expected: FAIL with an import error for `query_replay_cases`.

- [ ] **Step 3: Implement replay query functions**

In `balatro_agent/analysis.py`, add these public functions after `write_replay_cases`:

```python
def load_replay_cases(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return list(_read_jsonl(path))


def query_replay_cases(
    cases: Iterable[Dict[str, Any]],
    phase: Optional[str] = None,
    case_type: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    filtered = []
    phase_filter = str(phase or "").upper()
    type_filter = str(case_type or "")
    for case in cases:
        if phase_filter and str(case.get("phase") or "").upper() != phase_filter:
            continue
        if type_filter and str(case.get("case_type") or "") != type_filter:
            continue
        filtered.append(case)
    filtered.sort(key=_replay_relevance_score, reverse=True)
    return filtered[: max(0, limit)]
```

Add this helper near `_proposal_agents`:

```python
def _replay_relevance_score(case: Dict[str, Any]) -> float:
    type_bonus = {
        "error": 1000.0,
        "terminal_loss": 600.0,
        "decision": 300.0,
        "terminal_unknown": 100.0,
        "terminal_win": 50.0,
    }.get(str(case.get("case_type") or ""), 0.0)
    return (
        type_bonus
        + _as_int(case.get("rejected_count")) * 50.0
        + _as_int(case.get("score_gap")) * 0.1
        + _as_int(case.get("ante")) * 5.0
    )
```

- [ ] **Step 4: Add CLI test**

Append this test method to `AnalysisTests`:

```python
    def test_replay_query_cli_outputs_matching_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            replay = root / "replay.jsonl"
            replay.write_text(
                "\n".join(
                    [
                        json.dumps({"case_type": "decision", "phase": "SHOP", "ante": 1, "source": "a"}),
                        json.dumps({"case_type": "error", "phase": "SHOP", "ante": 2, "source": "b"}),
                        json.dumps({"case_type": "decision", "phase": "SELECTING_HAND", "ante": 3, "source": "c"}),
                    ]
                )
                + "\n"
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = main(["replay-query", "--replay", str(replay), "--phase", "SHOP", "--limit", "1"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(len(payload["cases"]), 1)
        self.assertEqual(payload["cases"][0]["source"], "b")
```

- [ ] **Step 5: Add CLI parser and handler**

In `balatro_agent/cli.py`, update the import:

```python
from balatro_agent.analysis import (
    compare_eval_summaries,
    load_replay_cases,
    query_replay_cases,
    summarize_jsonl_logs,
    write_replay_cases,
)
```

In `build_parser()`, add this parser after `build-replay`:

```python
    replay_query = subparsers.add_parser("replay-query", help="从 replay JSONL 查询最相关案例")
    replay_query.add_argument("--replay", type=Path, default=Path("strategy/runs/replay.jsonl"), help="replay JSONL 路径")
    replay_query.add_argument("--phase", default=None, help="可选阶段过滤，例如 SHOP")
    replay_query.add_argument("--case-type", default=None, help="可选案例类型过滤，例如 error")
    replay_query.add_argument("--limit", type=int, default=5, help="返回案例数量")
```

In `main()`, add this handler before creating `BalatroBotClient`:

```python
    if args.command == "replay-query":
        cases = query_replay_cases(
            load_replay_cases(args.replay),
            phase=args.phase,
            case_type=args.case_type,
            limit=args.limit,
        )
        print(json.dumps({"cases": cases}, indent=2, sort_keys=True))
        return 0
```

- [ ] **Step 6: Run replay query verification**

Run:

```bash
python3 -m unittest tests.test_analysis.AnalysisTests.test_query_replay_cases_filters_and_orders_by_relevance
python3 -m unittest tests.test_analysis.AnalysisTests.test_replay_query_cli_outputs_matching_cases
```

Expected: both tests pass.

- [ ] **Step 7: Run full verification**

Run:

```bash
python3 -m unittest discover -s tests
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add balatro_agent/analysis.py balatro_agent/cli.py tests/test_analysis.py
git commit -m "feat: query replay cases"
```

## Task 5: Replay-Aware Subagent Task Packs

**Files:**
- Modify: `scripts/subagent-task.sh`
- Test: manual shell verification command below

- [ ] **Step 1: Create a small replay fixture for manual verification**

Run:

```bash
mkdir -p /tmp/balatro-agent-plan
cat > /tmp/balatro-agent-plan/replay.jsonl <<'EOF'
{"case_type":"error","phase":"SHOP","ante":3,"source":"runs/eval/AGENT4.jsonl","action":"buy","executed":"next_round","score_gap":0,"rejected_count":2}
{"case_type":"decision","phase":"SELECTING_HAND","ante":2,"source":"runs/eval/AGENT5.jsonl","action":"play","executed":"play","score_gap":500,"rejected_count":0}
EOF
```

- [ ] **Step 2: Run current script and confirm replay is absent**

Run:

```bash
REPLAY=/tmp/balatro-agent-plan/replay.jsonl PHASE=SHOP REPLAY_LIMIT=1 sh scripts/subagent-task.sh "分析商店失败" /tmp/balatro-agent-plan/task.md
rg "相关 replay 案例|runs/eval/AGENT4.jsonl" /tmp/balatro-agent-plan/task.md
```

Expected: the script creates the task file; `rg` exits non-zero because replay cases are not included yet.

- [ ] **Step 3: Modify `scripts/subagent-task.sh`**

Add these variables after `OUTPUT=${2:-}`:

```sh
REPLAY=${REPLAY:-}
PHASE=${PHASE:-}
CASE_TYPE=${CASE_TYPE:-}
REPLAY_LIMIT=${REPLAY_LIMIT:-5}
```

Inside the output block, after the “最近研究运行” section, add:

```sh
  if [ -n "$REPLAY" ] && [ -f "$REPLAY" ]; then
    echo
    echo "## 相关 replay 案例"
    if [ -n "$PHASE" ] && [ -n "$CASE_TYPE" ]; then
      python3 -m balatro_agent replay-query \
        --replay "$REPLAY" \
        --phase "$PHASE" \
        --case-type "$CASE_TYPE" \
        --limit "$REPLAY_LIMIT"
    elif [ -n "$PHASE" ]; then
      python3 -m balatro_agent replay-query \
        --replay "$REPLAY" \
        --phase "$PHASE" \
        --limit "$REPLAY_LIMIT"
    elif [ -n "$CASE_TYPE" ]; then
      python3 -m balatro_agent replay-query \
        --replay "$REPLAY" \
        --case-type "$CASE_TYPE" \
        --limit "$REPLAY_LIMIT"
    else
      python3 -m balatro_agent replay-query \
        --replay "$REPLAY" \
        --limit "$REPLAY_LIMIT"
    fi
  fi
```

- [ ] **Step 4: Run manual verification**

Run:

```bash
REPLAY=/tmp/balatro-agent-plan/replay.jsonl PHASE=SHOP REPLAY_LIMIT=1 sh scripts/subagent-task.sh "分析商店失败" /tmp/balatro-agent-plan/task.md
rg "相关 replay 案例|runs/eval/AGENT4.jsonl" /tmp/balatro-agent-plan/task.md
sh -n scripts/subagent-task.sh
```

Expected: `rg` finds both `相关 replay 案例` and `runs/eval/AGENT4.jsonl`; shell syntax check passes.

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts/subagent-task.sh
git commit -m "feat: include replay cases in subagent tasks"
```

## Task 6: Document The New Research Loop

**Files:**
- Modify: `strategy/runs/README.md`
- Modify: `README.md`

- [ ] **Step 1: Update `strategy/runs/README.md`**

Add this section after “固定 seed 分组”:

```markdown
## 策略晋升门槛

候选策略或 genome 先在 `dev` cohort 上验证收益，再在 `regression` 和 `heldout`
cohort 上检查退化。推荐流程：

1. 保存 baseline 摘要：`python3 -m balatro_agent summarize-eval --log-dir runs/eval-baseline > runs/baseline-summary.json`
2. 保存候选摘要：`python3 -m balatro_agent summarize-eval --log-dir runs/eval-candidate > runs/candidate-summary.json`
3. 比较门槛：`BASELINE=runs/baseline-summary.json CANDIDATE=runs/candidate-summary.json COHORT=regression sh scripts/promotion-gate.sh`

默认阻断条件：

- `max_ante` 下降。
- `win_rate` 下降。
- `error_count` 增加。
- baseline 中已经胜利的 seed 在候选中丢失胜利。
- `heldout` 中 `rejected_count` 增加。

被阻断的候选只能保留为工作假设或失败案例，不能晋升为稳定策略。
```

Add this section after “replay 案例类型”:

```markdown
## replay 检索和子 agent 注入

构建 replay 后，可以查询相关案例：

```bash
python3 -m balatro_agent replay-query --replay strategy/runs/replay.jsonl --phase SHOP --limit 5
```

生成子 agent 任务包时可以注入相关案例：

```bash
REPLAY=strategy/runs/replay.jsonl PHASE=SHOP REPLAY_LIMIT=5 \
  sh scripts/subagent-task.sh "分析最近商店失败"
```

子 agent 应基于这些案例提出可验证的策略假设，并在输出中说明证据路径。
```

- [ ] **Step 2: Update `README.md` common commands**

In the “常用命令” section, add these command blocks after “抽取 replay 经验案例”:

```markdown
比较 baseline 和候选评估摘要：

```bash
BASELINE=runs/baseline-summary.json CANDIDATE=runs/candidate-summary.json COHORT=regression \
  sh scripts/promotion-gate.sh
```

查询 replay 案例：

```bash
python3 -m balatro_agent replay-query --replay strategy/runs/replay.jsonl --phase SHOP --limit 5
```
```

- [ ] **Step 3: Run documentation checks**

Run:

```bash
rg "promotion-gate|replay-query|策略晋升门槛" README.md strategy/runs/README.md
git diff --check
```

Expected: `rg` finds all three phrases; `git diff --check` exits successfully.

- [ ] **Step 4: Commit**

Run:

```bash
git add README.md strategy/runs/README.md
git commit -m "docs: document promotion gate workflow"
```

## Task 7: Final Verification

**Files:**
- No new source files in this task.

- [ ] **Step 1: Run all tests**

Run:

```bash
python3 -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 2: Run shell syntax checks**

Run:

```bash
sh -n scripts/*.sh
```

Expected: no output and exit code 0.

- [ ] **Step 3: Verify CLI help includes new commands**

Run:

```bash
python3 -m balatro_agent --help | rg "promotion-gate|replay-query"
```

Expected: both command names are printed.

- [ ] **Step 4: Verify a minimal end-to-end local flow**

Run:

```bash
mkdir -p /tmp/balatro-agent-final
cat > /tmp/balatro-agent-final/baseline.json <<'EOF'
{"run_count":1,"win_rate":0.0,"error_count":0,"rejected_count":0,"max_ante":2,"runs":[{"path":"base/AGENT1.jsonl","status":"game_over_loss","max_ante":2}]}
EOF
cat > /tmp/balatro-agent-final/candidate.json <<'EOF'
{"run_count":1,"win_rate":0.0,"error_count":0,"rejected_count":0,"max_ante":3,"runs":[{"path":"cand/AGENT1.jsonl","status":"game_over_loss","max_ante":3}]}
EOF
python3 -m balatro_agent promotion-gate \
  --baseline /tmp/balatro-agent-final/baseline.json \
  --candidate /tmp/balatro-agent-final/candidate.json \
  --cohort dev
```

Expected JSON contains:

```json
{
  "promote": true
}
```

- [ ] **Step 5: Verify replay query local flow**

Run:

```bash
cat > /tmp/balatro-agent-final/replay.jsonl <<'EOF'
{"case_type":"decision","phase":"SHOP","ante":1,"source":"a"}
{"case_type":"error","phase":"SHOP","ante":2,"source":"b"}
EOF
python3 -m balatro_agent replay-query \
  --replay /tmp/balatro-agent-final/replay.jsonl \
  --phase SHOP \
  --limit 1
```

Expected JSON contains:

```json
{
  "source": "b"
}
```

- [ ] **Step 6: Inspect final diff**

Run:

```bash
git status --short
git diff --stat HEAD
```

Expected: only the planned files are changed relative to the last commit in this implementation branch.

## Self-Review Checklist

- Spec coverage: Tasks 1-2 implement promotion gates, Tasks 3-5 implement replay enrichment/retrieval/subagent injection, Task 6 documents the workflow, Task 7 verifies the full loop.
- Placeholder scan: The plan contains concrete paths, commands, expected outcomes, and code snippets for each implementation step.
- Type consistency: Public functions are `compare_eval_summaries`, `load_replay_cases`, and `query_replay_cases`; CLI commands are `promotion-gate` and `replay-query`; shell wrapper is `scripts/promotion-gate.sh`.
