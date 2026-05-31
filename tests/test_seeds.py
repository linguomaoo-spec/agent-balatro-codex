import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from balatro_agent.cli import main
from balatro_agent.seeds import load_seed_config, resolve_seed_list


class SeedConfigTests(unittest.TestCase):
    def test_load_seed_config_reads_named_cohorts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seeds.json"
            path.write_text(
                json.dumps(
                    {
                        "cohorts": {
                            "dev": ["AGENT1", "AGENT2"],
                            "regression": ["AGENT3"],
                            "heldout": ["AGENT4"],
                        }
                    }
                )
            )

            config = load_seed_config(path)

        self.assertEqual(config["cohorts"]["dev"], ["AGENT1", "AGENT2"])

    def test_resolve_seed_list_prefers_explicit_seeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seeds.json"
            path.write_text(json.dumps({"cohorts": {"dev": ["AGENT1"]}}))

            seeds = resolve_seed_list(["CUSTOM"], path, "dev")

        self.assertEqual(seeds, ["CUSTOM"])

    def test_resolve_seed_list_uses_named_cohort(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seeds.json"
            path.write_text(json.dumps({"cohorts": {"regression": ["AGENT4", "AGENT5"]}}))

            seeds = resolve_seed_list([], path, "regression")

        self.assertEqual(seeds, ["AGENT4", "AGENT5"])

    def test_seed_cohorts_cli_outputs_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seeds.json"
            path.write_text(json.dumps({"cohorts": {"dev": ["AGENT1"]}}))
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = main(["seed-cohorts", "--seed-config", str(path)])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(payload["cohorts"]["dev"], ["AGENT1"])


if __name__ == "__main__":
    unittest.main()
