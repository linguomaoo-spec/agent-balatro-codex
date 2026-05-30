from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from balatro_agent.actions import BLIND_SELECT, BOOSTER_OPENED, ROUND_EVAL, SELECTING_HAND, SHOP
from balatro_agent.model import (
    ActionProposal,
    GameState,
    Genome,
    card_rank,
    card_rank_value,
    item_cost,
    item_name,
    item_type,
)


class Agent:
    name = "agent"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        raise NotImplementedError


class RoundAgent(Agent):
    name = "round"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase == ROUND_EVAL:
            return [ActionProposal("cash_out", {}, 1000.0, self.name, reasons=["回合结算"])]
        if state.phase == BLIND_SELECT:
            return [ActionProposal("select", {}, 1000.0, self.name, reasons=["默认选择盲注"])]
        return []


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


class HandAgent(Agent):
    name = "hand"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase != SELECTING_HAND:
            return []
        hand = state.hand
        if not hand:
            return []

        play_indices, hand_label = self._best_play_indices(hand)
        play_score = self._score_play(hand, play_indices, hand_label) * genome.weight("play")
        proposals = [
            ActionProposal(
                "play",
                {"cards": play_indices},
                play_score,
                self.name,
                confidence=0.65,
                reasons=[f"解析到的最佳牌型：{hand_label}"],
            )
        ]

        discard_indices = self._discard_indices(hand, play_indices)
        if state.discards_remaining > 0 and state.hands_remaining > 1 and discard_indices:
            discard_score = (
                8.0 + len(discard_indices) + genome.weight("risk") * 2.0
            ) * genome.weight("discard")
            proposals.append(
                ActionProposal(
                    "discard",
                    {"cards": discard_indices},
                    discard_score,
                    self.name,
                    confidence=0.45,
                    reasons=["资源充足时改进较弱的非对子手牌"],
                )
            )
        return proposals

    def _best_play_indices(self, hand: List[Dict[str, object]]) -> Tuple[List[int], str]:
        by_rank: Dict[str, List[int]] = defaultdict(list)
        for index, card in enumerate(hand):
            rank = card_rank(card)
            by_rank[rank].append(index)

        groups = [
            (len(indices), max(card_rank_value(hand[index]) for index in indices), indices, rank)
            for rank, indices in by_rank.items()
            if rank
        ]
        groups.sort(reverse=True)
        if groups and groups[0][0] >= 2:
            size, _rank_value, indices, rank = groups[0]
            if size >= 4:
                label = "four_kind"
            elif size == 3:
                label = "three_kind"
            else:
                label = f"pair_{rank}"
            return sorted(indices[:5]), label

        ranked = sorted(
            range(len(hand)),
            key=lambda idx: (card_rank_value(hand[idx]), -idx),
            reverse=True,
        )
        return sorted(ranked[: min(5, len(ranked))]), "high_cards"

    def _score_play(
        self,
        hand: List[Dict[str, object]],
        indices: Iterable[int],
        hand_label: str,
    ) -> float:
        rank_sum = sum(card_rank_value(hand[index]) for index in indices)
        bonuses = {
            "four_kind": 80.0,
            "three_kind": 45.0,
            "high_cards": 5.0,
        }
        if hand_label.startswith("pair"):
            return rank_sum + 28.0
        return rank_sum + bonuses.get(hand_label, 10.0)

    def _discard_indices(self, hand: List[Dict[str, object]], keep: List[int]) -> List[int]:
        keep_set = set(keep)
        candidates = [
            index
            for index, card in enumerate(hand)
            if index not in keep_set and card_rank_value(card) <= 9
        ]
        candidates.sort(key=lambda idx: card_rank_value(hand[idx]))
        return candidates[: min(5, len(candidates))]


class ShopAgent(Agent):
    name = "shop"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase != SHOP:
            return []
        proposals: List[ActionProposal] = []
        money = state.money

        for index, item in enumerate(state.shop_cards()):
            cost = item_cost(item)
            if cost and cost > money:
                continue
            kind = item_type(item)
            if kind == "JOKER":
                base = 20.0 * genome.weight("buy_joker")
            elif kind == "CONSUMABLE":
                base = 8.0 * genome.weight("buy_consumable")
            else:
                base = 5.0
            base += self._synergy_bonus(item, state, genome)
            base -= max(0, cost - max(0, money - int(genome.weight("cash_reserve", 5.0)))) * 0.7
            proposals.append(
                ActionProposal(
                    "buy",
                    {"card": index},
                    base,
                    self.name,
                    confidence=0.55,
                    reasons=[f"商店卡牌：{item_name(item) or kind or index}"],
                )
            )

        for index, voucher in enumerate(state.shop_vouchers()):
            cost = item_cost(voucher)
            if cost and cost > money:
                continue
            proposals.append(
                ActionProposal(
                    "buy",
                    {"voucher": index},
                    12.0 * genome.weight("buy_voucher"),
                    self.name,
                    confidence=0.45,
                    reasons=[f"优惠券：{item_name(voucher) or index}"],
                )
            )

        for index, pack in enumerate(state.shop_packs()):
            cost = item_cost(pack)
            if cost and cost > money:
                continue
            proposals.append(
                ActionProposal(
                    "buy",
                    {"pack": index},
                    10.0 * genome.weight("buy_pack"),
                    self.name,
                    confidence=0.4,
                    reasons=[f"补充包：{item_name(pack) or index}"],
                )
            )
        return proposals

    def _synergy_bonus(self, item: Dict[str, object], state: GameState, genome: Genome) -> float:
        name = item_name(item).lower()
        bonus = 0.0
        if "mult" in name:
            bonus += 2.5
        if "chip" in name:
            bonus += 1.5
        if state.ante >= 4 and "x" in name:
            bonus += 3.0
        return bonus * genome.weight("synergy")


class EconomyAgent(Agent):
    name = "economy"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase != SHOP:
            return []
        reserve = genome.weight("cash_reserve", 5.0)
        proposals = [
            ActionProposal(
                "next_round",
                {},
                4.0 + max(0.0, reserve - state.money) * genome.weight("next_round", 0.15),
                self.name,
                confidence=0.8,
                reasons=["没有高价值动作胜出时离开商店"],
            )
        ]
        if state.money >= reserve + 5:
            proposals.append(
                ActionProposal(
                    "reroll",
                    {},
                    7.0 * genome.weight("reroll", 0.35),
                    self.name,
                    confidence=0.35,
                    reasons=["金钱高于保留线"],
                )
            )
        return proposals


def default_agents() -> List[Agent]:
    return [RoundAgent(), BoosterAgent(), HandAgent(), ShopAgent(), EconomyAgent()]
