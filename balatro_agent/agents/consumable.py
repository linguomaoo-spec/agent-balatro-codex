from __future__ import annotations
from collections import defaultdict
from typing import Dict, List
from balatro_agent.actions import SELECTING_HAND, SHOP
from balatro_agent.agents.base import Agent
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


class ConsumableAgent(Agent):
    name = "consumable"

    # 手牌类型 → 行星牌名称关键词
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

    # 需要选择目标的塔罗牌：key -> 需要的目标牌数量
    _TARGETED_TAROT_COUNTS = {
        "c_magician": 2,
        "c_lovers": 1,
        "c_empress": 2,
        "c_strength": 1,       # 升一级：选最高分单牌
        "c_death": 2,           # 复制牌：选两张最高分牌
        "c_chariot": 1,         # 钢铁牌：选最高分牌
        "c_justice": 1,         # 玻璃牌：选最高分牌
        "c_devil": 1,           # 黄金牌：选最高分牌
        "c_heirophant": 2,      # 奖励牌：选两张
        "c_sun": 3,             # 转换最多三张牌为红心
        "c_moon": 3,            # 转换最多三张牌为梅花
        "c_world": 3,           # 转换最多三张牌为黑桃
        "c_star": 3,            # 转换最多三张牌为方块
        "c_hanged_man": 2,      # 摧毁两张选中牌
    }
    # 不需要选择目标、可以直接使用的塔罗牌
    _NO_TARGET_TAROTS = {
        "c_hermit",         # 加倍金钱
        "c_temperance",     # 获得所有Joker的卖出价值
        "c_fool",           # 复制最后使用的消耗牌
        "c_wheel_of_fortune", # 随机增强Joker
    }

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase not in {SELECTING_HAND, SHOP}:
            return []

        # 检测是否临近单手Boss（The Needle）
        approaching_needle = self._approaching_needle(state)
        has_campfire = self._has_campfire(state)

        proposals: List[ActionProposal] = []
        for index, item in enumerate(state.consumables):
            kind = item_type(item)
            key = str(item.get("key") or item.get("id") or "").lower()
            if kind == "PLANET":
                # 行星牌永久升级，评分高确保优先使用
                planet_score = 500.0
                # 渐进式牌型专精：目标牌型行星牌大幅加分
                planet_score += self._committed_planet_bonus(state, item)
                proposals.append(
                    ActionProposal(
                        "use",
                        {"consumable": index},
                        planet_score,
                        self.name,
                        confidence=0.95,
                        reasons=[f"立即使用行星牌：{item_name(item) or index}"],
                    )
                )
                continue

            # 无需目标的塔罗牌（Hermit, Temperance等）
            if key in self._NO_TARGET_TAROTS:
                score = self._no_target_tarot_score(key, state, has_campfire)
                if score > 0:
                    proposals.append(
                        ActionProposal(
                            "use",
                            {"consumable": index},
                            score,
                            self.name,
                            confidence=0.85,
                            reasons=[f"立即使用塔罗牌：{item_name(item) or index}"],
                        )
                    )
                continue

            # 需要选择目标的塔罗牌
            target_count = self._TARGETED_TAROT_COUNTS.get(key)
            if not target_count:
                # 未识别的消耗牌但有Campfire燃料价值
                if has_campfire and state.phase == SHOP:
                    proposals.append(
                        ActionProposal(
                            "use",
                            {"consumable": index},
                            250.0,
                            self.name,
                            confidence=0.7,
                            reasons=[f"Campfire燃料：{item_name(item) or index}"],
                        )
                    )
                continue

            # 需要选牌的塔罗牌只能在SELECTING_HAND阶段使用
            if state.phase != SELECTING_HAND:
                continue
            if not state.hand:
                continue
            target_indices = self._best_tarot_targets(state, target_count)
            if len(target_indices) != target_count:
                continue
            # 临近The Needle时塔罗牌使用更紧迫
            needle_bonus = 80.0 if approaching_needle and state.phase == SELECTING_HAND else 0.0
            proposals.append(
                ActionProposal(
                    "use",
                    {"consumable": index, "cards": target_indices},
                    450.0 + needle_bonus,
                    self.name,
                    confidence=0.85,
                    reasons=[f"立即使用塔罗牌：{item_name(item) or index}"],
                )
            )
        return proposals

    def _approaching_needle(self, state: GameState) -> bool:
        """检测是否临近The Needle单手Boss。"""
        name = state.blind_name.lower()
        return "the needle" in name

    def _has_campfire(self, state: GameState) -> bool:
        return any(
            str(joker.get("key") or "").lower() == "j_campfire"
            for joker in state.jokers
        )

    def _committed_planet_bonus(self, state: GameState, item: Dict[str, object]) -> float:
        """目标牌型对应的行星牌给予额外加分。"""
        committed = self._resolve_committed_hand_type(state)
        if not committed:
            return 0.0
        target_planet = self._HAND_TYPE_TO_PLANET.get(committed, "")
        if not target_planet:
            return 0.0
        item_name_lower = item_name(item).lower()
        if target_planet in item_name_lower:
            return 25.0 + state.ante * 3.0  # 锁定后目标星球牌大幅加分
        return 0.0

    def _resolve_committed_hand_type(self, state: GameState) -> Optional[str]:
        """根据当前Joker组合和ante解析目标牌型。"""
        ante = state.ante
        if ante < 3:
            return None
        joker_keys = {str(j.get("key") or "").lower() for j in state.jokers}
        if not joker_keys:
            return None

        from collections import defaultdict
        # Joker → 目标牌型信号（精简版）
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
            "j_ride_the_bus": [("two_pair", 2.0)],
            "j_even_steven": [("pair", 1.5)],
            "j_odd_todd": [("pair", 1.5)],
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

    def _no_target_tarot_score(self, key: str, state: GameState, has_campfire: bool) -> float:
        """计算无需目标的塔罗牌使用评分。"""
        if key == "c_hermit":
            # 钱少时价值高，钱多时价值低
            if state.money < 8:
                return 500.0
            elif state.money < 15:
                return 400.0
            elif state.money < 25:
                return 300.0
            return 200.0
        if key == "c_temperance":
            # 有牌可卖时才有用
            if state.hand and len(state.hand) > 0:
                if state.money < 10:
                    return 450.0
                return 350.0
            return 0.0
        if key == "c_fool":
            # 复制效果，中等优先级
            return 300.0
        if key == "c_hanged_man":
            # 摧毁瘦身，当手牌多时更有用
            if state.hand and len(state.hand) >= 5:
                return 300.0
            return 0.0
        # 其他通用增益牌
        if key == "c_wheel_of_fortune":
            base = 350.0
            if has_campfire:
                base += 50.0
            return base
        # Campfire燃料
        if has_campfire:
            return 250.0
        return 0.0

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
