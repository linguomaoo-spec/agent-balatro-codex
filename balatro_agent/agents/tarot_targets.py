from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional

from balatro_agent.model import GameState, card_enhancement, card_rank_value, card_suit


TARGETED_TAROT_COUNTS: Dict[str, int] = {
    "c_magician": 2,
    "c_lovers": 1,
    "c_empress": 2,
    "c_strength": 1,
    "c_death": 2,
    "c_chariot": 1,
    "c_justice": 1,
    "c_devil": 1,
    "c_heirophant": 2,
    "c_sun": 3,
    "c_moon": 3,
    "c_world": 3,
    "c_star": 3,
    "c_hanged_man": 2,
}

_ENHANCEMENTS = {
    "c_magician",
    "c_lovers",
    "c_empress",
    "c_chariot",
    "c_justice",
    "c_heirophant",
}
_SUIT_TAROTS = {
    "c_sun": "H",
    "c_moon": "C",
    "c_world": "S",
    "c_star": "D",
}
_SUIT_JOKER_SUITS = {
    "j_lusty_joker": "H",
    "j_gluttenous_joker": "C",
    "j_wrathful_joker": "S",
    "j_greedy_joker": "D",
}


@dataclass(frozen=True)
class TarotTargetChoice:
    cards: List[int]
    reasons: List[str]


def choose_tarot_targets(tarot_key: str, state: GameState) -> Optional[TarotTargetChoice]:
    """Return effect-aware hand targets for a supported Tarot card.

    A missing choice means that spending the Tarot has no supported strategic target in
    the current hand. Callers should not create an action proposal in that case.
    """

    key = str(tarot_key or "").lower()
    required = TARGETED_TAROT_COUNTS.get(key)
    if required is None or len(state.hand) < required:
        return None
    if key in _ENHANCEMENTS:
        return _enhancement_targets(key, state, required)
    if key == "c_strength":
        return _strength_targets(state)
    if key == "c_death":
        return _death_targets(state)
    if key == "c_devil":
        return _devil_targets(state)
    if key in _SUIT_TAROTS:
        return _suit_targets(key, state, required)
    if key == "c_hanged_man":
        return _hanged_man_targets(state, required)
    return None


def _enhancement_targets(key: str, state: GameState, required: int) -> Optional[TarotTargetChoice]:
    ranked = _rank_for_improvement(state)
    candidates = [index for index in ranked if not card_enhancement(state.hand[index])]
    if len(candidates) < required:
        return None
    return TarotTargetChoice(
        candidates[:required],
        [f"{key}：强化主力牌型中的未增强牌 {candidates[:required]}"],
    )


def _strength_targets(state: GameState) -> Optional[TarotTargetChoice]:
    rank_counts = Counter(card_rank_value(card) for card in state.hand)
    candidates = sorted(
        range(len(state.hand)),
        key=lambda index: (
            rank_counts.get(card_rank_value(state.hand[index]) + 1, 0),
            _core_score(index, state),
            -bool(card_enhancement(state.hand[index])),
            card_rank_value(state.hand[index]),
        ),
        reverse=True,
    )
    if not candidates:
        return None
    target = candidates[0]
    return TarotTargetChoice([target], [f"c_strength：提升可形成主力组合的牌 {target}"])


def _death_targets(state: GameState) -> Optional[TarotTargetChoice]:
    if len(state.hand) < 2:
        return None
    source = _rank_for_improvement(state)[0]
    destinations = sorted(
        (index for index in range(len(state.hand)) if index != source),
        key=lambda index: _removal_score(index, state),
    )
    if not destinations:
        return None
    destination = destinations[0]
    # BalatroBot follows Balatro's left-to-right Death semantics: first card becomes
    # a copy of the second card. Keep this ordering local and explicit.
    return TarotTargetChoice(
        [destination, source],
        [f"c_death：用主力模板 {source} 覆盖低价值牌 {destination}"],
    )


def _devil_targets(state: GameState) -> Optional[TarotTargetChoice]:
    candidates = sorted(range(len(state.hand)), key=lambda index: _removal_score(index, state))
    if not candidates:
        return None
    target = candidates[0]
    return TarotTargetChoice([target], [f"c_devil：将非主力牌 {target} 转为黄金牌"])


def _suit_targets(key: str, state: GameState, required: int) -> Optional[TarotTargetChoice]:
    target_suit = _SUIT_TAROTS[key]
    if not _supports_suit_plan(state, target_suit):
        return None
    candidates = [
        index
        for index in sorted(range(len(state.hand)), key=lambda index: _removal_score(index, state))
        if card_suit(state.hand[index]) != target_suit
    ]
    if len(candidates) < required:
        return None
    selected = candidates[:required]
    return TarotTargetChoice(selected, [f"{key}：将非目标花色牌 {selected} 转为 {target_suit}"])


def _hanged_man_targets(state: GameState, required: int) -> Optional[TarotTargetChoice]:
    candidates = sorted(range(len(state.hand)), key=lambda index: _removal_score(index, state))
    if len(candidates) < required:
        return None
    selected = candidates[:required]
    return TarotTargetChoice(selected, [f"c_hanged_man：移除低价值非主力牌 {selected}"])


def _rank_for_improvement(state: GameState) -> List[int]:
    return sorted(
        range(len(state.hand)),
        key=lambda index: (
            _core_score(index, state),
            not bool(card_enhancement(state.hand[index])),
            card_rank_value(state.hand[index]),
        ),
        reverse=True,
    )


def _removal_score(index: int, state: GameState) -> float:
    card = state.hand[index]
    return (
        _core_score(index, state) * 10.0
        + card_rank_value(card)
        + (25.0 if card_enhancement(card) else 0.0)
    )


def _core_score(index: int, state: GameState) -> float:
    card = state.hand[index]
    rank = card_rank_value(card)
    rank_counts = Counter(card_rank_value(item) for item in state.hand)
    score = 0.0
    if rank_counts[rank] >= 2:
        score += 6.0 + rank_counts[rank]
    if _has_rank_joker(state, rank):
        score += 6.0
    suit = card_suit(card)
    if _supports_suit_plan(state, suit):
        score += 4.0
    return score


def _supports_suit_plan(state: GameState, suit: str) -> bool:
    joker_suits = {
        _SUIT_JOKER_SUITS.get(str(joker.get("key") or "").lower())
        for joker in state.jokers
    }
    if suit in joker_suits:
        return True
    return sum(1 for card in state.hand if card_suit(card) == suit) >= 4


def _has_rank_joker(state: GameState, rank: int) -> bool:
    keys = {str(joker.get("key") or "").lower() for joker in state.jokers}
    return (rank == 14 and "j_scholar" in keys) or (rank in {10, 4} and "j_walkie_talkie" in keys)
