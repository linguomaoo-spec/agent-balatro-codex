from __future__ import annotations

from typing import Dict, List, Optional

from balatro_agent.actions import (
    BLIND_SELECT,
    BOOSTER_OPENED,
    ROUND_EVAL,
    SELECTING_HAND,
    SHOP,
    validate_action,
)
from balatro_agent.agents import Agent, default_agents
from balatro_agent.model import ActionProposal, Decision, GameState, Genome


class DefaultOrchestrator:
    def __init__(
        self,
        genome: Optional[Genome] = None,
        agents: Optional[List[Agent]] = None,
    ) -> None:
        self.genome = genome or Genome.default()
        self.agents = agents or default_agents()
        self.last_decision: Optional[Decision] = None

    def decide(self, state: GameState) -> ActionProposal:
        decision = self.decide_with_details(state)
        return decision.selected

    def decide_with_details(self, state: GameState) -> Decision:
        proposals: List[ActionProposal] = []
        for agent in self.agents:
            proposals.extend(agent.propose(state, self.genome))

        valid: List[ActionProposal] = []
        rejected: List[Dict[str, str]] = []
        for proposal in proposals:
            validation = validate_action(proposal, state)
            if validation.ok:
                valid.append(proposal)
            else:
                rejected.append(
                    {
                        "method": proposal.method,
                        "agent": proposal.agent,
                        "reason": validation.reason,
                    }
                )

        if valid:
            selected = max(valid, key=lambda proposal: (proposal.score, proposal.confidence))
        else:
            selected = self._fallback(state)

        decision = Decision(state, selected, valid, rejected)
        self.last_decision = decision
        return decision

    def _fallback(self, state: GameState) -> ActionProposal:
        if state.phase == ROUND_EVAL:
            return ActionProposal("cash_out", {}, 0.0, "fallback", reasons=["回合结算兜底"])
        if state.phase == BLIND_SELECT:
            return ActionProposal("select", {}, 0.0, "fallback", reasons=["盲注选择兜底"])
        if state.phase == SHOP:
            return ActionProposal("next_round", {}, 0.0, "fallback", reasons=["商店兜底"])
        if state.phase == BOOSTER_OPENED:
            return ActionProposal("pack", {"skip": True}, 0.0, "fallback", reasons=["补充包兜底"])
        if state.phase == SELECTING_HAND and state.hand:
            return ActionProposal("play", {"cards": [0]}, 0.0, "fallback", reasons=["手牌兜底"])
        return ActionProposal("gamestate", {}, 0.0, "fallback", reasons=["未知状态兜底"])
