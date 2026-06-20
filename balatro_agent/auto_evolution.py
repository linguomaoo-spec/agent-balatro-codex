from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from balatro_agent.analysis import compare_eval_summaries, summarize_jsonl_logs


class AutoEvolutionError(RuntimeError):
    pass


@dataclass
class AutoEvolutionConfig:
    root: Path
    mutator_command: str
    evaluator: Path
    test_command: str = "python3 -m unittest discover -s tests"
    run_root: Path = Path("runs/auto-evolve")


class AutoEvolution:
    """Execute one unrestricted candidate change on the current branch."""

    cohorts: Sequence[str] = ("dev", "regression", "heldout")

    def __init__(self, config: AutoEvolutionConfig) -> None:
        self.config = config
        self.root = config.root.resolve()
        self.run_root = (self.root / config.run_root).resolve() if not config.run_root.is_absolute() else config.run_root

    def run(self) -> Dict[str, Any]:
        self._require_clean_tracked_tree()
        baseline_commit = self._git("rev-parse", "HEAD").strip()
        initial_untracked = set(self._untracked())
        round_root = self.run_root / "round-1"
        baseline = self._evaluate_all(round_root / "baseline")

        mutation = self._shell(self.config.mutator_command, baseline_commit)
        if mutation.returncode != 0:
            return self._revert(baseline_commit, "mutator_failed", baseline, mutation)

        tests = self._shell(self.config.test_command, baseline_commit)
        if tests.returncode != 0:
            return self._revert(baseline_commit, "tests_failed", baseline, tests)

        try:
            candidate = self._evaluate_all(round_root / "candidate")
        except AutoEvolutionError as exc:
            return self._revert(baseline_commit, "evaluation_failed", baseline, {"error": str(exc)})
        gate = self._gate(baseline, candidate)
        if not gate["promote"]:
            return self._revert(baseline_commit, "evaluation_failed", baseline, gate)

        self._stage_candidate(initial_untracked)
        if not self._has_staged_changes():
            return self._revert(baseline_commit, "no_candidate_changes", baseline, gate)
        self._git("commit", "-m", "auto-evolve: promote round 1")
        return {
            "status": "promoted",
            "baseline_commit": baseline_commit,
            "commit": self._git("rev-parse", "HEAD").strip(),
            "baseline": baseline,
            "candidate": candidate,
            "gate": gate,
        }

    def _evaluate_all(self, root: Path) -> Dict[str, Dict[str, Any]]:
        summaries: Dict[str, Dict[str, Any]] = {}
        for cohort in self.cohorts:
            log_dir = root / cohort
            result = self._run((str(self.config.evaluator), cohort, str(log_dir)))
            if result.returncode != 0:
                raise AutoEvolutionError(f"evaluator failed for {cohort}: {result.stderr.strip()}")
            summaries[cohort] = summarize_jsonl_logs(log_dir)
            (root / f"{cohort}-summary.json").write_text(
                json.dumps(summaries[cohort], indent=2, sort_keys=True) + "\n"
            )
        return summaries

    def _gate(self, baseline: Dict[str, Dict[str, Any]], candidate: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        gates = {
            cohort: compare_eval_summaries(baseline[cohort], candidate[cohort], cohort=cohort)
            for cohort in self.cohorts
        }
        dev_improved = (
            candidate["dev"]["win_rate"] > baseline["dev"]["win_rate"]
            or candidate["dev"]["max_ante"] > baseline["dev"]["max_ante"]
        )
        failed = [cohort for cohort, result in gates.items() if not result["promote"]]
        if not dev_improved:
            failed.append("dev_not_improved")
        return {"promote": not failed, "failed_checks": failed, "dev_improved": dev_improved, "cohorts": gates}

    def _revert(self, baseline_commit: str, reason: str, baseline: Dict[str, Any], detail: Any) -> Dict[str, Any]:
        self._git("reset", "--hard", baseline_commit)
        return {"status": "reverted", "baseline_commit": baseline_commit, "reason": reason, "baseline": baseline, "detail": self._detail(detail)}

    def _stage_candidate(self, initial_untracked: set[str]) -> None:
        tracked = self._git("diff", "--name-only").splitlines()
        new_files = [path for path in self._untracked() if path not in initial_untracked and not self._inside_run_root(path)]
        paths = [path for path in tracked + new_files if path]
        if paths:
            self._git("add", "--", *paths)

    def _inside_run_root(self, path: str) -> bool:
        try:
            (self.root / path).resolve().relative_to(self.run_root)
            return True
        except ValueError:
            return False

    def _require_clean_tracked_tree(self) -> None:
        if self._run(("git", "diff", "--quiet")).returncode != 0 or self._run(("git", "diff", "--cached", "--quiet")).returncode != 0:
            raise AutoEvolutionError("auto-evolve requires no tracked, uncommitted changes")

    def _has_staged_changes(self) -> bool:
        return self._run(("git", "diff", "--cached", "--quiet")).returncode != 0

    def _untracked(self) -> List[str]:
        return [path for path in self._git("ls-files", "--others", "--exclude-standard").splitlines() if path]

    def _git(self, *args: str) -> str:
        result = self._run(("git", *args))
        if result.returncode != 0:
            raise AutoEvolutionError(result.stderr.strip() or "git command failed")
        return result.stdout

    def _shell(self, command: str, baseline_commit: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update({"AUTO_EVOLVE_ROOT": str(self.root), "AUTO_EVOLVE_BASELINE_COMMIT": baseline_commit, "AUTO_EVOLVE_ROUND": "1"})
        return subprocess.run(command, cwd=self.root, env=env, shell=True, text=True, capture_output=True, check=False)

    def _run(self, command: Iterable[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(list(command), cwd=self.root, text=True, capture_output=True, check=False)

    @staticmethod
    def _detail(detail: Any) -> Any:
        if isinstance(detail, subprocess.CompletedProcess):
            return {"returncode": detail.returncode, "stdout": detail.stdout, "stderr": detail.stderr}
        return detail
