from __future__ import annotations

import json
import random
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from balatro_agent.client import BalatroBotClient
from balatro_agent.model import Genome
from balatro_agent.orchestrator import DefaultOrchestrator
from balatro_agent.runner import Runner


RunFactory = Callable[[Genome, Optional[str], Optional[Path]], Dict[str, Any]]


@dataclass
class EvalResult:
    genome: Genome
    runs: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def score(self) -> float:
        if not self.runs:
            return 0.0
        scores = []
        for run in self.runs:
            state = run.get("state") or {}
            ante = float(state.get("ante", 0) or run.get("ante", 0) or 0)
            steps = float(run.get("steps", 0) or 0)
            final_score = float(state.get("score", 0) or run.get("score", 0) or 0)
            money = float(state.get("money", 0) or 0)
            jokers = float(state.get("jokers", 0) or state.get("joker_count", 0) or 0)
            status_bonus = 100.0 if _run_won(run) else 0.0
            scores.append(
                status_bonus
                + ante * 20.0
                + steps * 0.02
                + final_score * 0.002
                + money * 0.05
                + jokers * 1.5
            )
        return statistics.mean(scores)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "genome": json.loads(self.genome.to_json()),
            "runs": self.runs,
        }


class EvolutionEngine:
    def __init__(self, run_factory: RunFactory, rng: Optional[random.Random] = None) -> None:
        self.run_factory = run_factory
        self.rng = rng or random.Random()

    def evaluate(
        self,
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
            runs.append(self.run_factory(genome, seed, log_path))
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
            results.sort(key=lambda result: result.score, reverse=True)
            best = results[0]
            current = best.genome
            generation_dir.mkdir(parents=True, exist_ok=True)
            (generation_dir / "scores.json").write_text(
                json.dumps([result.as_dict() for result in results], indent=2, sort_keys=True)
                + "\n"
            )
            best.genome.save(generation_dir / "best_genome.json")
        return best


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
) -> RunFactory:
    def run_once(genome: Genome, seed: Optional[str], log_path: Optional[Path]) -> Dict[str, Any]:
        client = BalatroBotClient(base_url=base_url, timeout=timeout)
        client.call("menu", {})
        client.start(deck=deck, stake=stake, seed=seed)
        runner = Runner(client, DefaultOrchestrator(genome), log_path=log_path)
        return runner.run(max_steps=max_steps)

    return run_once
