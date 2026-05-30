import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from balatro_agent.analysis import summarize_jsonl_logs
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


if __name__ == "__main__":
    unittest.main()
