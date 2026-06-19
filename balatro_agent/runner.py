from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from balatro_agent.actions import GAME_OVER, ROUND_EVAL
from balatro_agent.client import BalatroBotClient, BalatroBotError
from balatro_agent.model import ActionProposal, GameState
from balatro_agent.orchestrator import DefaultOrchestrator
from balatro_agent.search import CheckpointSearchPlanner, SearchStateMismatch

TRANSIENT_PHASES = {"HAND_PLAYED", "DRAW_TO_HAND", "PLAY_TAROT", "NEW_ROUND"}
ROUND_EVAL_SETTLE_SECONDS = 2.0


class Runner:
    def __init__(
        self,
        client: BalatroBotClient,
        orchestrator: Optional[DefaultOrchestrator] = None,
        log_path: Optional[Path] = None,
        planner: Optional[CheckpointSearchPlanner] = None,
        scenario_library: Optional[Any] = None,
        seed: Optional[str] = None,
    ) -> None:
        self.client = client
        self.orchestrator = orchestrator or DefaultOrchestrator()
        self.log_path = log_path
        self.planner = planner
        self.scenario_library = scenario_library
        self.seed = seed

    def step(self) -> ActionProposal:
        state = GameState(self.client.gamestate())
        if state.phase == ROUND_EVAL:
            time.sleep(ROUND_EVAL_SETTLE_SECONDS)
        self._capture_scenario(state)
        decision = self.orchestrator.decide_with_details(state, search=self.planner is not None)
        search_summary: Optional[Dict[str, Any]] = None
        selected = decision.selected
        if self.planner is not None:
            choice = self.planner.choose(state, decision)
            selected = choice.selected
            search_summary = choice.summary
        error: Optional[Dict[str, Any]] = None
        transport_warning: Optional[Dict[str, Any]] = None
        try:
            self.client.execute(selected)
        except ConnectionError as exc:
            error = {
                "type": "connection",
                "message": str(exc),
            }
            if not self._action_applied(state):
                self._log(decision.as_log_record(), selected, error, search_summary)
                return selected
            transport_warning = error
            error = None
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
        self._log(
            decision.as_log_record(),
            selected,
            error,
            search_summary,
            transport_warning,
        )
        return selected

    def run(self, max_steps: int = 500, sleep_seconds: float = 0.05) -> Dict[str, Any]:
        steps = 0
        last_action: Optional[ActionProposal] = None
        while steps < max_steps:
            state = GameState(self.client.gamestate())
            if state.phase == GAME_OVER:
                self._log_terminal(state, last_action)
                status = "game_over"
                if state.won is True:
                    status = "game_over_win"
                elif state.won is False:
                    status = "game_over_loss"
                return {"status": status, "steps": steps, "state": state.summary()}
            if state.phase in TRANSIENT_PHASES:
                if sleep_seconds:
                    time.sleep(sleep_seconds)
                continue
            if state.phase == ROUND_EVAL:
                time.sleep(ROUND_EVAL_SETTLE_SECONDS)
            self._capture_scenario(state)
            decision = self.orchestrator.decide_with_details(state, search=self.planner is not None)
            search_summary: Optional[Dict[str, Any]] = None
            last_action = decision.selected
            if self.planner is not None:
                try:
                    choice = self.planner.choose(state, decision)
                except SearchStateMismatch as exc:
                    error = {
                        "type": "search_state_mismatch",
                        "message": str(exc),
                    }
                    self._log(decision.as_log_record(), last_action, error)
                    return {
                        "status": "infra_error",
                        "steps": steps,
                        "state": state.summary(),
                        "error": error,
                    }
                last_action = choice.selected
                search_summary = choice.summary
            error: Optional[Dict[str, Any]] = None
            transport_warning: Optional[Dict[str, Any]] = None
            try:
                self.client.execute(last_action)
            except BalatroBotError as exc:
                # pack 选择失败（如需要目标牌但手牌不足）→ 自动跳过
                if last_action.method == "pack" and not last_action.params.get("skip"):
                    try:
                        self.client.execute(
                            ActionProposal("pack", {"skip": True}, 0, "fallback",
                                           reasons=["pack选择失败，兜底跳过"]))
                    except Exception:
                        pass
                error = {
                    "type": "balatrobot",
                    "message": str(exc),
                }
                self._log(decision.as_log_record(), last_action, error)
                if sleep_seconds:
                    time.sleep(sleep_seconds)
                continue
            except ConnectionError as exc:
                error = {
                    "type": "connection",
                    "message": str(exc),
                }
                if not self._action_applied(state):
                    self._log(decision.as_log_record(), last_action, error)
                    if sleep_seconds:
                        time.sleep(sleep_seconds)
                    continue
                transport_warning = error
                error = None
            self._log(
                decision.as_log_record(),
                last_action,
                error,
                search_summary,
                transport_warning,
            )
            steps += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)
        final_state = GameState(self.client.gamestate())
        return {
            "status": "max_steps",
            "steps": steps,
            "last_action": last_action.as_dict() if last_action else None,
            "state": final_state.summary(),
        }

    def _capture_scenario(self, state: GameState) -> None:
        if self.scenario_library is not None:
            self.scenario_library.capture(self.client, state, self.seed)

    def _recover(self, state: GameState, failed: ActionProposal) -> Optional[ActionProposal]:
        if failed.method == "reroll":
            return ActionProposal("next_round", {}, -1.0, "recovery", reasons=["重掷失败"])
        if failed.method == "buy":
            return ActionProposal("next_round", {}, -1.0, "recovery", reasons=["购买失败"])
        if failed.method == "discard" and state.hand:
            return ActionProposal("play", {"cards": [0]}, -1.0, "recovery", reasons=["弃牌失败"])
        return None

    def _log_terminal(self, state: GameState, last_action: Optional[ActionProposal]) -> None:
        if self.log_path is None:
            return
        terminal_action = last_action or ActionProposal(
            "game_over",
            {},
            0.0,
            "runner",
            reasons=["记录终局状态"],
        )
        self._log(
            {
                "state": state.summary(),
                "action": terminal_action.as_dict(),
                "proposals": [],
                "rejected": [],
                "terminal": True,
            },
            terminal_action,
            None,
        )

    def _log(
        self,
        record: Dict[str, Any],
        executed: ActionProposal,
        error: Optional[Dict[str, Any]],
        search: Optional[Dict[str, Any]] = None,
        transport_warning: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        record = dict(record)
        record["executed"] = executed.as_dict()
        if search is not None:
            record["search"] = search
        if error:
            record["error"] = error
        if transport_warning:
            record["transport_warning"] = transport_warning
        with self.log_path.open("a") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def _action_applied(self, previous_state: GameState, settle_seconds: float = 0.2) -> bool:
        if settle_seconds:
            time.sleep(settle_seconds)
        try:
            current_state = GameState(self.client.gamestate())
        except ConnectionError:
            return False
        return current_state.raw != previous_state.raw
