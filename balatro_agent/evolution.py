from __future__ import annotations

import json
import random
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from balatro_agent.client import BalatroBotClient, BalatroBotError
from balatro_agent.model import Genome, GameState
from balatro_agent.orchestrator import DefaultOrchestrator
from balatro_agent.runner import Runner
from balatro_agent.search import CheckpointSearchPlanner, SearchConfig


RunFactory = Callable[[Genome, Optional[str], Optional[Path]], Dict[str, Any]]


@dataclass(frozen=True)
class RunOutcome:
    seed: str
    won: bool
    ante: int
    completion: float
    errors: int
    steps: int
    rejected: int = 0
    alive: bool = False

    @classmethod
    def from_run(cls, seed: str, run: Dict[str, Any]) -> "RunOutcome":
        state = run.get("state") or {}
        score = float(state.get("score", 0) or run.get("score", 0) or 0)
        required = float(state.get("required_score", 0) or run.get("required_score", 0) or 0)
        completion = min(1.0, score / required) if required > 0 else 0.0
        error_count = int(run.get("error_count", 0) or (1 if run.get("error") else 0))
        won = _run_won(run)
        status = str(run.get("status") or "")
        phase = str(state.get("phase") or state.get("state") or "").upper()
        terminal = status.startswith("game_over") or phase == "GAME_OVER"
        return cls(
            seed=seed,
            won=won,
            ante=int(state.get("ante", 0) or run.get("ante", 0) or 0),
            completion=completion,
            errors=error_count,
            steps=int(run.get("steps", 0) or 0),
            rejected=int(run.get("rejected_count", 0) or 0),
            alive=not won and not terminal and error_count == 0,
        )

    @property
    def rank_key(self) -> Tuple[int, int, float, int, int]:
        outcome_rank = 2 if self.won else 1 if self.alive else 0
        return (
            outcome_rank,
            self.ante,
            self.completion,
            -(self.errors + self.rejected),
            -self.steps,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "won": self.won,
            "ante": self.ante,
            "completion": self.completion,
            "errors": self.errors,
            "steps": self.steps,
            "rejected": self.rejected,
            "alive": self.alive,
        }


@dataclass
class EvalResult:
    genome: Genome
    runs: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def score(self) -> float:
        outcomes = list(self.outcomes.values())
        if not outcomes:
            return 0.0
        scores = [
            (2 if outcome.won else 1 if outcome.alive else 0) * 1000.0
            + outcome.ante * 20.0
            + outcome.completion * 10.0
            - outcome.errors * 5.0
            - outcome.rejected * 5.0
            - outcome.steps * 0.001
            for outcome in outcomes
        ]
        return statistics.mean(scores)

    @property
    def outcomes(self) -> Dict[str, RunOutcome]:
        result: Dict[str, RunOutcome] = {}
        for index, run in enumerate(self.runs):
            seed = str(run.get("seed") or f"run_{index}")
            result[seed] = RunOutcome.from_run(seed, run)
        return result

    @property
    def fitness_key(self) -> Tuple[int, int, float, float, float, int, int]:
        outcomes = list(self.outcomes.values())
        if not outcomes:
            return (0, 0, 0.0, 0.0, 0.0, 0, 0)
        antes = [outcome.ante for outcome in outcomes]
        completion = [outcome.completion for outcome in outcomes]
        return (
            sum(1 for outcome in outcomes if outcome.won),
            min(antes),
            statistics.mean(antes),
            min(completion),
            statistics.mean(completion),
            -sum(outcome.errors for outcome in outcomes),
            -sum(outcome.steps for outcome in outcomes),
        )

    def dominates(self, other: "EvalResult") -> bool:
        own = self.outcomes
        theirs = other.outcomes
        if set(own) != set(theirs) or not own:
            return False
        comparisons = [own[seed].rank_key >= theirs[seed].rank_key for seed in own]
        improvements = [own[seed].rank_key > theirs[seed].rank_key for seed in own]
        return all(comparisons) and any(improvements)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "fitness": list(self.fitness_key),
            "outcomes": [outcome.as_dict() for outcome in self.outcomes.values()],
            "genome": json.loads(self.genome.to_json()),
            "runs": self.runs,
        }


@dataclass
class ParetoArchive:
    results: List[EvalResult] = field(default_factory=list)

    def add(self, candidate: EvalResult) -> None:
        if any(existing.dominates(candidate) for existing in self.results):
            return
        self.results = [existing for existing in self.results if not candidate.dominates(existing)]
        if not any(existing.outcomes == candidate.outcomes for existing in self.results):
            self.results.append(candidate)
        self.results.sort(key=lambda result: result.fitness_key, reverse=True)


class EvolutionEngine:
    def __init__(
        self,
        run_factory: RunFactory,
        rng: Optional[random.Random] = None,
        scenario_run_factory: Optional[RunFactory] = None,
    ) -> None:
        self.run_factory = run_factory
        self.scenario_run_factory = scenario_run_factory or run_factory
        self.rng = rng or random.Random()

    def evaluate(
        self,
        genome: Genome,
        seeds: List[Optional[str]],
        log_dir: Optional[Path] = None,
    ) -> EvalResult:
        return self._evaluate_with(self.run_factory, genome, seeds, log_dir)

    def _evaluate_with(
        self,
        run_factory: RunFactory,
        genome: Genome,
        seeds: List[Optional[str]],
        log_dir: Optional[Path] = None,
    ) -> EvalResult:
        runs: List[Dict[str, Any]] = []
        for seed in seeds:
            log_path = None
            if log_dir is not None:
                seed_label = seed or f"run_{len(runs)}"
                log_path = log_dir / f"{seed_label}.jsonl"
            run = run_factory(genome, seed, log_path)
            run.setdefault("seed", seed)
            runs.append(run)
        return EvalResult(genome, runs)

    def evolve(
        self,
        base: Genome,
        generations: int,
        population: int,
        seeds: List[Optional[str]],
        output_dir: Path,
    ) -> EvalResult:
        best = self.evaluate(base, seeds, output_dir / "generation_0" / "base")
        best.genome.save(output_dir / "generation_0" / "best_genome.json")

        current = best.genome
        for generation in range(1, generations + 1):
            generation_dir = output_dir / f"generation_{generation}"
            candidates = [current] + [
                current.mutated(self.rng, sigma=0.15) for _ in range(max(0, population - 1))
            ]
            results = [
                self.evaluate(candidate, seeds, generation_dir / f"candidate_{index}")
                for index, candidate in enumerate(candidates)
            ]
            results.sort(key=lambda result: result.fitness_key, reverse=True)
            best = results[0]
            current = best.genome
            generation_dir.mkdir(parents=True, exist_ok=True)
            (generation_dir / "scores.json").write_text(
                json.dumps([result.as_dict() for result in results], indent=2, sort_keys=True)
                + "\n"
            )
            best.genome.save(generation_dir / "best_genome.json")
        return best

    def evolve_staged(
        self,
        base: Genome,
        generations: int,
        population: int,
        scenario_seeds: Any,
        dev_seeds: List[Optional[str]],
        regression_seeds: List[Optional[str]],
        heldout_seeds: List[Optional[str]],
        output_dir: Path,
        dev_finalists: int = 3,
        regression_finalists: int = 2,
    ) -> EvalResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        archive = ParetoArchive()
        fitness_log: List[Dict[str, Any]] = []
        baseline_dev = self.evaluate(base, dev_seeds, output_dir / "baseline" / "dev")
        archive.add(baseline_dev)
        all_dev_results = [baseline_dev]
        resolved_scenarios = scenario_seeds() if callable(scenario_seeds) else scenario_seeds

        elites = [base]
        for generation in range(1, generations + 1):
            generation_dir = output_dir / f"generation_{generation}"
            candidates = self._candidate_population(elites, population)
            scenario_results = [
                self._evaluate_with(
                    self.scenario_run_factory,
                    candidate,
                    resolved_scenarios,
                    generation_dir / f"candidate_{index}" / "scenarios",
                )
                for index, candidate in enumerate(candidates)
            ]
            scenario_results.sort(key=lambda result: result.fitness_key, reverse=True)
            promoted = scenario_results[: min(dev_finalists, len(scenario_results))]
            dev_results = [
                self.evaluate(result.genome, dev_seeds, generation_dir / f"finalist_{index}" / "dev")
                for index, result in enumerate(promoted)
            ]
            for result in dev_results:
                archive.add(result)
            all_dev_results.extend(dev_results)
            all_dev_results.sort(key=lambda result: result.fitness_key, reverse=True)
            elites = [result.genome for result in archive.results[:2]] or [base]
            fitness_log.append(
                {
                    "generation": generation,
                    "scenarios": [result.as_dict() for result in scenario_results],
                    "dev": [result.as_dict() for result in dev_results],
                }
            )

        baseline_regression = self.evaluate(
            base,
            regression_seeds,
            output_dir / "baseline" / "regression",
        )
        finalist_genomes = [
            result.genome
            for result in all_dev_results
            if result.genome.weights != base.weights
        ][:regression_finalists]
        if len(finalist_genomes) < regression_finalists:
            finalist_genomes.extend(
                result.genome
                for result in all_dev_results
                if result.genome not in finalist_genomes
            )
            finalist_genomes = finalist_genomes[:regression_finalists]
        regression_results = [
            self.evaluate(genome, regression_seeds, output_dir / "regression" / f"finalist_{index}")
            for index, genome in enumerate(finalist_genomes)
        ]
        gates = [passes_regression_gate(baseline_regression, result) for result in regression_results]
        eligible = [
            result
            for result, gate in zip(regression_results, gates)
            if gate["promote"]
        ]
        champion = max(eligible, key=lambda result: result.fitness_key) if eligible else baseline_regression
        heldout = self.evaluate(champion.genome, heldout_seeds, output_dir / "heldout")

        _write_json(output_dir / "fitness.json", fitness_log)
        _write_json(
            output_dir / "elite_archive.json",
            [result.as_dict() for result in archive.results],
        )
        _write_json(
            output_dir / "regression-gate.json",
            {
                "baseline": baseline_regression.as_dict(),
                "finalists": [
                    {"result": result.as_dict(), "gate": gate}
                    for result, gate in zip(regression_results, gates)
                ],
                "champion": champion.as_dict(),
            },
        )
        _write_json(output_dir / "heldout.json", heldout.as_dict())
        if not any(outcome.won for result in all_dev_results for outcome in result.outcomes.values()):
            best_failure = max(all_dev_results, key=lambda result: result.fitness_key)
            _write_json(
                output_dir / "failure-analysis.json",
                {
                    "reason": "no_dev_win_after_configured_generations",
                    "best": best_failure.as_dict(),
                    "scenario_count": len(resolved_scenarios),
                },
            )
        champion.genome.save(output_dir / "best_genome.json")
        return champion

    def _candidate_population(self, elites: List[Genome], population: int) -> List[Genome]:
        if population <= 0:
            return []
        candidates = list(elites[: min(len(elites), population)])
        if len(elites) >= 2 and len(candidates) < population:
            candidates.append(elites[0].crossover(elites[1], self.rng))
        while len(candidates) < population:
            parent = elites[self.rng.randrange(len(elites))]
            candidates.append(parent.mutated(self.rng, mutation_rate=0.3))
        return candidates


def passes_regression_gate(baseline: EvalResult, candidate: EvalResult) -> Dict[str, Any]:
    baseline_outcomes = baseline.outcomes
    candidate_outcomes = candidate.outcomes
    failures: List[str] = []
    per_seed: Dict[str, Dict[str, Any]] = {}
    if set(baseline_outcomes) != set(candidate_outcomes):
        failures.append("seed_set_mismatch")
    for seed in sorted(set(baseline_outcomes) & set(candidate_outcomes)):
        before = baseline_outcomes[seed]
        after = candidate_outcomes[seed]
        seed_failures: List[str] = []
        if before.won and not after.won:
            seed_failures.append("lost_win")
        if after.ante < before.ante:
            seed_failures.append("ante_regression")
        if after.errors > before.errors:
            seed_failures.append("error_increased")
        if after.rejected > before.rejected:
            seed_failures.append("rejected_increased")
        failures.extend(f"{seed}:{failure}" for failure in seed_failures)
        per_seed[seed] = {
            "baseline": before.as_dict(),
            "candidate": after.as_dict(),
            "failures": seed_failures,
        }
    return {"promote": not failures, "failures": failures, "per_seed": per_seed}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _run_won(run: Dict[str, Any]) -> bool:
    if run.get("status") == "game_over_win":
        return True
    state = run.get("state") or {}
    return state.get("won") is True


def make_live_run_factory(
    base_url: str,
    deck: str,
    stake: str,
    max_steps: int,
    timeout: float,
    search_config: Optional[SearchConfig] = None,
    scenario_library: Optional[Any] = None,
    elite_archive: Optional[Any] = None,
) -> RunFactory:
    def run_once(genome: Genome, seed: Optional[str], log_path: Optional[Path]) -> Dict[str, Any]:
        client = BalatroBotClient(base_url=base_url, timeout=timeout)
        if GameState(client.gamestate()).phase != "MENU":
            client.call("menu", {})
        start_error: Optional[ConnectionError] = None
        try:
            client.start(deck=deck, stake=stake, seed=seed)
        except ConnectionError as exc:
            start_error = exc
        started_state = _wait_for_started_run(client)
        if started_state is None:
            status = "start_error" if start_error else "start_timeout"
            result: Dict[str, Any] = {"status": status, "steps": 0, "seed": seed}
            if start_error:
                result["error"] = {"type": "connection", "message": str(start_error)}
            return result
        orchestrator = DefaultOrchestrator(genome)
        planner = None
        if search_config is not None:
            planner = CheckpointSearchPlanner(
                client,
                DefaultOrchestrator(genome),
                genome,
                search_config,
            )
        runner = Runner(
            client,
            orchestrator,
            log_path=log_path,
            planner=planner,
            scenario_library=scenario_library,
            seed=seed,
            elite_archive=elite_archive,
        )
        result = runner.run(max_steps=max_steps)
        result.setdefault("seed", seed)
        return result

    return run_once


def make_checkpoint_run_factory(
    base_url: str,
    max_steps: int,
    timeout: float,
    search_config: Optional[SearchConfig] = None,
) -> RunFactory:
    def run_once(genome: Genome, seed: Optional[str], log_path: Optional[Path]) -> Dict[str, Any]:
        if not seed:
            return {
                "status": "infra_error",
                "steps": 0,
                "seed": seed,
                "error": {"type": "missing_checkpoint"},
            }
        client = BalatroBotClient(base_url=base_url, timeout=timeout)
        checkpoint = Path(seed)
        try:
            client.load_checkpoint(checkpoint)
            state = _wait_for_loaded_checkpoint(client)
        except (ConnectionError, BalatroBotError, OSError) as exc:
            return {
                "status": "infra_error",
                "steps": 0,
                "seed": seed,
                "error": {"type": "checkpoint_load", "message": str(exc)},
            }
        if state is None:
            return {
                "status": "infra_error",
                "steps": 0,
                "seed": seed,
                "error": {"type": "checkpoint_timeout"},
            }
        orchestrator = DefaultOrchestrator(genome)
        planner = None
        if search_config is not None:
            planner = CheckpointSearchPlanner(
                client,
                DefaultOrchestrator(genome),
                genome,
                search_config,
            )
        runner = Runner(client, orchestrator, log_path=log_path, planner=planner)
        result = runner.run(max_steps=max_steps)
        result.setdefault("seed", seed)
        if "state" not in result:
            result["state"] = GameState(client.gamestate()).summary()
        return result

    return run_once


def _wait_for_started_run(
    client: BalatroBotClient,
    attempts: int = 50,
    sleep_seconds: float = 0.1,
) -> Optional[GameState]:
    for _ in range(attempts):
        try:
            state = GameState(client.gamestate())
        except ConnectionError:
            state = None
        if state is not None and state.phase != "MENU":
            return state
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return None


def _wait_for_loaded_checkpoint(
    client: BalatroBotClient,
    attempts: int = 50,
    sleep_seconds: float = 0.05,
) -> Optional[GameState]:
    for _ in range(attempts):
        try:
            state = GameState(client.gamestate())
        except ConnectionError:
            state = None
        if state is not None and state.phase not in {"MENU", "UNKNOWN"}:
            return state
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return None
