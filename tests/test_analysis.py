import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from balatro_agent.analysis import extract_replay_cases, summarize_jsonl_logs
from balatro_agent.cli import main


class AnalysisTests(unittest.TestCase):
    def test_summarize_jsonl_logs_reports_run_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "win.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "state": {
                                    "phase": "SELECTING_HAND",
                                    "ante": 8,
                                    "money": 10,
                                    "score": 1000,
                                    "required_score": 1200,
                                    "jokers": 4,
                                    "won": None,
                                },
                                "action": {"method": "play"},
                                "executed": {"method": "play"},
                                "rejected": [{}],
                            }
                        ),
                        json.dumps(
                            {
                                "state": {
                                    "phase": "GAME_OVER",
                                    "ante": 9,
                                    "money": 20,
                                    "score": 0,
                                    "required_score": 0,
                                    "jokers": 5,
                                    "won": True,
                                },
                                "action": {"method": "gamestate"},
                                "executed": {"method": "gamestate"},
                            }
                        ),
                    ]
                )
                + "\n"
            )
            (root / "loss.jsonl").write_text(
                json.dumps(
                    {
                        "state": {
                            "phase": "SHOP",
                            "ante": 2,
                            "money": 3,
                            "score": 80,
                            "required_score": 300,
                            "jokers": 2,
                            "won": False,
                        },
                        "action": {"method": "buy"},
                        "executed": {"method": "next_round"},
                        "error": {"name": "NOT_ALLOWED"},
                        "rejected": [{}, {}],
                    }
                )
                + "\n"
            )

            summary = summarize_jsonl_logs(root)

        self.assertEqual(summary["run_count"], 2)
        self.assertEqual(summary["record_count"], 3)
        self.assertEqual(summary["win_count"], 1)
        self.assertEqual(summary["error_count"], 1)
        self.assertEqual(summary["rejected_count"], 3)
        self.assertEqual(summary["max_ante"], 9)

        runs = {Path(run["path"]).name: run for run in summary["runs"]}
        self.assertEqual(runs["win.jsonl"]["status"], "game_over_win")
        self.assertEqual(runs["loss.jsonl"]["failure_phase"], "SHOP")
        self.assertEqual(runs["loss.jsonl"]["score_gap"], 220)
        self.assertEqual(runs["loss.jsonl"]["final_jokers"], 2)

    def test_summarize_eval_cli_outputs_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "seed.jsonl").write_text(
                json.dumps(
                    {
                        "state": {"phase": "SHOP", "ante": 1, "money": 5},
                        "action": {"method": "next_round"},
                        "executed": {"method": "next_round"},
                    }
                )
                + "\n"
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = main(["summarize-eval", "--log-dir", str(root)])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(payload["run_count"], 1)
        self.assertEqual(payload["record_count"], 1)

    def test_extract_replay_cases_keeps_errors_and_terminal_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "state": {
                                    "phase": "SHOP",
                                    "ante": 2,
                                    "money": 8,
                                    "score": 0,
                                    "required_score": 0,
                                    "jokers": 2,
                                },
                                "action": {"method": "buy"},
                                "executed": {"method": "next_round"},
                                "error": {"name": "NOT_ALLOWED"},
                                "rejected": [{}],
                            }
                        ),
                        json.dumps(
                            {
                                "state": {
                                    "phase": "GAME_OVER",
                                    "ante": 3,
                                    "money": 0,
                                    "score": 250,
                                    "required_score": 600,
                                    "jokers": 2,
                                    "won": False,
                                },
                                "action": {"method": "play"},
                                "executed": {"method": "play"},
                            }
                        ),
                    ]
                )
                + "\n"
            )

            cases = extract_replay_cases(root)

        self.assertEqual([case["case_type"] for case in cases], ["error", "terminal_loss"])
        self.assertEqual(cases[0]["phase"], "SHOP")
        self.assertEqual(cases[0]["error_name"], "NOT_ALLOWED")
        self.assertEqual(cases[1]["score_gap"], 350)

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

    def test_build_replay_cli_writes_jsonl_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "replay.jsonl"
            (root / "run.jsonl").write_text(
                json.dumps(
                    {
                        "state": {
                            "phase": "GAME_OVER",
                            "ante": 9,
                            "won": True,
                        },
                        "action": {"method": "gamestate"},
                        "executed": {"method": "gamestate"},
                    }
                )
                + "\n"
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = main(["build-replay", "--log-dir", str(root), "--output", str(output)])
            payload = json.loads(output.read_text())

        self.assertEqual(result, 0)
        self.assertEqual(payload["case_type"], "terminal_win")
        self.assertEqual(payload["phase"], "GAME_OVER")

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
                        "runs": [
                            {
                                "path": "base/AGENT1.jsonl",
                                "status": "game_over_loss",
                                "max_ante": 2,
                            }
                        ],
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
                        "runs": [
                            {
                                "path": "cand/AGENT1.jsonl",
                                "status": "game_over_loss",
                                "max_ante": 3,
                            }
                        ],
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

    def test_query_replay_cases_filters_and_orders_by_relevance(self):
        from balatro_agent.analysis import query_replay_cases

        cases = [
            {
                "case_type": "decision",
                "phase": "SHOP",
                "ante": 2,
                "score_gap": 0,
                "rejected_count": 1,
                "source": "a",
            },
            {
                "case_type": "terminal_loss",
                "phase": "SELECTING_HAND",
                "ante": 4,
                "score_gap": 900,
                "rejected_count": 0,
                "source": "b",
            },
            {
                "case_type": "error",
                "phase": "SHOP",
                "ante": 3,
                "score_gap": 100,
                "rejected_count": 2,
                "source": "c",
            },
        ]

        result = query_replay_cases(cases, phase="SHOP", limit=2)

        self.assertEqual([case["source"] for case in result], ["c", "a"])

    def test_replay_query_cli_outputs_matching_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            replay = root / "replay.jsonl"
            replay.write_text(
                "\n".join(
                    [
                        json.dumps({"case_type": "decision", "phase": "SHOP", "ante": 1, "source": "a"}),
                        json.dumps({"case_type": "error", "phase": "SHOP", "ante": 2, "source": "b"}),
                        json.dumps(
                            {
                                "case_type": "decision",
                                "phase": "SELECTING_HAND",
                                "ante": 3,
                                "source": "c",
                            }
                        ),
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


if __name__ == "__main__":
    unittest.main()
