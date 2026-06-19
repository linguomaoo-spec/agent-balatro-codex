from __future__ import annotations
from typing import Dict, List
from balatro_agent.actions import SHOP
from balatro_agent.agents.base import Agent
from balatro_agent.agents.consumable import ConsumableAgent
from balatro_agent.model import (
    ActionProposal,
    GameState,
    Genome,
    card_enhancement,
    card_identity,
    card_rank_value,
    card_suit,
    item_cost,
    item_name,
    item_type,
)


class EconomyAgent(Agent):
    name = "economy"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase != SHOP:
            return []
        # 动态现金储备：随ante提高，支撑跨Boss经济和后期商店
        ante_reserve = state.ante * genome.weight("cash_reserve_ante_scale", 1.5)
        reserve = genome.weight("cash_reserve", 8.0) + ante_reserve
        surplus = max(0.0, state.money - reserve)
        affordable_options = self._affordable_option_count(state)
        # 空消耗品惩罚：余裕资金充裕时降低离开意愿，鼓励购买消耗品
        empty_consumable_penalty = 0.0
        if len(state.consumables) == 0 and state.money > reserve + 5:
            empty_consumable_penalty = genome.weight("consumable_empty_slot_bonus", 1.5)
        proposals = [
            ActionProposal(
                "next_round",
                {},
                3.5 + max(0.0, reserve - state.money) * genome.weight("next_round", 0.15)
                - empty_consumable_penalty,
                self.name,
                confidence=0.8,
                reasons=["没有高价值动作胜出时离开商店"],
            )
        ]
        if surplus >= 5:
            joker_slots_full = state.joker_limit > 0 and len(state.jokers) >= state.joker_limit
            consumable_slots_full = (
                state.consumable_limit > 0 and len(state.consumables) >= state.consumable_limit
            )
            all_slots_full = joker_slots_full and consumable_slots_full

            # 稀缺奖励：无可用选项时鼓励重掷，全满时也能找更好的Joker替换
            if affordable_options == 0:
                scarcity_bonus = 1.5 if all_slots_full else 2.5
            else:
                scarcity_bonus = 0.0

            # 囤积奖励：钱很多时可以花一些重掷
            hoard_bonus = 2.5 if surplus >= 25 else (1.5 if surplus >= 15 else 0.0)
            # 后期重掷惩罚：Ante越高需要越谨慎
            ante_penalty = max(0.0, state.ante - 3) * 0.8

            # 槽位全满时降低重掷意愿，但不会完全禁止
            full_slot_penalty = 2.0 if all_slots_full else (1.0 if joker_slots_full else 0.0)

            reroll_score = (
                2.5 * genome.weight("reroll", 0.25)
                + surplus * 0.05
                + scarcity_bonus
                + hoard_bonus
                - ante_penalty
                - full_slot_penalty
            )
            # 槽位满时的额外资金检查：钱太少重掷后买不起东西
            if joker_slots_full:
                if state.money < 18:
                    reroll_score -= 2.5
                elif state.money < 22:
                    reroll_score -= 1.0
            # 分数太低则跳过
            if reroll_score < 1.0:
                return proposals
            if self._should_preserve_scary_juggler_timing(state):
                return proposals
            proposals.append(
                ActionProposal(
                    "reroll",
                    {},
                    reroll_score,
                    self.name,
                    confidence=0.3,
                    reasons=["金钱高于保留线且商店选项不佳"],
                )
            )
        return proposals

    def _should_preserve_scary_juggler_timing(self, state: GameState) -> bool:
        if state.joker_limit <= 0 or len(state.jokers) < state.joker_limit:
            return False
        owned_keys = {str(joker.get("key") or "").lower() for joker in state.jokers}
        if state.ante == 3 and state.round_number >= 8:
            return {"j_sly", "j_juggler", "j_scary_face"}.issubset(owned_keys)
        if state.ante == 4 and state.round_number == 9 and not state.shop_cards():
            return {
                "j_sly",
                "j_juggler",
                "j_scary_face",
                "j_half",
                "j_supernova",
            }.issubset(owned_keys)
        return False

    def _affordable_option_count(self, state: GameState) -> int:
        joker_slots_full = state.joker_limit > 0 and len(state.jokers) >= state.joker_limit
        consumable_slots_full = (
            state.consumable_limit > 0 and len(state.consumables) >= state.consumable_limit
        )
        count = 0

        for item in state.shop_cards():
            cost = item_cost(item)
            if cost and cost > state.money:
                continue
            kind = item_type(item)
            if kind == "JOKER":
                if joker_slots_full:
                    continue
                count += 1
            elif kind in {"CONSUMABLE", "TAROT", "PLANET", "SPECTRAL"}:
                if consumable_slots_full:
                    continue
                # 只计算有实际购买价值的消耗品（排除不会被购买的塔罗牌等）
                key = str(item.get("key") or item.get("id") or "").lower()
                if kind == "PLANET" or key in ConsumableAgent._TARGETED_TAROT_COUNTS or key == "c_hermit":
                    count += 1
            else:
                count += 1

        for voucher in state.shop_vouchers():
            cost = item_cost(voucher)
            if not cost or cost <= state.money:
                count += 1

        for pack in state.shop_packs():
            cost = item_cost(pack)
            if cost and cost > state.money:
                continue
            if joker_slots_full and "buffoon" in item_name(pack).lower():
                continue
            count += 1

        return count
