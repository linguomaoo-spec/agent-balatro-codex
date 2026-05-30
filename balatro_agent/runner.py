from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from balatro_agent.actions import GAME_OVER
from balatro_agent.client import BalatroBotClient, BalatroBotError
from balatro_agent.model import ActionProposal, GameState
from balatro_agent.orchestrator import DefaultOrchestrator


class Runner:
    def __init__(
        self,
        client: BalatroBotClient,
        orchestrator: Optional[DefaultOrchestrator] = None,
        log_path: Optional[Path] = None,
    ) -> None:
        self.client = client
        self.orchestrator = orchestrator or DefaultOrchestrator()
        self.log_path = log_path

    def step(self) -> ActionProposal:
        state = GameState(self.client.gamestate())
        decision = self.orchestrator.decide_with_details(state)
        selected = decision.selected
        error: Optional[Dict[str, Any]] = None
        try:
            self.client.execute(selected)
        except BalatroBotError as exc:
            error = {
                "code": exc.code,
                "name": exc.name,
                "message": exc.message,
                "data": exc.data,
            }
            recovery = self._recover(state, selected)
            if recovery is not None:
                selected = recovery
                self.client.execute(selected)
        self._log(decision.as_log_record(), selected, error)
        return selected

    def run(self, max_steps: int = 500, sleep_seconds: float = 0.05) -> Dict[str, Any]:
        steps = 0
        last_action: Optional[ActionProposal] = None
        while steps < max_steps:
            state = GameState(self.client.gamestate())
            if state.phase == GAME_OVER:
                status = "game_over"
                if state.won is True:
                    status = "game_over_win"
                elif state.won is False:
                    status = "game_over_loss"
                return {"status": status, "steps": steps, "state": state.summary()}
            decision = self.orchestrator.decide_with_details(state)
            last_action = decision.selected
            self.client.execute(last_action)
            self._log(decision.as_log_record(), last_action, None)
            steps += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)
        return {
            "status": "max_steps",
            "steps": steps,
            "last_action": last_action.as_dict() if last_action else None,
        }

    def _recover(self, state: GameState, failed: ActionProposal) -> Optional[ActionProposal]:
        if failed.method == "reroll":
            return ActionProposal("next_round", {}, -1.0, "recovery", reasons=["重掷失败"])
        if failed.method == "buy":
            return ActionProposal("next_round", {}, -1.0, "recovery", reasons=["购买失败"])
        if failed.method == "discard" and state.hand:
            return ActionProposal("play", {"cards": [0]}, -1.0, "recovery", reasons=["弃牌失败"])
        return None

    def _log(
        self,
        record: Dict[str, Any],
        executed: ActionProposal,
        error: Optional[Dict[str, Any]],
    ) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        record = dict(record)
        record["executed"] = executed.as_dict()
        if error:
            record["error"] = error
        with self.log_path.open("a") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
