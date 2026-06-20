from __future__ import annotations
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from balatro_agent.actions import BOOSTER_OPENED
from balatro_agent.agents.base import Agent
from balatro_agent.model import (
    ActionProposal,
    GameState,
    Genome,
    item_cost,
    item_name,
    item_type,
)
from balatro_agent.agents.tarot_targets import TARGETED_TAROT_COUNTS, choose_tarot_targets


class BoosterAgent(Agent):
    name = "booster"

    # 无需目标的塔罗牌
    _NO_TARGET_TAROTS = {
        "c_hermit",
        "c_temperance",
        "c_fool",
        "c_wheel_of_fortune",
    }

    # 手牌类型 → 行星牌关键词
    _HAND_TYPE_TO_PLANET = {
        "pair": "mercury",
        "two_pair": "uranus",
        "three_kind": "saturn",
        "straight": "saturn",
        "flush": "jupiter",
        "full_house": "mars",
        "four_kind": "mars",
        "straight_flush": "neptune",
        "high_card": "pluto",
    }

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase != BOOSTER_OPENED:
            return []
        choices = state.booster_choices()
        if not choices:
            return [
                ActionProposal(
                    "pack",
                    {"skip": True},
                    1.0,
                    self.name,
                    reasons=["没有解析到补充包选项，跳过"],
                )
            ]

        proposals: List[ActionProposal] = []
        for index, card in enumerate(choices):
            key = str(card.get("key") or "").lower()
            kind = item_type(card)

            score = self._score_booster_card(card, state, genome)

            params: Dict = {"card": index}
            # 需要目标牌的塔罗牌：从手牌中选择最佳目标
            target_count = TARGETED_TAROT_COUNTS.get(key, 0)
            target_reasons: List[str] = []
            if target_count > 0:
                choice = choose_tarot_targets(key, state)
                if choice is None:
                    continue
                params["cards"] = choice.cards
                target_reasons = choice.reasons

            proposals.append(
                ActionProposal(
                    "pack",
                    params,
                    score,
                    self.name,
                    confidence=0.55,
                    reasons=[f"补充包选择：{item_name(card) or index}", *target_reasons],
                )
            )

        # 如果安全选项不够，直接跳过
        if not proposals:
            proposals.append(
                ActionProposal(
                    "pack",
                    {"skip": True},
                    10.0,  # 高分确保兜底
                    self.name,
                    confidence=0.9,
                    reasons=["所有补充包选项需要目标牌但手牌不足，跳过"],
                )
            )
        return proposals

    def _score_booster_card(
        self,
        card: Dict[str, object],
        state: GameState,
        genome: Genome,
    ) -> float:
        """根据游戏状态评估补充包卡牌价值。"""
        key = str(card.get("key") or "").lower()
        kind = item_type(card)
        base = 15.0  # 基础分

        # 行星牌评分
        if kind == "PLANET":
            base = 30.0
            # 目标牌型行星牌大幅加分
            committed = self._resolve_committed_hand_type(state)
            if committed:
                target_planet = self._HAND_TYPE_TO_PLANET.get(committed, "")
                if target_planet and target_planet in key:
                    base += 20.0 + state.ante * 2.0
            # 低等级牌型加分
            level_bonus = self._planet_level_bonus(state, card)
            base += level_bonus

        # 塔罗牌评分
        elif kind in ("TAROT", "CONSUMABLE"):
            # 无需目标的塔罗牌
            if key in self._NO_TARGET_TAROTS:
                if key == "c_hermit":
                    if state.money < 10:
                        base = 38.0
                    elif state.money < 20:
                        base = 28.0
                    else:
                        base = 18.0
                elif key == "c_temperance":
                    base = 22.0 if state.money < 15 else 16.0
                elif key == "c_fool":
                    base = 18.0
                elif key == "c_wheel_of_fortune":
                    base = 22.0
                    if self._has_campfire(state):
                        base += 5.0
            else:
                # 需要目标的塔罗牌：手牌充足时价值更高
                target_count = TARGETED_TAROT_COUNTS.get(key, 0)
                if state.hand and len(state.hand) >= target_count:
                    base = 20.0
                    # 万能牌、奖励牌、钢铁牌价值更高
                    if key in ("c_lovers", "c_chariot", "c_justice"):
                        base += 4.0
                    if key == "c_death" and len(state.hand) >= 3:
                        base += 6.0  # 复制好牌
                else:
                    base = 10.0  # 手牌不足时降分

            # Campfire 燃料价值
            if self._has_campfire(state):
                base += 5.0

            # 临近单手Boss时塔罗牌价值提升
            if "the needle" in state.blind_name.lower():
                base += 6.0

        # 鬼牌评分
        elif kind == "SPECTRAL":
            base = 22.0

        # 小丑牌包（Buffoon Pack）
        elif kind == "JOKER":
            base = 18.0
            if len(state.jokers) < state.joker_limit:
                base += 8.0

        return base

    def _resolve_committed_hand_type(self, state: GameState) -> Optional[str]:
        """根据当前Joker组合解析目标牌型。"""
        ante = state.ante
        if ante < 3:
            return None
        joker_keys = {str(j.get("key") or "").lower() for j in state.jokers}
        if not joker_keys:
            return None

        _JOKER_SIGNAL = {
            "j_half": [("pair", 3.0), ("high_card", 2.5)],
            "j_sly": [("pair", 3.0), ("two_pair", 2.0)],
            "j_photograph": [("pair", 2.5), ("high_card", 2.5)],
            "j_hanging_chad": [("high_card", 3.0), ("pair", 2.0)],
            "j_scholar": [("pair", 2.5), ("high_card", 2.5)],
            "j_walkie_talkie": [("two_pair", 2.5), ("pair", 1.5)],
            "j_runner": [("straight", 3.5)],
            "j_lusty_joker": [("flush", 3.0)],
            "j_greedy_joker": [("flush", 3.0)],
            "j_wrathful_joker": [("flush", 3.0)],
            "j_gluttenous_joker": [("flush", 3.0)],
            "j_card_sharp": [("__repeat__", 4.0)],
            "j_supernova": [("__consistency__", 3.5)],
            "j_trousers": [("two_pair", 3.0)],
        }

        signal_scores: Dict[str, float] = defaultdict(float)
        consistency_bonus = 0.0
        repeat_bonus = 0.0

        for key in joker_keys:
            signals = _JOKER_SIGNAL.get(key, [])
            for hand_type, strength in signals:
                if hand_type == "__consistency__":
                    consistency_bonus += strength
                elif hand_type == "__repeat__":
                    repeat_bonus += strength
                else:
                    signal_scores[hand_type] = signal_scores.get(hand_type, 0) + strength

        if consistency_bonus > 0 and signal_scores:
            best_type = max(signal_scores, key=signal_scores.get)
            signal_scores[best_type] += consistency_bonus * 0.8
        if repeat_bonus > 0:
            for small_type in ("pair", "high_card", "two_pair"):
                if small_type in signal_scores:
                    signal_scores[small_type] += repeat_bonus

        if not signal_scores:
            return None

        best_type = max(signal_scores, key=signal_scores.get)
        best_score = signal_scores[best_type]
        total_score = sum(signal_scores.values()) + 1.0
        confidence = best_score / total_score

        if ante >= 6:
            if best_score >= 2.5 or (best_score >= 1.5 and confidence >= 0.25):
                return best_type
        elif ante >= 3:
            if (best_score >= 5.0 and confidence >= 0.30) or (best_score >= 3.5 and confidence >= 0.35):
                return best_type
        return None

    def _has_campfire(self, state: GameState) -> bool:
        return any(
            str(joker.get("key") or "").lower() == "j_campfire"
            for joker in state.jokers
        )

    def _planet_level_bonus(self, state: GameState, item: Dict[str, object]) -> float:
        """低等级手牌的行星牌价值更高。"""
        name = item_name(item).lower()
        raw = state.raw.get("hands") if isinstance(state.raw, dict) else None
        if not isinstance(raw, dict):
            return 0.0
        for hand_name, hand_state in raw.items():
            if not isinstance(hand_state, dict):
                continue
            if hand_name.lower() not in name:
                continue
            level = float(hand_state.get("level", 1) or 1)
            if level < 3:
                return 8.0
            if level < 5:
                return 4.0
            return 1.0
        return 0.0
