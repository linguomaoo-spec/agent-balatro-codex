from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Dict, Iterable, List, Optional, Tuple

from balatro_agent.actions import BLIND_SELECT, BOOSTER_OPENED, ROUND_EVAL, SELECTING_HAND, SHOP
from balatro_agent.model import (
    ActionProposal,
    GameState,
    Genome,
    card_enhancement,
    card_rank_value,
    card_suit,
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


class ConsumableAgent(Agent):
    name = "consumable"
    _TARGETED_TAROT_COUNTS = {
        "c_magician": 2,
        "c_lovers": 1,
        "c_empress": 2,
    }

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase not in {SELECTING_HAND, SHOP}:
            return []

        proposals: List[ActionProposal] = []
        for index, item in enumerate(state.consumables):
            kind = item_type(item)
            key = str(item.get("key") or item.get("id") or "").lower()
            if kind == "PLANET":
                proposals.append(
                    ActionProposal(
                        "use",
                        {"consumable": index},
                        200.0,
                        self.name,
                        confidence=0.9,
                        reasons=[f"立即使用行星牌：{item_name(item) or index}"],
                    )
                )
                continue
            target_count = self._TARGETED_TAROT_COUNTS.get(key)
            if state.phase != SELECTING_HAND or not target_count or not state.hand:
                continue
            target_indices = self._best_tarot_targets(state, target_count)
            if len(target_indices) != target_count:
                continue
            proposals.append(
                ActionProposal(
                    "use",
                    {"consumable": index, "cards": target_indices},
                    400.0,
                    self.name,
                    confidence=0.8,
                    reasons=[f"立即使用塔罗牌：{item_name(item) or index}"],
                )
            )
        return proposals

    def _best_tarot_targets(self, state: GameState, count: int) -> List[int]:
        suit_counts: Dict[str, int] = defaultdict(int)
        for card in state.hand:
            suit = card_suit(card)
            if suit:
                suit_counts[suit] += 1
        ranked = sorted(
            range(len(state.hand)),
            key=lambda index: (
                card_rank_value(state.hand[index]),
                suit_counts.get(card_suit(state.hand[index]), 0),
            ),
            reverse=True,
        )
        return ranked[:count]


class HandAgent(Agent):
    name = "hand"

    _HAND_BASE_SCORES = {
        "straight_flush": 700.0,
        "four_kind": 430.0,
        "full_house": 400.0,
        "flush": 260.0,
        "straight": 240.0,
        "three_kind": 240.0,
        "two_pair": 120.0,
        "pair": 40.0,
        "high_card": 5.0,
    }

    _HAND_STATE_NAMES = {
        "straight_flush": "Straight Flush",
        "four_kind": "Four of a Kind",
        "full_house": "Full House",
        "flush": "Flush",
        "straight": "Straight",
        "three_kind": "Three of a Kind",
        "two_pair": "Two Pair",
        "pair": "Pair",
        "high_card": "High Card",
    }

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase != SELECTING_HAND:
            return []
        hand = state.hand
        if not hand:
            return []

        play_indices, hand_label = self._best_play_indices(hand, state)
        play_score = (
            self._score_play(hand, play_indices, hand_label)
            + self._hand_value_bonus(state, hand_label)
            + self._joker_play_bonus(state, hand, play_indices)
        ) * genome.weight("play")
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

        discard_indices, potential_score = self._discard_plan(
            state,
            hand,
            play_indices,
            hand_label,
            play_score,
            state.hands_remaining,
            state.discards_remaining,
        )
        if discard_indices:
            discard_score = self._score_discard(
                state,
                genome,
                hand_label,
                play_score,
                potential_score,
                len(discard_indices),
            )
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

    def _best_play_indices(self, hand: List[Dict[str, object]], state: GameState) -> Tuple[List[int], str]:
        best_indices: List[int] = []
        best_label = "high_card"
        best_score = float("-inf")
        best_rank_sum = float("-inf")

        for size in range(1, min(5, len(hand)) + 1):
            for combo in combinations(range(len(hand)), size):
                indices = list(combo)
                hand_label = self._classify_play(hand, indices)
                if hand_label == "invalid":
                    continue
                score = (
                    self._score_play(hand, indices, hand_label)
                    + self._hand_value_bonus(state, hand_label)
                    + self._joker_play_bonus(state, hand, indices)
                )
                rank_sum = sum(card_rank_value(hand[index]) for index in indices)
                if (score, rank_sum, -len(indices)) > (best_score, best_rank_sum, -len(best_indices)):
                    best_indices = indices
                    best_label = hand_label
                    best_score = score
                    best_rank_sum = rank_sum

        if best_indices:
            return self._ordered_play_indices(state, hand, best_indices), best_label

        ranked = sorted(range(len(hand)), key=lambda idx: card_rank_value(hand[idx]), reverse=True)
        return [ranked[0]], "high_card"

    def _score_play(
        self,
        hand: List[Dict[str, object]],
        indices: Iterable[int],
        hand_label: str,
    ) -> float:
        rank_sum = sum(card_rank_value(hand[index]) for index in indices)
        effect_bonus = sum(self._card_effect_bonus(hand[index]) for index in indices)
        return rank_sum + effect_bonus + self._HAND_BASE_SCORES.get(hand_label, 0.0)

    def _hand_value_bonus(self, state: GameState, hand_label: str) -> float:
        hand_name = self._HAND_STATE_NAMES.get(hand_label)
        if not hand_name:
            return 0.0
        hands = state.raw.get("hands") if isinstance(state.raw, dict) else None
        if not isinstance(hands, dict):
            return 0.0
        hand_state = hands.get(hand_name)
        if not isinstance(hand_state, dict):
            return 0.0
        chips = float(hand_state.get("chips", 0) or 0)
        mult = float(hand_state.get("mult", 0) or 0)
        level = float(hand_state.get("level", 1) or 1)
        return chips + mult * 10.0 + max(0.0, level - 1.0) * 8.0

    def _classify_play(self, hand: List[Dict[str, object]], indices: List[int]) -> str:
        cards = [hand[index] for index in indices]
        rank_groups: Dict[int, int] = defaultdict(int)
        rank_values: List[int] = []
        for card in cards:
            rank_value = card_rank_value(card)
            if rank_value <= 0:
                return "invalid"
            rank_groups[rank_value] += 1
            rank_values.append(rank_value)

        counts = sorted(rank_groups.values(), reverse=True)
        is_flush = len(cards) == 5 and self._is_flush(cards)
        is_straight = len(cards) == 5 and self._is_straight(rank_values)

        if is_flush and is_straight:
            return "straight_flush"
        if counts == [4]:
            return "four_kind"
        if counts == [3, 2]:
            return "full_house"
        if is_flush:
            return "flush"
        if is_straight:
            return "straight"
        if counts == [3]:
            return "three_kind"
        if counts == [2, 2]:
            return "two_pair"
        if counts == [2]:
            return "pair"
        if len(cards) == 1:
            return "high_card"
        return "invalid"

    def _discard_plan(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        play_indices: List[int],
        hand_label: str,
        play_score: float,
        hands_remaining: int,
        discards_remaining: int,
    ) -> Tuple[List[int], float]:
        if discards_remaining <= 0:
            return [], float("-inf")
        if hand_label not in {"high_card", "pair"}:
            return [], float("-inf")
        if (
            hands_remaining == 1
            and len(play_indices) == 1
            and self._should_protect_singleton_play(state, hand[play_indices[0]])
        ):
            return [], play_score

        pair_keep_indices = self._pair_pressure_keep_plan(
            state,
            hand,
            hand_label,
            play_score,
        )
        if pair_keep_indices:
            pair_discard = [index for index in range(len(hand)) if index not in pair_keep_indices]
            if pair_discard:
                return pair_discard[: min(5, len(pair_discard))], play_score + 25.0

        photograph_keep_indices = self._photograph_pressure_keep_plan(
            state,
            hand,
            play_indices,
            hand_label,
            play_score,
        )
        if photograph_keep_indices:
            photograph_discard = [
                index for index in range(len(hand)) if index not in photograph_keep_indices
            ]
            if photograph_discard:
                return photograph_discard[: min(5, len(photograph_discard))], play_score + 25.0

        pressure_keep_indices = self._pressure_keep_plan(state, hand, hand_label)
        if pressure_keep_indices:
            pressure_discard = [index for index in range(len(hand)) if index not in pressure_keep_indices]
            if pressure_discard:
                return pressure_discard[: min(5, len(pressure_discard))], play_score + 30.0

        keep_indices, potential_score = self._best_keep_plan(state, hand)
        if not keep_indices:
            return [], potential_score

        shortfall = max(0.0, float(state.blind_requirement - state.score))
        target_per_hand = shortfall / max(1, hands_remaining)
        desperate_for_upgrade = play_score < target_per_hand * 0.65 and potential_score >= play_score * 0.85
        if potential_score <= play_score + 15.0 and not desperate_for_upgrade:
            return [], potential_score

        discard = [index for index in range(len(hand)) if index not in keep_indices]
        return discard[: min(5, len(discard))], potential_score

    def _pair_pressure_keep_plan(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        hand_label: str,
        play_score: float,
    ) -> List[int]:
        if hand_label not in {"pair", "two_pair"}:
            return []
        if state.hands_remaining < 3 or state.discards_remaining < 2:
            return []

        shortfall = max(0.0, float(state.blind_requirement - state.score))
        target_per_hand = shortfall / max(1, state.hands_remaining)
        if play_score >= target_per_hand * 0.35:
            return []

        rank_groups: Dict[int, List[int]] = defaultdict(list)
        for index, card in enumerate(hand):
            rank_value = card_rank_value(card)
            if rank_value <= 0:
                continue
            rank_groups[rank_value].append(index)

        pair_groups = [indices for indices in rank_groups.values() if len(indices) >= 2]
        if len(pair_groups) < 3:
            return []

        keep = sorted(index for indices in pair_groups for index in indices[:2])
        if len(keep) >= len(hand):
            return []
        return keep

    def _photograph_pressure_keep_plan(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        play_indices: List[int],
        hand_label: str,
        play_score: float,
    ) -> List[int]:
        joker_keys = set(self._joker_keys(state))
        if "j_photograph" not in joker_keys:
            return []
        if hand_label != "high_card" or len(play_indices) != 1:
            return []
        if state.hands_remaining <= 1 or state.discards_remaining <= 0:
            return []

        played_rank = card_rank_value(hand[play_indices[0]])
        if played_rank not in {11, 12, 13}:
            return []

        shortfall = max(0.0, float(state.blind_requirement - state.score))
        target_per_hand = shortfall / max(1, state.hands_remaining)
        if play_score >= target_per_hand * 0.5:
            return []

        rank_groups: Dict[int, List[int]] = defaultdict(list)
        for index, card in enumerate(hand):
            rank_value = card_rank_value(card)
            if rank_value <= 0:
                continue
            rank_groups[rank_value].append(index)

        pair_groups = [indices for indices in rank_groups.values() if len(indices) >= 2]
        if not pair_groups:
            return []

        best_pair = max(
            pair_groups,
            key=lambda indices: (
                len(indices),
                max(card_rank_value(hand[index]) for index in indices),
            ),
        )

        premium_singles = sorted(
            (
                index
                for index, card in enumerate(hand)
                if index not in best_pair and card_rank_value(card) >= 11
            ),
            key=lambda index: self._card_priority(state, hand[index]),
            reverse=True,
        )
        if not premium_singles:
            return []

        keep = sorted(set(best_pair + premium_singles[:2]))
        if len(keep) >= len(hand):
            return []
        return keep

    def _pressure_keep_plan(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        hand_label: str,
    ) -> List[int]:
        if state.hands_remaining != 1 or state.discards_remaining <= 0:
            return []
        if state.discards_remaining < 4:
            return []
        if hand_label not in {"high_card", "pair"}:
            return []

        shortfall = max(0.0, float(state.blind_requirement - state.score))
        if shortfall < max(1500.0, float(state.blind_requirement) * 0.2):
            return []

        rank_groups: Dict[int, List[int]] = defaultdict(list)
        for index, card in enumerate(hand):
            rank_value = card_rank_value(card)
            if rank_value <= 0:
                continue
            rank_groups[rank_value].append(index)

        multi_groups = [indices for indices in rank_groups.values() if len(indices) >= 2]
        if len(multi_groups) < 2:
            return []

        multi_groups.sort(
            key=lambda indices: (
                len(indices),
                max(card_rank_value(hand[index]) for index in indices),
            ),
            reverse=True,
        )

        keep: List[int] = []
        for indices in multi_groups[:2]:
            keep.extend(indices[: min(3, len(indices))])
        keep = sorted(set(keep))
        if len(keep) >= len(hand):
            return []
        return keep

    def _score_discard(
        self,
        state: GameState,
        genome: Genome,
        hand_label: str,
        play_score: float,
        potential_score: float,
        discard_count: int,
    ) -> float:
        score = (
            play_score + 10.0 + discard_count + genome.weight("risk") * 2.0
        ) * genome.weight("discard")

        if hand_label not in {"high_card", "pair"}:
            return score

        shortfall = max(0.0, float(state.blind_requirement - state.score))
        if shortfall <= 0:
            return score

        target_per_hand = shortfall / max(1, state.hands_remaining)
        if play_score >= target_per_hand * 0.65:
            return score

        improvement_bonus = max(0.0, potential_score - play_score) * 0.7
        pressure_bonus = max(0.0, target_per_hand - play_score) * 0.18
        return score + min(220.0, improvement_bonus + pressure_bonus)

    def _best_keep_plan(self, state: GameState, hand: List[Dict[str, object]]) -> Tuple[List[int], float]:
        best_indices: List[int] = []
        best_score = float("-inf")
        for size in range(2, min(5, len(hand)) + 1):
            for combo in combinations(range(len(hand)), size):
                indices = list(combo)
                potential_score = self._potential_keep_score(state, hand, indices)
                if (potential_score, len(indices)) > (best_score, len(best_indices)):
                    best_indices = indices
                    best_score = potential_score
        return best_indices, best_score

    def _potential_keep_score(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        indices: List[int],
    ) -> float:
        cards = [hand[index] for index in indices]
        rank_counts: Dict[int, int] = defaultdict(int)
        rank_values: List[int] = []
        for card in cards:
            rank_value = card_rank_value(card)
            if rank_value <= 0:
                return float("-inf")
            rank_values.append(rank_value)
            rank_counts[rank_value] += 1

        max_rank_group = max(rank_counts.values(), default=0)
        max_suit_group = self._max_flush_group(cards)
        longest_run = self._longest_run(rank_values)
        score = sum(rank_values) * 0.4
        score += sum(self._card_effect_bonus(card) for card in cards) * 0.9
        score += sum(self._card_synergy_bonus(state, card) for card in cards) * 0.8

        if max_rank_group >= 2:
            score += 14.0 * max_rank_group
        if len([count for count in rank_counts.values() if count >= 2]) >= 2:
            score += 16.0
        if max_suit_group >= 3:
            score += 16.0 * max_suit_group
        if longest_run >= 3:
            score += 16.0 * longest_run
        if len(indices) >= 4 and max_suit_group == len(indices) and longest_run == len(indices):
            score += 45.0
        return score

    def _is_flush(self, cards: List[Dict[str, object]]) -> bool:
        return self._max_flush_group(cards) >= len(cards)

    def _max_flush_group(self, cards: List[Dict[str, object]]) -> int:
        suit_counts: Dict[str, int] = defaultdict(int)
        wild_count = 0
        for card in cards:
            if card_enhancement(card) == "WILD":
                wild_count += 1
                continue
            suit = card_suit(card)
            if suit:
                suit_counts[suit] += 1
        if wild_count and not suit_counts:
            return len(cards)
        return max((count + wild_count for count in suit_counts.values()), default=wild_count)

    def _is_straight(self, rank_values: List[int]) -> bool:
        unique = sorted(set(rank_values))
        if len(unique) != 5:
            return False
        if unique == [2, 3, 4, 5, 14]:
            return True
        return unique[-1] - unique[0] == 4

    def _longest_run(self, rank_values: List[int]) -> int:
        unique = sorted(set(rank_values))
        if not unique:
            return 0
        longest = 1
        current = 1
        for previous, current_rank in zip(unique, unique[1:]):
            if current_rank == previous + 1:
                current += 1
            else:
                current = 1
            longest = max(longest, current)
        if 14 in unique and {2, 3, 4, 5}.issubset(set(unique)):
            longest = max(longest, 5)
        return longest

    def _ordered_play_indices(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        indices: List[int],
    ) -> List[int]:
        return sorted(
            indices,
            key=lambda index: (
                self._card_priority(state, hand[index]),
                card_rank_value(hand[index]),
            ),
            reverse=True,
        )

    def _should_protect_singleton_play(self, state: GameState, card: Dict[str, object]) -> bool:
        joker_keys = set(self._joker_keys(state))
        rank_value = card_rank_value(card)
        return "j_scholar" in joker_keys and rank_value == 14

    def _joker_play_bonus(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        indices: List[int],
    ) -> float:
        bonus = sum(self._card_synergy_bonus(state, hand[index]) for index in indices)
        joker_keys = self._joker_keys(state)
        played_ranks = [card_rank_value(hand[index]) for index in indices]
        first_rank = played_ranks[0] if played_ranks else 0
        if "j_hanging_chad" in joker_keys and indices:
            bonus += 2.0 * max(self._card_priority(state, hand[index]) for index in indices)
        if "j_half" in joker_keys and 1 <= len(indices) <= 3:
            bonus += 220.0
        if "j_scholar" in joker_keys:
            ace_count = sum(1 for rank in played_ranks if rank == 14)
            if ace_count:
                bonus += 72.0 * ace_count
                if first_rank == 14 and "j_hanging_chad" in joker_keys:
                    bonus += 40.0
        if "j_photograph" in joker_keys:
            face_ranks = {11, 12, 13}
            if first_rank in face_ranks:
                bonus += 72.0
                if "j_hanging_chad" in joker_keys:
                    bonus += 36.0
            elif any(rank in face_ranks for rank in played_ranks):
                bonus += 36.0
        return bonus

    def _card_priority(self, state: GameState, card: Dict[str, object]) -> float:
        return (
            card_rank_value(card)
            + self._card_effect_bonus(card)
            + self._card_synergy_bonus(state, card)
        )

    def _card_effect_bonus(self, card: Dict[str, object]) -> float:
        enhancement = card_enhancement(card)
        if enhancement == "BONUS":
            return 30.0
        if enhancement == "MULT":
            return 36.0
        if enhancement == "WILD":
            return 10.0
        if enhancement == "GLASS":
            return 45.0
        if enhancement == "LUCKY":
            return 18.0
        if enhancement == "GOLD":
            return 8.0
        return 0.0

    def _card_synergy_bonus(self, state: GameState, card: Dict[str, object]) -> float:
        joker_keys = self._joker_keys(state)
        bonus = 0.0
        if card_enhancement(card) == "WILD":
            bonus += 6.0

        if not joker_keys:
            return bonus

        suit = card_suit(card)
        rank_value = card_rank_value(card)

        suit_bonus_by_key = {
            "j_gluttenous_joker": "C",
            "j_lusty_joker": "H",
            "j_greedy_joker": "D",
            "j_wrathful_joker": "S",
        }
        for key, expected_suit in suit_bonus_by_key.items():
            if key in joker_keys and suit == expected_suit:
                bonus += 18.0

        if "j_walkie_talkie" in joker_keys and rank_value in {4, 10}:
            bonus += 18.0
        if "j_even_steven" in joker_keys and rank_value in {2, 4, 6, 8, 10}:
            bonus += 10.0
        if "j_odd_todd" in joker_keys and rank_value in {3, 5, 7, 9, 14}:
            bonus += 12.0
        if "j_scholar" in joker_keys and rank_value == 14:
            bonus += 24.0
        if "j_photograph" in joker_keys and rank_value in {11, 12, 13}:
            bonus += 18.0

        return bonus

    def _joker_keys(self, state: GameState) -> List[str]:
        return [str(joker.get("key") or "") for joker in state.jokers if isinstance(joker, dict)]


class ShopAgent(Agent):
    name = "shop"
    _JOKER_REPLACEMENT_MARGIN = 10.0

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase != SHOP:
            return []
        proposals: List[ActionProposal] = []
        money = state.money
        joker_slots_full = state.joker_limit > 0 and len(state.jokers) >= state.joker_limit
        consumable_slots_full = (
            state.consumable_limit > 0 and len(state.consumables) >= state.consumable_limit
        )

        if joker_slots_full:
            sell_proposal = self._sell_joker_proposal(state, money)
            if sell_proposal is not None:
                proposals.append(sell_proposal)

        for index, item in enumerate(state.shop_cards()):
            cost = item_cost(item)
            if cost and cost > money:
                continue
            kind = item_type(item)
            if kind == "JOKER":
                if joker_slots_full:
                    continue
                base = self._joker_strength(item, state) * genome.weight("buy_joker")
            elif kind in {"CONSUMABLE", "TAROT", "PLANET", "SPECTRAL"}:
                if consumable_slots_full:
                    continue
                base = self._consumable_buy_score(item, state, genome)
                if base is None:
                    continue
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
            if joker_slots_full and "buffoon" in item_name(pack).lower():
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

    def _sell_joker_proposal(
        self,
        state: GameState,
        money: int,
    ) -> Optional[ActionProposal]:
        owned = list(state.jokers)
        if not owned:
            return None

        best_shop_option: Optional[Tuple[float, int, Dict[str, object]]] = None
        for index, item in enumerate(state.shop_cards()):
            if item_type(item) != "JOKER":
                continue
            cost = item_cost(item)
            if cost and cost > money:
                continue
            score = self._joker_strength(item, state)
            candidate = (score, index, item)
            if best_shop_option is None or candidate > best_shop_option:
                best_shop_option = candidate

        if best_shop_option is None:
            return None

        weakest_owned = min(
            (
                (self._joker_strength(joker, state), index, joker)
                for index, joker in enumerate(owned)
            ),
            default=None,
        )
        if weakest_owned is None:
            return None

        best_score, _, best_item = best_shop_option
        weakest_score, weakest_index, weakest_item = weakest_owned
        if best_score < weakest_score + self._JOKER_REPLACEMENT_MARGIN:
            return None

        return ActionProposal(
            "sell",
            {"joker": weakest_index},
            16.0 + best_score - weakest_score,
            self.name,
            confidence=0.6,
            reasons=[
                f"卖出较弱 Joker：{item_name(weakest_item) or weakest_index}",
                f"为更强 Joker 腾槽：{item_name(best_item)}",
            ],
        )

    def _consumable_buy_score(
        self,
        item: Dict[str, object],
        state: GameState,
        genome: Genome,
    ) -> Optional[float]:
        kind = item_type(item)
        key = str(item.get("key") or item.get("id") or "").lower()
        base = 8.0 * genome.weight("buy_consumable")

        if kind == "PLANET":
            return base
        if key in ConsumableAgent._TARGETED_TAROT_COUNTS:
            return base
        if key == "c_hermit" and 0 < state.money < 10:
            return base
        return None

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

    def _joker_strength(self, item: Dict[str, object], state: Optional[GameState] = None) -> float:
        key = str(item.get("key") or item.get("id") or "").lower()
        name = item_name(item).lower()
        value = item.get("value")
        effect = ""
        if isinstance(value, dict):
            effect = str(value.get("effect") or "").lower()

        key_scores = {
            "j_abstract": 36.0,
            "j_ancient": 18.0,
            "j_delayed_grat": 6.0,
            "j_gluttenous_joker": 14.0,
            "j_lusty_joker": 14.0,
            "j_greedy_joker": 14.0,
            "j_wrathful_joker": 14.0,
            "j_half": 30.0,
            "j_photograph": 24.0,
            "j_scholar": 20.0,
            "j_walkie_talkie": 22.0,
            "j_blue_joker": 24.0,
            "j_campfire": 20.0,
            "j_hanging_chad": 28.0,
        }
        base = key_scores.get(key, 14.0)

        if "abstract joker" in name:
            base = max(base, 36.0)
        if "ancient joker" in name:
            base = max(base, 18.0)
        if "scholar" in name:
            base = max(base, 20.0)
        if "photograph" in name:
            base = max(base, 24.0)
        if "campfire" in name:
            base = max(base, 20.0)
        if "half joker" in name:
            base = max(base, 30.0)

        if key not in key_scores:
            if "x" in name or "x" in effect or "倍率" in effect:
                base += 10.0
            if "mult" in name or "倍率" in effect:
                base += 6.0
            if "chip" in name or "筹码" in effect:
                base += 4.0
            if "trigger" in effect or "额外触发" in effect:
                base += 6.0
            if "discard" in name or "弃牌" in effect:
                base -= 3.0
            if "$" in effect or "money" in name or "dollar" in name:
                base -= 2.0

        if state is not None:
            owned_keys = {str(joker.get("key") or "").lower() for joker in state.jokers}
            if key == "j_photograph":
                if "j_hanging_chad" in owned_keys:
                    base += 10.0
                if "j_half" in owned_keys:
                    base += 4.0
            if key == "j_scholar":
                if "j_half" in owned_keys:
                    base += 8.0
                if "j_hanging_chad" in owned_keys:
                    base += 4.0
        return base


class EconomyAgent(Agent):
    name = "economy"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase != SHOP:
            return []
        reserve = genome.weight("cash_reserve", 5.0)
        surplus = max(0.0, state.money - reserve)
        affordable_options = self._affordable_option_count(state)
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
        if surplus >= 5:
            scarcity_bonus = 2.5 if affordable_options == 0 else 0.0
            hoard_bonus = 2.0 if surplus >= 20 else 0.0
            ante_bonus = max(0.0, state.ante - 2) * 0.6
            reroll_score = (
                2.0 * genome.weight("reroll", 0.35)
                + surplus * 0.05
                + scarcity_bonus
                + hoard_bonus
                + ante_bonus
            )
            joker_slots_full = state.joker_limit > 0 and len(state.jokers) >= state.joker_limit
            if joker_slots_full:
                if state.money < 25:
                    reroll_score -= 2.0
                elif state.money < 30:
                    reroll_score -= 0.5
            proposals.append(
                ActionProposal(
                    "reroll",
                    {},
                    reroll_score,
                    self.name,
                    confidence=0.35,
                    reasons=["金钱高于保留线"],
                )
            )
        return proposals

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
            if kind == "JOKER" and joker_slots_full:
                continue
            if kind in {"CONSUMABLE", "TAROT", "PLANET", "SPECTRAL"} and consumable_slots_full:
                continue
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


def default_agents() -> List[Agent]:
    return [RoundAgent(), BoosterAgent(), ConsumableAgent(), HandAgent(), ShopAgent(), EconomyAgent()]
