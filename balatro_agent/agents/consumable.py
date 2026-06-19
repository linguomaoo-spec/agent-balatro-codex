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
                proposals.append(
                    ActionProposal(
                        "use",
                        {"consumable": index},
                        500.0,
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
