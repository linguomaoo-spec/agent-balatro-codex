from __future__ import annotations
from typing import List
from balatro_agent.actions import BOOSTER_OPENED
from balatro_agent.agents.base import Agent
from balatro_agent.model import ActionProposal, GameState, Genome


class BoosterAgent(Agent):
    name = "booster"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase != BOOSTER_OPENED:
            return []
        choices = state.booster_choices()
        if choices:
            return [
                ActionProposal(
                    "pack",
                    {"card": 0},
                    5.0,
                    self.name,
                    reasons=["保守基线：选择第一个补充包选项"],
                )
            ]
        return [
            ActionProposal(
                "pack",
                {"skip": True},
                1.0,
                self.name,
                reasons=["没有解析到补充包选项"],
            )
        ]
