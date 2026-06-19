from __future__ import annotations
from typing import Dict, List
from balatro_agent.actions import SHOP
from balatro_agent.agents.base import Agent
from balatro_agent.model import (
    ActionProposal,
    GameState,
    Genome,
    item_cost,
    item_name,
    item_type,
)


class JokerOrderAgent(Agent):
    name = "joker_order"

    _CHIP_JOKERS = {
        "j_banner",
        "j_blue_joker",
        "j_clever",
        "j_crafty",
        "j_devious",
        "j_ice_cream",
        "j_odd_todd",
        "j_runner",
        "j_scary_face",
        "j_sly",
        "j_square",
        "j_stone",
        "j_wily",
    }
    _MULT_JOKERS = {
        "j_abstract",
        "j_crazy",
        "j_droll",
        "j_even_steven",
        "j_fibonacci",
        "j_flash",
        "j_green_joker",
        "j_half",
        "j_joker",
        "j_jolly",
        "j_mad",
        "j_misprint",
        "j_mystic_summit",
        "j_popcorn",
        "j_raised_fist",
        "j_ride_the_bus",
        "j_supernova",
        "j_trousers",
        "j_walkie_talkie",
        "j_zany",
    }
    _XMULT_JOKERS = {
        "j_baron",
        "j_blackboard",
        "j_campfire",
        "j_card_sharp",
        "j_cavendish",
        "j_constellation",
        "j_flower_pot",
        "j_glass",
        "j_hologram",
        "j_joker_stencil",
        "j_obelisk",
        "j_photograph",
        "j_steel_joker",
        "j_stencil",
        "j_throwback",
        "j_vampire",
    }

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase != SHOP:
            return []
        if not any(self._joker_order_group(joker) == 3 for joker in state.jokers):
            return []
        order = self._joker_order(state.jokers)
        if not order:
            return []
        return [
            ActionProposal(
                "rearrange",
                {"jokers": order},
                20.0,
                self.name,
                confidence=0.85,
                reasons=["按筹码、加倍率、乘法倍率整理小丑牌顺序"],
            )
        ]

    def _joker_order(self, jokers: List[Dict[str, object]]) -> List[int]:
        if len(jokers) <= 1:
            return []
        order = sorted(
            range(len(jokers)),
            key=lambda index: (self._joker_order_group(jokers[index]), index),
        )
        if order == list(range(len(jokers))):
            return []
        return order

    def _joker_order_group(self, joker: Dict[str, object]) -> int:
        key = str(joker.get("key") or joker.get("id") or "").lower()
        name = item_name(joker).lower()
        value = joker.get("value") if isinstance(joker.get("value"), dict) else {}
        modifier = joker.get("modifier") if isinstance(joker.get("modifier"), dict) else {}
        effect = str(joker.get("effect") or value.get("effect") or "").lower()
        edition = str(joker.get("edition") or modifier.get("edition") or "").lower()

        if key in self._XMULT_JOKERS or self._looks_like_xmult(key, name, effect) or "polychrome" in edition:
            return 3
        if key in self._CHIP_JOKERS or self._looks_like_chip(name, effect):
            return 0
        if key in self._MULT_JOKERS or self._looks_like_additive_mult("", name, effect):
            return 1
        return 2

    def _looks_like_xmult(self, key: str, name: str, effect: str) -> bool:
        text = f"{key} {name} {effect}"
        return "x mult" in text or "xmult" in text or "x-mult" in text or "x倍率" in text

    def _looks_like_chip(self, name: str, effect: str) -> bool:
        text = f"{name} {effect}"
        return ("chip" in text or "筹码" in text) and not self._looks_like_additive_mult("", name, effect)

    def _looks_like_additive_mult(self, key: str, name: str, effect: str) -> bool:
        text = f"{key} {name} {effect}"
        if self._looks_like_xmult(key, name, effect):
            return False
        return "mult" in text or "倍率" in text
