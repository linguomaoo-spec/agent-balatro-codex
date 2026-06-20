import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from balatro_agent.cli import build_parser, main


class CliTests(unittest.TestCase):
    def test_evolve_exposes_simulation_flags(self):
        parser = build_parser()
        subparsers = next(
            action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
        )
        evolve = subparsers.choices["evolve"]
        options = {option for action in evolve._actions for option in action.option_strings}

        self.assertIn("--sim", options)
        self.assertIn("--sim-log-dir", options)

    def test_evolve_sim_uses_historical_scenarios_without_live_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_dir = root / "logs"
            log_dir.mkdir()
            (log_dir / "AGENT1.jsonl").write_text(json.dumps({
                "state": {
                    "phase": "SELECTING_HAND",
                    "ante": 1,
                    "score": 0,
                    "required_score": 300,
                    "money": 4,
                    "joker_keys": [],
                    "hand_cards": ["S_A", "H_A", "S_3", "H_5", "S_9"],
                    "deck_cards_remaining": 44,
                    "hands": 4,
                    "discards": 4,
                },
            }) + "\n")
            seed_config = root / "seeds.json"
            seed_config.write_text(json.dumps({"cohorts": {
                "dev": ["AGENT1"], "regression": ["REG1"], "heldout": ["HELD1"],
            }}))
            output_dir = root / "evolution"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = main([
                    "evolve", "--sim", "--sim-log-dir", str(log_dir),
                    "--seed-config", str(seed_config), "--output-dir", str(output_dir),
                    "--generations", "1", "--population", "2",
                ])

            self.assertEqual(result, 0)
            self.assertTrue((output_dir / "best_genome.json").exists())
            self.assertIn("fitness", json.loads(stdout.getvalue()))


if __name__ == "__main__":
    unittest.main()
