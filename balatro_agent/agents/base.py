from __future__ import annotations
from typing import List
from balatro_agent.model import ActionProposal, GameState, Genome


class Agent:
    name = "agent"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        raise NotImplementedError

    def propose_search(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        return self.propose(state, genome)
