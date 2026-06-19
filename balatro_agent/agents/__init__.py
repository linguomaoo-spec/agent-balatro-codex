from __future__ import annotations

from balatro_agent.agents.base import Agent
from balatro_agent.agents.round import RoundAgent
from balatro_agent.agents.booster import BoosterAgent
from balatro_agent.agents.consumable import ConsumableAgent
from balatro_agent.agents.hand import HandAgent
from balatro_agent.agents.joker_order import JokerOrderAgent
from balatro_agent.agents.shop import ShopAgent
from balatro_agent.agents.economy import EconomyAgent


def default_agents():
    """默认 agent 列表，按优先级排列。"""
    return [
        EconomyAgent(),
        BoosterAgent(),
        ConsumableAgent(),
        JokerOrderAgent(),
        ShopAgent(),
        HandAgent(),
        RoundAgent(),
    ]


__all__ = [
    "Agent", "RoundAgent", "BoosterAgent", "ConsumableAgent",
    "HandAgent", "JokerOrderAgent", "ShopAgent", "EconomyAgent",
    "default_agents",
]
