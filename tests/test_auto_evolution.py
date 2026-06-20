import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from balatro_agent.cli import main


class AutoEvolutionTests(unittest.TestCase):
    def _repository(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        (root / "strategy.txt").write_text("baseline\n")
        subprocess.run(["git", "add", "strategy.txt"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)

    def _write_evaluator(self, root: Path) -> Path:
        evaluator = root / "evaluate.py"
        evaluator.write_text(
            """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

cohort, log_dir = sys.argv[1:]
improved = Path('strategy.txt').read_text().strip() == 'candidate'
won = improved
payload = {"state": {"phase": "GAME_OVER", "ante": 9 if improved else 8, "won": won}, "action": {"method": "play"}, "executed": {"method": "play"}}
path = Path(log_dir)
path.mkdir(parents=True, exist_ok=True)
(path / f"{cohort}.jsonl").write_text(json.dumps(payload) + "\\n")
"""
        )
        evaluator.chmod(0o755)
        return evaluator

    def _run(self, root: Path, mutator: str) -> dict:
        evaluator = self._write_evaluator(root)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = main(
                [
                    "auto-evolve",
                    "--root", str(root),
                    "--mutator-command", mutator,
                    "--evaluator", str(evaluator),
                    "--test-command", "true",
                    "--run-root", str(root / "runs"),
                ]
            )
        self.assertEqual(result, 0)
        return json.loads(stdout.getvalue())

    def test_auto_evolve_commits_an_improved_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repository(root)

            result = self._run(root, "printf 'candidate\\n' > strategy.txt")

            self.assertEqual(result["status"], "promoted")
            self.assertEqual((root / "strategy.txt").read_text(), "candidate\n")
            subject = subprocess.check_output(["git", "log", "-1", "--format=%s"], cwd=root, text=True).strip()
            self.assertEqual(subject, "auto-evolve: promote round 1")

    def test_auto_evolve_restores_baseline_when_candidate_does_not_improve(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repository(root)
            before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()

            result = self._run(root, "printf 'unchanged-quality\\n' > strategy.txt")

            self.assertEqual(result["status"], "reverted")
            self.assertEqual((root / "strategy.txt").read_text(), "baseline\n")
            after = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            self.assertEqual(after, before)

    def test_auto_evolve_restores_baseline_when_candidate_evaluation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repository(root)
            evaluator = root / "evaluate.py"
            evaluator.write_text(
                """#!/usr/bin/env python3
import sys
from pathlib import Path
if Path('strategy.txt').read_text().strip() == 'candidate':
    raise SystemExit(1)
Path(sys.argv[2]).mkdir(parents=True, exist_ok=True)
Path(sys.argv[2], 'seed.jsonl').write_text('{\"state\": {\"phase\": \"GAME_OVER\", \"ante\": 8, \"won\": false}}\\n')
"""
            )
            evaluator.chmod(0o755)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                result = main(
                    [
                        "auto-evolve", "--root", str(root),
                        "--mutator-command", "printf 'candidate\\n' > strategy.txt",
                        "--evaluator", str(evaluator), "--test-command", "true",
                        "--run-root", str(root / "runs"),
                    ]
                )

            self.assertEqual(result, 0)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "reverted")
            self.assertEqual((root / "strategy.txt").read_text(), "baseline\n")
