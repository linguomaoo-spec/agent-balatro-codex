from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from balatro_agent.analysis import compare_eval_summaries, summarize_jsonl_logs
from balatro_agent.measure import (
    SeedDistribution,
    aggregate_seed_distributions,
    distribution_gate,
)


class AutoEvolutionError(RuntimeError):
    pass


@dataclass
class AutoEvolutionConfig:
    root: Path
    mutator_command: str
    evaluator: Path
    test_command: str = "python3 -m unittest discover -s tests"
    run_root: Path = Path("runs/auto-evolve")
    # 阶段 0/3：用于估计噪声的 baseline 评估目录列表。提供后，dev cohort
    # 的晋升判断从"单次符号比较"升级为"effect-size 分布比较"，避免把单次
    # live 噪声当进步（2026-06-20 进化锯齿的根因）。None 时退回旧行为。
    baseline_eval_dirs: Optional[List[Path]] = None
    effect_threshold: float = 2.0
    min_samples: int = 2


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

        # 阶段 0/3：若提供 baseline 噪声分布，对 dev 用 effect-size 分布判断。
        # 这阻止"单次 live 噪声造成的伪改进"被晋升。
        dist_gate: Optional[Dict[str, Any]] = None
        if self.config.baseline_eval_dirs:
            base_dist = aggregate_seed_distributions(self.config.baseline_eval_dirs)
            cand_dist = _distributions_from_summary(candidate["dev"])
            dist_result = distribution_gate(
                base_dist,
                cand_dist,
                effect_threshold=self.config.effect_threshold,
                min_samples=self.config.min_samples,
            )
            dist_gate = dist_result.as_dict()
            if not dist_result.promote:
                # 分布判断要求"显著改进"才晋升；在噪声内或样本不足时拒绝
                dev_improved = False
                if "dev:significant_regression" in " ".join(dist_result.failed_checks):
                    failed.append("dev_distribution_regression")
                else:
                    failed.append("dev_within_noise_or_insufficient")

        if not dev_improved:
            failed.append("dev_not_improved")
        return {
            "promote": not failed,
            "failed_checks": failed,
            "dev_improved": dev_improved,
            "cohorts": gates,
            "distribution_gate": dist_gate,
        }

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


def _distributions_from_summary(summary: Dict[str, Any]) -> Dict[str, SeedDistribution]:
    """从一次 cohort 运行的 summarize_jsonl_logs 结果构建候选分布。

    候选通常为单次运行（n=1），用于与多次运行的 baseline 分布比较 effect size。
    """
    dist: Dict[str, SeedDistribution] = {}
    for run in summary.get("runs") or []:
        seed = Path(str(run.get("path") or "")).stem
        if not seed:
            continue
        score = int(run.get("final_score") or 0)
        d = dist.setdefault(seed, SeedDistribution(seed=seed))
        d.samples.append(score)
    return dist
