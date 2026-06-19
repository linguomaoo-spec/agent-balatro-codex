from __future__ import annotations
from typing import List
from balatro_agent.actions import BLIND_SELECT, ROUND_EVAL
from balatro_agent.agents.base import Agent
from balatro_agent.model import ActionProposal, GameState, Genome


class RoundAgent(Agent):
    name = "round"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase == ROUND_EVAL:
            return [ActionProposal("cash_out", {}, 1000.0, self.name, reasons=["回合结算"])]
        if state.phase == BLIND_SELECT:
            return [ActionProposal("select", {}, 1000.0, self.name, reasons=["默认选择盲注"])]
        return []
