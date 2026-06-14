from __future__ import annotations

import hashlib
import json
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from balatro_agent.actions import BLIND_SELECT, BOOSTER_OPENED, GAME_OVER, ROUND_EVAL, SELECTING_HAND, SHOP
from balatro_agent.client import BalatroBotError
from balatro_agent.model import ActionProposal, Decision, GameState, Genome


ValueKey = Tuple[int, int, int, float, float]


class StateValue:
    """Lexicographic state value with non-negotiable outcome/progress priority."""

    def __init__(self, genome: Genome) -> None:
        self.genome = genome

    def evaluate(self, state: GameState) -> ValueKey:
        if state.phase == GAME_OVER:
            outcome = 2 if state.won is True else 0
        else:
            outcome = 1

        required = state.blind_requirement
        completion = min(1.0, state.score / required) if required > 0 else 0.0
        resources = (
            state.hands_remaining * self.genome.weight("value_hand", 1.0)
            + state.discards_remaining * self.genome.weight("value_discard", 0.5)
            + state.money * self.genome.weight("value_money", 0.02)
            + len(state.jokers) * self.genome.weight("value_joker", 0.5)
            + len(state.consumables) * self.genome.weight("value_consumable", 0.25)
        )
        if outcome == 0:
            resources = 0.0
        return (outcome, state.ante, state.round_number, completion, resources)


class SearchStateMismatch(RuntimeError):
    pass


@dataclass
class SearchConfig:
    normal_budget: int = 6
    priority_budget: int = 12
    horizons: Dict[str, int] = field(
        default_factory=lambda: {
            "SELECTING_HAND": 4,
            "SHOP": 6,
            "BLIND_SELECT": 4,
            BOOSTER_OPENED: 4,
        }
    )
    settle_attempts: int = 50
    settle_seconds: float = 0.05
    disable_after_failures: int = 2

    @classmethod
    def load(cls, path: Path) -> "SearchConfig":
        payload = json.loads(path.read_text())
        horizons = cls().horizons
        horizons.update({str(key): int(value) for key, value in payload.get("horizons", {}).items()})
        return cls(
            normal_budget=int(payload.get("normal_budget", 6)),
            priority_budget=int(payload.get("priority_budget", 12)),
            horizons=horizons,
            settle_attempts=int(payload.get("settle_attempts", 50)),
            settle_seconds=float(payload.get("settle_seconds", 0.05)),
            disable_after_failures=int(payload.get("disable_after_failures", 2)),
        )


@dataclass
class SearchChoice:
    selected: ActionProposal
    summary: Dict[str, Any]


class CheckpointScenarioLibrary:
    def __init__(self, root: Path, max_scenarios: int = 18) -> None:
        self.root = root
        self.max_scenarios = max_scenarios
        self.frozen = False
        self.entries: List[Dict[str, Any]] = []
        self._fingerprints: set[str] = set()
        manifest = self.root / "manifest.json"
        if manifest.exists():
            payload = json.loads(manifest.read_text())
            self.entries = list(payload.get("scenarios", []))
            self._fingerprints = {
                str(entry.get("fingerprint")) for entry in self.entries if entry.get("fingerprint")
            }

    def capture(self, client: Any, state: GameState, seed: Optional[str]) -> bool:
        category = self._category(state)
        if self.frozen or category is None or len(self.entries) >= self.max_scenarios:
            return False
        per_category_limit = max(1, self.max_scenarios // 6)
        if sum(1 for entry in self.entries if entry.get("category") == category) >= per_category_limit:
            return False
        fingerprint = CheckpointSearchPlanner._fingerprint(state)
        if fingerprint in self._fingerprints:
            return False
        self.root.mkdir(parents=True, exist_ok=True)
        index = len(self.entries) + 1
        path = self.root / f"{index:02d}-{category}.jkr"
        try:
            client.save_checkpoint(path)
        except (ConnectionError, BalatroBotError, OSError):
            return False
        entry = {
            "path": str(path.resolve()),
            "category": category,
            "seed": seed,
            "phase": state.phase,
            "ante": state.ante,
            "round": state.round_number,
            "fingerprint": fingerprint,
        }
        self.entries.append(entry)
        self._fingerprints.add(fingerprint)
        self._write_manifest()
        return True

    def checkpoints(self) -> List[str]:
        return [str(entry["path"]) for entry in self.entries]

    def freeze(self) -> List[str]:
        self.frozen = True
        return self.checkpoints()

    def _write_manifest(self) -> None:
        (self.root / "manifest.json").write_text(
            json.dumps({"scenarios": self.entries}, indent=2, sort_keys=True) + "\n"
        )

    @staticmethod
    def _category(state: GameState) -> Optional[str]:
        if CheckpointSearchPlanner._priority_state(state) and state.phase != SHOP:
            return "boss"
        if state.phase == SELECTING_HAND:
            return "hand"
        if state.phase == SHOP:
            return "shop_early" if state.ante <= 3 else "shop_late"
        if state.phase == BLIND_SELECT:
            return "blind_select"
        if state.phase == BOOSTER_OPENED:
            return "booster"
        return None


class CheckpointSearchPlanner:
    TRANSIENT_PHASES = {"HAND_PLAYED", "DRAW_TO_HAND", "PLAY_TAROT", "NEW_ROUND"}

    def __init__(
        self,
        client: Any,
        rollout_orchestrator: Any,
        genome: Genome,
        config: Optional[SearchConfig] = None,
    ) -> None:
        self.client = client
        self.rollout_orchestrator = rollout_orchestrator
        self.config = config or SearchConfig()
        self.state_value = StateValue(genome)
        self.checkpoint_failures = 0
        self.disabled = False

    def choose(self, state: GameState, decision: Decision) -> SearchChoice:
        candidates = self._deduplicated(decision.proposals)
        if self.disabled or len(candidates) <= 1:
            return SearchChoice(
                decision.selected,
                {
                    "candidate_count": len(candidates),
                    "evaluated_count": 0,
                    "branches": [],
                    "fallback_reason": "search_disabled" if self.disabled else "single_candidate",
                },
            )

        budget = self.config.priority_budget if self._priority_state(state) else self.config.normal_budget
        candidates = candidates[: max(1, budget)]
        started = time.monotonic()
        root_fingerprint = self._fingerprint(state)
        branches: List[Dict[str, Any]] = []
        best_action = decision.selected
        best_value: Optional[ValueKey] = None

        with tempfile.TemporaryDirectory(prefix="balatro-search-") as tmp:
            checkpoint = Path(tmp) / "root.jkr"
            try:
                self.client.save_checkpoint(checkpoint)
            except (ConnectionError, BalatroBotError, OSError) as exc:
                self._record_checkpoint_failure()
                return SearchChoice(
                    decision.selected,
                    {
                        "candidate_count": len(candidates),
                        "evaluated_count": 0,
                        "branches": [],
                        "fallback_reason": "checkpoint_save_failed",
                        "error": str(exc),
                    },
                )

            for candidate in candidates:
                try:
                    self.client.load_checkpoint(checkpoint)
                    branch_state = self._settled_state()
                except (ConnectionError, BalatroBotError, OSError) as exc:
                    self._record_checkpoint_failure()
                    branches.append(
                        {
                            "action": candidate.as_dict(),
                            "rollout_steps": 0,
                            "error": str(exc),
                        }
                    )
                    if self.disabled:
                        break
                    continue
                self.checkpoint_failures = 0
                try:
                    self.client.execute(candidate)
                    branch_state = self._settled_state()
                    rollout_steps = 0
                    horizon = max(0, self.config.horizons.get(state.phase, 4))
                    while rollout_steps < horizon and branch_state.phase not in {GAME_OVER, ROUND_EVAL}:
                        rollout_decision = self.rollout_orchestrator.decide_with_details(branch_state)
                        self.client.execute(rollout_decision.selected)
                        branch_state = self._settled_state()
                        rollout_steps += 1
                    value = self.state_value.evaluate(branch_state)
                    branch = {
                        "action": candidate.as_dict(),
                        "value": list(value),
                        "rollout_steps": rollout_steps,
                    }
                    branches.append(branch)
                    if best_value is None or value > best_value:
                        best_value = value
                        best_action = candidate
                except (ConnectionError, BalatroBotError, OSError) as exc:
                    branches.append(
                        {
                            "action": candidate.as_dict(),
                            "rollout_steps": 0,
                            "error": str(exc),
                        }
                    )

            try:
                self.client.load_checkpoint(checkpoint)
                restored = self._settled_state()
            except (ConnectionError, BalatroBotError, OSError) as exc:
                self._record_checkpoint_failure()
                raise SearchStateMismatch(f"checkpoint 最终恢复失败：{exc}") from exc
            if self._fingerprint(restored) != root_fingerprint:
                self._record_checkpoint_failure()
                raise SearchStateMismatch("checkpoint 恢复后的状态与根状态不一致")

        self.checkpoint_failures = 0
        return SearchChoice(
            best_action,
            {
                "candidate_count": len(self._deduplicated(decision.proposals)),
                "evaluated_count": len(branches),
                "branches": branches,
                "selected": best_action.as_dict(),
                "elapsed_ms": round((time.monotonic() - started) * 1000.0, 3),
            },
        )

    def _settled_state(self) -> GameState:
        state = GameState(self.client.gamestate())
        for _ in range(max(1, self.config.settle_attempts) - 1):
            if state.phase not in self.TRANSIENT_PHASES:
                return state
            if self.config.settle_seconds:
                time.sleep(self.config.settle_seconds)
            state = GameState(self.client.gamestate())
        return state

    def _record_checkpoint_failure(self) -> None:
        self.checkpoint_failures += 1
        if self.checkpoint_failures >= self.config.disable_after_failures:
            self.disabled = True

    @staticmethod
    def _deduplicated(proposals: List[ActionProposal]) -> List[ActionProposal]:
        unique: Dict[str, ActionProposal] = {}
        for proposal in sorted(proposals, key=lambda item: (item.score, item.confidence), reverse=True):
            key = json.dumps(
                {"method": proposal.method, "params": proposal.params},
                sort_keys=True,
                separators=(",", ":"),
            )
            unique.setdefault(key, proposal)
        return list(unique.values())

    @staticmethod
    def _priority_state(state: GameState) -> bool:
        if state.phase == SHOP:
            return True
        blind = state.raw.get("blind") if isinstance(state.raw, dict) else None
        if isinstance(blind, dict) and bool(blind.get("boss")):
            return True
        blinds = state.raw.get("blinds") if isinstance(state.raw, dict) else None
        if not isinstance(blinds, dict):
            return False
        return any(
            isinstance(item, dict)
            and str(item.get("status") or "").upper() == "CURRENT"
            and str(item.get("type") or "").upper() == "BOSS"
            for item in blinds.values()
        )

    @staticmethod
    def _fingerprint(state: GameState) -> str:
        payload = json.dumps(state.summary(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
