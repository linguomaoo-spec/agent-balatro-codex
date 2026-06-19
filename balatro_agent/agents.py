from __future__ import annotations

from collections import defaultdict
from math import comb
from itertools import combinations
from typing import Dict, Iterable, List, Optional, Tuple

from balatro_agent.actions import BLIND_SELECT, BOOSTER_OPENED, ROUND_EVAL, SELECTING_HAND, SHOP
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


class Agent:
    name = "agent"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        raise NotImplementedError

    def propose_search(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        return self.propose(state, genome)


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

    # Boss盲注限制检测
    _BOSS_ONLY_ONE_TYPE = {"the mouth", "the mouth "}
    _BOSS_DEBUFF_SUIT = {
        "the head": "H",
        "the goad": "S",
        "the club": "C",
        "the window": "D",
    }
    _BOSS_VERY_LARGE = {"the wall", "violet vessel", "crimson heart"}
    _BOSS_DISCARD_COST = {"the hook", "the hook "}
    _BOSS_ONE_HAND = {"the needle", "the needle "}

    def _is_needle_boss(self, state: GameState) -> bool:
        """检测当前是否为The Needle等单手Boss。"""
        name = state.blind_name.lower().strip()
        return any(boss in name for boss in self._BOSS_ONE_HAND)

    def _boss_info(self, state: GameState) -> dict:
        """解析当前Boss盲注的限制条件。"""
        info = {"only_one_type": False, "debuff_suit": "", "very_large": False,
                "discard_costs_hand": False}
        name = state.blind_name.lower().strip()
        if not name:
            return info
        if any(boss in name for boss in self._BOSS_ONLY_ONE_TYPE):
            info["only_one_type"] = True
        for boss, suit in self._BOSS_DEBUFF_SUIT.items():
            if boss in name:
                info["debuff_suit"] = suit
        if any(boss in name for boss in self._BOSS_VERY_LARGE):
            info["very_large"] = True
        if any(boss in name for boss in self._BOSS_DISCARD_COST):
            info["discard_costs_hand"] = True
        return info

    def _joker_hand_preference(self, state: GameState) -> dict:
        """根据拥有的Joker确定最优牌型方向。返回 {hand_type: bonus_score}。"""
        prefs: dict = {}
        joker_keys = set(self._joker_keys(state))

        # 对子/高牌方向（小牌型）- 温和引导而非压倒
        if "j_half" in joker_keys:
            prefs["pair"] = prefs.get("pair", 0) + 35
            prefs["high_card"] = prefs.get("high_card", 0) + 25
            prefs["three_kind"] = prefs.get("three_kind", 0) + 15
        if "j_photograph" in joker_keys:
            prefs["pair"] = prefs.get("pair", 0) + 20
            prefs["high_card"] = prefs.get("high_card", 0) + 20
        if "j_hanging_chad" in joker_keys:
            prefs["high_card"] = prefs.get("high_card", 0) + 15
            prefs["pair"] = prefs.get("pair", 0) + 10

        # 顺子方向
        if "j_runner" in joker_keys:
            prefs["straight"] = prefs.get("straight", 0) + 40
        if "j_superposition" in joker_keys:
            prefs["straight"] = prefs.get("straight", 0) + 30

        # 同花方向
        suit_jokers = {"j_lusty_joker", "j_wrathful_joker", "j_greedy_joker", "j_gluttenous_joker"}
        if any(j in joker_keys for j in suit_jokers):
            prefs["flush"] = prefs.get("flush", 0) + 35
        if "j_ancient" in joker_keys:
            prefs["flush"] = prefs.get("flush", 0) + 25

        # 特定点数方向
        if "j_walkie_talkie" in joker_keys:
            prefs["two_pair"] = prefs.get("two_pair", 0) + 15
            prefs["pair"] = prefs.get("pair", 0) + 10
        if "j_scholar" in joker_keys:
            prefs["pair"] = prefs.get("pair", 0) + 15
            prefs["high_card"] = prefs.get("high_card", 0) + 20
        if "j_even_steven" in joker_keys:
            prefs["pair"] = prefs.get("pair", 0) + 8
        if "j_odd_todd" in joker_keys:
            prefs["pair"] = prefs.get("pair", 0) + 8

        # 通用方向
        if "j_ride_the_bus" in joker_keys:
            prefs["two_pair"] = prefs.get("two_pair", 0) + 12
            prefs["straight"] = prefs.get("straight", 0) + 10
        if "j_green_joker" in joker_keys:
            prefs["pair"] = prefs.get("pair", 0) + 8
        return prefs

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
        rearrange_order = self._hand_rearrange_order(state, hand, play_indices)
        if rearrange_order:
            proposals.append(
                ActionProposal(
                    "rearrange",
                    {"hand": rearrange_order},
                    play_score + 0.1,
                    self.name,
                    confidence=0.9,
                    reasons=["先把重触发/首张触发牌移动到最佳结算顺序"],
                )
            )

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

    def propose_search(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        proposals = self.propose(state, genome)
        if state.phase != SELECTING_HAND or not state.hand:
            return proposals

        hand = state.hand
        requires_five = self._requires_five_card_play(state)
        play_candidates: List[ActionProposal] = []
        for size in range(1, min(5, len(hand)) + 1):
            if requires_five and size != 5:
                continue
            for combo in combinations(range(len(hand)), size):
                indices = list(combo)
                label = self._classify_play(hand, indices, allow_kickers=requires_five)
                if label == "invalid":
                    continue
                ordered = self._ordered_play_indices(state, hand, indices)
                score = (
                    self._score_play(hand, ordered, label)
                    + self._hand_value_bonus(state, label)
                    + self._joker_play_bonus(state, hand, ordered)
                ) * genome.weight("play")
                play_candidates.append(
                    ActionProposal(
                        "play",
                        {"cards": ordered},
                        score,
                        self.name,
                        confidence=0.55,
                        reasons=[f"搜索候选牌型：{label}"],
                    )
                )

        combined: List[ActionProposal] = []
        seen = set()
        for proposal in proposals + sorted(play_candidates, key=lambda item: item.score, reverse=True):
            key = (proposal.method, tuple(proposal.params.get("cards", [])))
            if key in seen:
                continue
            if proposal.method == "play" and sum(1 for item in combined if item.method == "play") >= 4:
                continue
            if proposal.method == "discard" and sum(1 for item in combined if item.method == "discard") >= 2:
                continue
            seen.add(key)
            combined.append(proposal)

        if state.discards_remaining > 0:
            for play in [item for item in combined if item.method == "play"]:
                keep = set(play.params.get("cards", []))
                discard = [index for index in range(len(hand)) if index not in keep][:5]
                key = ("discard", tuple(discard))
                if not discard or key in seen:
                    continue
                if sum(1 for item in combined if item.method == "discard") >= 2:
                    break
                seen.add(key)
                combined.append(
                    ActionProposal(
                        "discard",
                        {"cards": discard},
                        play.score * genome.weight("discard"),
                        self.name,
                        confidence=0.35,
                        reasons=["搜索候选：保留另一组高价值出牌"],
                    )
                )
        return combined

    def _best_play_indices(self, hand: List[Dict[str, object]], state: GameState) -> Tuple[List[int], str]:
        best_indices: List[int] = []
        best_label = "high_card"
        best_score = float("-inf")
        best_rank_sum = float("-inf")

        # 最后一手且无弃牌：全力一搏
        is_last_hand_all_in = (
            state.hands_remaining == 1
            and state.discards_remaining == 0
            and state.blind_requirement > state.score
        )
        requires_five_card_play = self._requires_five_card_play(state)

        # Boss感知 + Joker方向
        boss = self._boss_info(state)
        joker_prefs = self._joker_hand_preference(state)
        half_joker_active = "j_half" in set(self._joker_keys(state))
        # The Mouth: 只能出一种牌型，大幅强化Joker方向让agent自然锁定
        mouth_boss = boss["only_one_type"]

        for size in range(1, min(5, len(hand)) + 1):
            if requires_five_card_play and size != 5:
                continue
            for combo in combinations(range(len(hand)), size):
                indices = list(combo)
                hand_label = self._classify_play(
                    hand,
                    indices,
                    allow_kickers=requires_five_card_play,
                )
                if hand_label == "invalid":
                    continue
                # Boss花色削弱: 跳过被削同花
                if boss["debuff_suit"] and hand_label == "flush":
                    cards = [hand[i] for i in indices]
                    if any(card_suit(c) == boss["debuff_suit"] for c in cards):
                        continue

                base_score = (
                    self._score_play(hand, indices, hand_label)
                    + self._hand_value_bonus(state, hand_label)
                    + self._joker_play_bonus(state, hand, indices)
                )
                # Joker建牌方向奖励
                base_score += joker_prefs.get(hand_label, 0)
                # The Mouth: 极度强化Joker方向，确保一直选同一种牌型
                if mouth_boss:
                    base_score += joker_prefs.get(hand_label, 0) * 2.0
                # Boss超大盲注：倾向高分
                if boss["very_large"]:
                    base_score += size * 8.0
                if half_joker_active and not requires_five_card_play:
                    if 1 <= size <= 3:
                        base_score += 40.0
                    else:
                        base_score -= 20.0
                rank_sum = sum(card_rank_value(hand[index]) for index in indices)

                if is_last_hand_all_in:
                    # 全力模式：最大化绝对得分，size越大越好（更多牌触发更多joker效果）
                    all_in_score = base_score + size * 20.0
                    if (all_in_score, size, rank_sum) > (best_score, len(best_indices), best_rank_sum):
                        best_indices = indices
                        best_label = hand_label
                        best_score = all_in_score
                        best_rank_sum = rank_sum
                else:
                    score = base_score
                    # 大分差模式：距离目标分数很远时，倾向打出更多牌
                    shortfall = max(0.0, float(state.blind_requirement - state.score))
                    hands_left = max(1, state.hands_remaining)
                    if shortfall > 0 and hands_left <= 2:
                        # 分数紧张时，大牌型比单牌效率更重要
                        score += size * 12.0
                    if (score, rank_sum, -len(indices)) > (best_score, best_rank_sum, -len(best_indices)):
                        best_indices = indices
                        best_label = hand_label
                        best_score = score
                        best_rank_sum = rank_sum

        if best_indices:
            trigger_override = self._single_trigger_override(state, hand, best_indices, best_label)
            if trigger_override:
                return trigger_override, "high_card"
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

    def _classify_play(
        self,
        hand: List[Dict[str, object]],
        indices: List[int],
        allow_kickers: bool = False,
    ) -> str:
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
        if counts == [4] or (allow_kickers and len(cards) == 5 and counts[:1] == [4]):
            return "four_kind"
        if counts == [3, 2]:
            return "full_house"
        if is_flush:
            return "flush"
        if is_straight:
            return "straight"
        if counts == [3] or (allow_kickers and len(cards) == 5 and counts[:1] == [3]):
            return "three_kind"
        if counts == [2, 2] or (allow_kickers and len(cards) == 5 and counts[:2] == [2, 2]):
            return "two_pair"
        if counts == [2] or (allow_kickers and len(cards) == 5 and counts[:1] == [2]):
            return "pair"
        if len(cards) == 1:
            return "high_card"
        if allow_kickers and len(cards) == 5:
            return "high_card"
        return "invalid"

    def _requires_five_card_play(self, state: GameState) -> bool:
        blind_name = state.blind_name.lower()
        return "psychic" in blind_name or "bl_psychic" in blind_name

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

        boss = self._boss_info(state)
        # The Hook: 弃牌消耗出手次数，大幅减少弃牌意愿
        if boss["discard_costs_hand"] and hands_remaining <= 2:
            return [], float("-inf")
        # The Needle / 单手Boss: 必须找到能过盲的牌，极度激进弃牌
        needle_pressure = self._needle_pressure_keep(state, hand, play_indices, hand_label, play_score)
        if needle_pressure:
            return needle_pressure, play_score + 40.0
        desperation_keep_indices = self._last_hand_desperation_keep_plan(
            state,
            hand,
            play_indices,
            hand_label,
        )
        if desperation_keep_indices:
            desperation_discard = [
                index for index in range(len(hand)) if index not in desperation_keep_indices
            ]
            if desperation_discard:
                return desperation_discard[: min(5, len(desperation_discard))], play_score + 35.0

        if self._should_play_close_last_made_hand(state, hand_label, hands_remaining, discards_remaining):
            return [], play_score

        # 牌库将尽时更激进弃牌：每次弃牌后手牌都会变少，必须尽快找到大牌型
        deck_depleted = state.deck_card_count < 5
        if deck_depleted and hand_label in {"high_card", "pair", "two_pair"}:
            shortfall = max(0.0, float(state.blind_requirement - state.score))
            target_per_hand = shortfall / max(1, hands_remaining)
            if play_score < target_per_hand * 0.5:
                # 强行弃牌,在牌库耗尽前找大牌型
                keep_indices, potential = self._best_keep_plan(state, hand)
                if keep_indices and potential > play_score * 1.2:
                    discard = [i for i in range(len(hand)) if i not in keep_indices]
                    return discard[: min(5, len(discard))], potential

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

    def _last_hand_desperation_keep_plan(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        play_indices: List[int],
        hand_label: str,
    ) -> List[int]:
        if state.jokers:
            return []
        if state.hands_remaining != 1 or state.discards_remaining <= 0:
            return []

        shortfall = max(0.0, float(state.blind_requirement - state.score))
        if shortfall <= 0:
            return []
        if self._estimated_plain_score(hand, play_indices, hand_label) >= shortfall:
            return []

        best_indices: List[int] = []
        best_score = float("-inf")
        for size in range(2, min(5, len(hand)) + 1):
            for combo in combinations(range(len(hand)), size):
                indices = list(combo)
                score = self._desperation_draw_score(hand, indices)
                if score > best_score:
                    best_indices = indices
                    best_score = score
        if best_score < 200.0:
            return []
        return sorted(best_indices)

    def _desperation_draw_score(
        self,
        hand: List[Dict[str, object]],
        indices: List[int],
    ) -> float:
        cards = [hand[index] for index in indices]
        rank_values = [card_rank_value(card) for card in cards]
        if any(rank <= 0 for rank in rank_values):
            return float("-inf")

        max_flush_group = self._max_flush_group(cards)
        longest_run = self._longest_run(rank_values)
        if max_flush_group < 3 and longest_run < 3:
            return float("-inf")

        score = sum(rank_values) * 0.6 - len(indices) * 10.0
        if max_flush_group >= 3:
            score += max_flush_group * 85.0
        if longest_run >= 3:
            score += longest_run * 75.0
        return score

    def _estimated_plain_score(
        self,
        hand: List[Dict[str, object]],
        indices: List[int],
        hand_label: str,
    ) -> float:
        base_values = {
            "straight_flush": (100.0, 8.0),
            "four_kind": (60.0, 7.0),
            "full_house": (40.0, 4.0),
            "flush": (35.0, 4.0),
            "straight": (30.0, 4.0),
            "three_kind": (30.0, 3.0),
            "two_pair": (20.0, 2.0),
            "pair": (10.0, 2.0),
            "high_card": (5.0, 1.0),
        }
        base_chips, mult = base_values.get(hand_label, (0.0, 1.0))
        card_chips = sum(self._rank_chip_value(card_rank_value(hand[index])) for index in indices)
        return (base_chips + card_chips) * mult

    def _rank_chip_value(self, rank_value: int) -> int:
        if rank_value == 14:
            return 11
        if rank_value >= 10:
            return 10
        return max(0, rank_value)

    def _should_play_close_last_made_hand(
        self,
        state: GameState,
        hand_label: str,
        hands_remaining: int,
        discards_remaining: int,
    ) -> bool:
        if hands_remaining != 1 or discards_remaining > 1:
            return False
        if not state.jokers or hand_label == "high_card":
            return False
        shortfall = max(0.0, float(state.blind_requirement - state.score))
        return 0.0 < shortfall <= 1000.0

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

        paired_indices = {index for indices in pair_groups for index in indices}
        premium_singletons = [
            index
            for index, card in enumerate(hand)
            if index not in paired_indices and self._should_keep_premium_singleton(state, card)
        ]
        keep = sorted(
            set(index for indices in pair_groups for index in indices[:2]) | set(premium_singletons)
        )
        if len(keep) >= len(hand):
            return []
        return keep

    def _needle_pressure_keep(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        play_indices: List[int],
        hand_label: str,
        play_score: float,
    ) -> List[int]:
        """The Needle单手Boss：只有一次出牌机会，必须激进弃牌找到能过盲的牌型。"""
        if not self._is_needle_boss(state):
            return []
        if state.hands_remaining != 1 or state.discards_remaining <= 0:
            return []
        shortfall = max(0.0, float(state.blind_requirement - state.score))
        if shortfall <= 0:
            return []
        # 当前手牌能过盲就不用弃牌
        if play_score >= shortfall * 0.85:
            return []
        # 拼命找大牌型：保留能组成flush/straight/高对的牌
        rank_groups: Dict[int, List[int]] = defaultdict(list)
        suit_groups: Dict[str, List[int]] = defaultdict(list)
        for index, card in enumerate(hand):
            rank_value = card_rank_value(card)
            if rank_value <= 0:
                continue
            rank_groups[rank_value].append(index)
            suit = card_suit(card)
            if suit:
                suit_groups[suit].append(index)
        # 保留最大的对子组和最多同花组
        best_rank_group = max(rank_groups.values(), key=len, default=[])
        best_suit_group = max(suit_groups.values(), key=len, default=[])
        keep = set(best_rank_group[:2] + best_suit_group[:4])
        # 保留高分单牌
        premium = sorted(
            (i for i, c in enumerate(hand) if i not in keep and card_rank_value(c) >= 10),
            key=lambda i: card_rank_value(hand[i]),
            reverse=True,
        )
        keep.update(premium[:3])
        if len(keep) >= len(hand) or len(keep) < 2:
            return []
        discard = [i for i in range(len(hand)) if i not in keep]
        return discard[: min(5, len(discard))]

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
            return max(score, potential_score)

        shortfall = max(0.0, float(state.blind_requirement - state.score))
        if shortfall <= 0:
            return score

        target_per_hand = shortfall / max(1, state.hands_remaining)
        if play_score >= target_per_hand * 0.65:
            return score

        improvement_bonus = max(0.0, potential_score - play_score) * 0.85
        pressure_bonus = max(0.0, target_per_hand - play_score) * 0.30
        # 手数越少，弃牌换手越紧迫
        urgency_mult = 1.0 + max(0.0, (3 - state.hands_remaining)) * 0.3
        # Boss超大盲注：更激进弃牌找大牌
        boss = self._boss_info(state)
        if boss["very_large"]:
            urgency_mult += 0.4
        # The Mouth: 强化找Joker目标牌型
        if boss["only_one_type"]:
            urgency_mult += 0.3
        return score + min(280.0, (improvement_bonus + pressure_bonus) * urgency_mult)

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
        score += self._draw_odds_bonus(state, hand, cards)
        # Joker方向：保留有助于目标牌型的牌
        joker_prefs = self._joker_hand_preference(state)
        if joker_prefs:
            top_pref = max(joker_prefs.values())
            for card in cards:
                synergy = self._card_synergy_bonus(state, card)
                if synergy > 10:
                    score += synergy * 0.3
        return score

    def _draw_odds_bonus(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        keep_cards: List[Dict[str, object]],
    ) -> float:
        draw_count = min(5, max(0, len(hand) - len(keep_cards)))
        if draw_count <= 0:
            return 0.0

        draw_pool = self._draw_pool_cards(state, hand)
        total = len(draw_pool)
        if total <= 0:
            return 0.0

        rank_values = [card_rank_value(card) for card in keep_cards]
        rank_counts: Dict[int, int] = defaultdict(int)
        for rank_value in rank_values:
            if rank_value > 0:
                rank_counts[rank_value] += 1

        bonus = 0.0
        max_rank_group = max(rank_counts.values(), default=0)
        if max_rank_group >= 2:
            best_rank = max(
                (rank for rank, count in rank_counts.items() if count >= 2),
                key=lambda rank: (rank_counts[rank], rank),
            )
            outs = sum(1 for card in draw_pool if card_rank_value(card) == best_rank)
            bonus += self._draw_success_probability(total, outs, draw_count) * 210.0

        max_suit_group = self._max_flush_group(keep_cards)
        if len(keep_cards) >= 4 and max_suit_group >= 4:
            suit_counts: Dict[str, int] = defaultdict(int)
            for card in keep_cards:
                suit = card_suit(card)
                if suit:
                    suit_counts[suit] += 1
            if suit_counts:
                target_suit = max(suit_counts, key=suit_counts.get)
                outs = sum(1 for card in draw_pool if card_suit(card) == target_suit)
                bonus += self._draw_success_probability(total, outs, draw_count) * 150.0

        straight_outs = self._straight_out_ranks(rank_values)
        if straight_outs:
            outs = sum(1 for card in draw_pool if card_rank_value(card) in straight_outs)
            bonus += self._draw_success_probability(total, outs, draw_count) * 140.0

        return bonus

    def _draw_pool_cards(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
    ) -> List[Dict[str, object]]:
        deck_cards = state.deck_cards
        if deck_cards:
            return deck_cards
        if not state.discard_pile_cards:
            return []

        unavailable = {card_identity(card) for card in hand}
        unavailable.update(card_identity(card) for card in state.discard_pile_cards)
        ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
        suits = ["H", "D", "C", "S"]
        return [
            {"rank": rank, "suit": suit}
            for suit in suits
            for rank in ranks
            if f"{suit}_{rank}" not in unavailable
        ]

    def _draw_success_probability(self, total: int, outs: int, draw_count: int) -> float:
        if total <= 0 or outs <= 0 or draw_count <= 0:
            return 0.0
        if draw_count >= total:
            return 1.0
        misses = max(0, total - outs)
        if misses < draw_count:
            return 1.0
        return 1.0 - (comb(misses, draw_count) / comb(total, draw_count))

    def _straight_out_ranks(self, rank_values: List[int]) -> List[int]:
        unique = {rank for rank in rank_values if rank > 0}
        if len(unique) < 4:
            return []
        straights = [
            {14, 2, 3, 4, 5},
            {2, 3, 4, 5, 6},
            {3, 4, 5, 6, 7},
            {4, 5, 6, 7, 8},
            {5, 6, 7, 8, 9},
            {6, 7, 8, 9, 10},
            {7, 8, 9, 10, 11},
            {8, 9, 10, 11, 12},
            {9, 10, 11, 12, 13},
            {10, 11, 12, 13, 14},
        ]
        outs = set()
        for straight in straights:
            held = straight & unique
            if len(held) == 4:
                outs.update(straight - held)
        return sorted(outs)

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

    def _hand_rearrange_order(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        indices: List[int],
    ) -> List[int]:
        if not self._should_rearrange_hand_for_scoring(state, hand, indices):
            return []
        ordered = self._ordered_play_indices(state, hand, indices)
        selected = set(ordered)
        target = ordered + [index for index in range(len(hand)) if index not in selected]
        if target == list(range(len(hand))):
            return []
        return target

    def _should_rearrange_hand_for_scoring(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        indices: List[int],
    ) -> bool:
        if len(indices) <= 0 or len(hand) <= 1:
            return False
        joker_keys = set(self._joker_keys(state))
        retrigger_keys = {"j_hanging_chad", "j_hack", "j_dusk"}
        has_enhanced_play = any(card_enhancement(hand[index]) for index in indices)
        if has_enhanced_play and (retrigger_keys & joker_keys):
            return True
        if "j_photograph" in joker_keys:
            return any(card_rank_value(hand[index]) in {11, 12, 13} for index in indices)
        return False

    def _should_protect_singleton_play(self, state: GameState, card: Dict[str, object]) -> bool:
        joker_keys = set(self._joker_keys(state))
        rank_value = card_rank_value(card)
        return "j_scholar" in joker_keys and rank_value == 14

    def _should_keep_premium_singleton(self, state: GameState, card: Dict[str, object]) -> bool:
        joker_keys = set(self._joker_keys(state))
        rank_value = card_rank_value(card)
        if "j_scholar" in joker_keys and rank_value == 14:
            return True
        if (
            "j_photograph" in joker_keys
            and rank_value in {11, 12, 13}
            and ({"j_hanging_chad", "j_half"} & joker_keys)
        ):
            return True
        return False

    def _single_trigger_override(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        best_indices: List[int],
        hand_label: str,
    ) -> List[int]:
        joker_keys = set(self._joker_keys(state))
        if "j_photograph" not in joker_keys or not ({"j_hanging_chad", "j_half"} & joker_keys):
            return []
        if hand_label not in {"pair", "two_pair"}:
            return []
        if state.discards_remaining > 1 and state.hands_remaining > 2:
            return []

        face_indices = [
            index for index in best_indices if card_rank_value(hand[index]) in {11, 12, 13}
        ]
        if not face_indices:
            return []
        return [
            max(
                face_indices,
                key=lambda index: (
                    self._card_priority(state, hand[index]),
                    card_rank_value(hand[index]),
                ),
            )
        ]

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


class ShopAgent(Agent):
    name = "shop"
    _JOKER_REPLACEMENT_MARGIN = 15.0
    _NARROW_CONDITIONAL_JOKERS = {
        "j_clever",
        "j_sly",
        "j_droll",
        "j_zany",
        "j_wily",
        "j_mystic_summit",
        "j_hack",
    }

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
            sell_proposal = self._sell_joker_proposal(state, money, genome)
            if sell_proposal is not None:
                proposals.append(sell_proposal)

        # 自动卖出已失效的Joker（如牌库空时的Erosion）
        dead_sell = self._sell_dead_joker_proposal(state)
        if dead_sell is not None:
            proposals.append(dead_sell)

        for index, item in enumerate(state.shop_cards()):
            cost = item_cost(item)
            if cost and cost > money:
                continue
            kind = item_type(item)
            if kind == "JOKER":
                if joker_slots_full:
                    continue
                base = self._joker_strength(item, state, genome) * genome.weight("buy_joker")
                # Boss感知调整
                base += self._boss_aware_joker_adjust(item, state)
                # 后期低分Joker不值得购买
                if state.ante >= 4 and self._joker_strength(item, state, genome) < 20.0:
                    base *= 0.5
                # ante 5+: chip Joker降权，mult/X-mult升权
                if state.ante >= 5:
                    key = str(item.get("key") or "").lower()
                    name_lower = item_name(item).lower()
                    effect = ""
                    value = item.get("value")
                    if isinstance(value, dict):
                        effect = str(value.get("effect") or "").lower()
                    is_chip_joker = ("chip" in name_lower or "筹码" in effect) and \
                        "mult" not in name_lower and "倍率" not in effect and \
                        "x" not in name_lower
                    if is_chip_joker:
                        base *= 0.65
                    if "x" in name_lower or "x" in effect:
                        base *= 1.25
            elif kind in {"CONSUMABLE", "TAROT", "PLANET", "SPECTRAL"}:
                if consumable_slots_full:
                    continue
                base = self._consumable_buy_score(item, state, genome)
                if base is None:
                    continue
                # 消耗品槽全空时提升塔罗牌购买意愿——确保进入盲注时有即时战力
                if len(state.consumables) == 0 and kind != "PLANET":
                    base *= genome.weight("consumable_empty_slot_bonus", 1.5)
            else:
                base = 5.0
            base += self._synergy_bonus(item, state, genome)
            cash_reserve = int(
                genome.weight("cash_reserve", 8.0)
                + state.ante * genome.weight("cash_reserve_ante_scale", 1.5)
            )
            base -= max(0, cost - max(0, money - cash_reserve)) * 0.7
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
        genome: Genome,
    ) -> Optional[ActionProposal]:
        owned = list(state.jokers)
        if not owned:
            return None

        chad_sell = self._hanging_chad_small_build_sell_proposal(state, money)
        if chad_sell is not None:
            return chad_sell

        abstract_sell = self._abstract_over_popcorn_chad_sell_proposal(state, money)
        if abstract_sell is not None:
            return abstract_sell

        best_shop_option: Optional[Tuple[float, int, Dict[str, object]]] = None
        for index, item in enumerate(state.shop_cards()):
            if item_type(item) != "JOKER":
                continue
            cost = item_cost(item)
            if cost and cost > money:
                continue
            score = self._joker_strength(item, state, genome)
            candidate = (score, index, item)
            if best_shop_option is None or candidate > best_shop_option:
                best_shop_option = candidate

        if best_shop_option is None:
            return None

        weakest_owned = min(
            (
                (self._joker_strength(joker, state, genome), index, joker)
                for index, joker in enumerate(owned)
            ),
            default=None,
        )
        if weakest_owned is None:
            return None

        best_score, _, best_item = best_shop_option
        weakest_score, weakest_index, weakest_item = weakest_owned
        # 保护Blue Joker：Half+Chad构筑中的筹码基石不应被非chip非xmult替换
        weakest_key = str(weakest_item.get("key") or "").lower()
        if weakest_key == "j_blue_joker" or "blue joker" in item_name(weakest_item).lower():
            owned_keys = {str(j.get("key") or "").lower() for j in state.jokers}
            if {"j_half", "j_hanging_chad"} & owned_keys:
                best_key = str(best_item.get("key") or "").lower()
                best_name = item_name(best_item).lower()
                is_chip = "chip" in best_name or "筹码" in str(best_item.get("value", {})).lower()
                is_xmult = "x" in best_name or "x" in best_key
                if not is_chip and not is_xmult:
                    return None  # 不替换Blue Joker除非换的是chip或xmult
        # ante 4+ 无X-mult时降低X-mult Joker替换门槛
        margin = genome.weight("joker_replacement_margin", self._JOKER_REPLACEMENT_MARGIN)
        best_key = str(best_item.get("key") or "").lower()
        best_name = item_name(best_item).lower()
        # Photograph-Chad协同保护：卖Chad换Photograph时，Photograph失去Chad加成
        if best_key == "j_photograph" or "photograph" in best_name:
            weakest_key = str(weakest_item.get("key") or "").lower()
            if weakest_key == "j_hanging_chad" or "hanging chad" in item_name(weakest_item).lower():
                best_score -= 14.0  # 扣除Chad加成(+10)和Half+Chad联合加成(+4)
        # Chad主动保护：Half构筑中的重触发核心，不卖Chad换非重触发/非Xmult
        weakest_key_ck = str(weakest_item.get("key") or "").lower()
        if weakest_key_ck == "j_hanging_chad" or "hanging chad" in item_name(weakest_item).lower():
            owned_keys = {str(j.get("key") or "").lower() for j in state.jokers}
            if "j_half" in owned_keys:
                best_value = best_item.get("value", {})
                best_effect = str(best_value.get("effect", "") or "").lower() if isinstance(best_value, dict) else ""
                is_retrigger = "retrigger" in best_effect or "trigger" in best_effect
                is_strong_xmult = ("x" in best_name or "x" in best_key) and best_score > 45
                if not is_retrigger and not is_strong_xmult:
                    return None  # Chad+Half核心不容替换
        xmult_priority_ante = int(genome.weight("xmult_priority_ante", 4.0))
        if state.ante >= xmult_priority_ante and ("x" in best_name or "x" in best_key):
            has_xmult = any(
                "x" in str(owned.get("key", "") or "").lower()
                or "x" in str(owned.get("name", "") or "").lower()
                for owned in state.jokers
            )
            if not has_xmult:
                margin = 4.0  # 大幅降低门槛，鼓励入手首张X-mult
        if best_score < weakest_score + margin:
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

    def _hanging_chad_small_build_sell_proposal(
        self,
        state: GameState,
        money: int,
    ) -> Optional[ActionProposal]:
        owned_keys = {str(joker.get("key") or "").lower() for joker in state.jokers}
        if not {
            "j_sly",
            "j_scary_face",
            "j_half",
            "j_supernova",
            "j_popcorn",
        }.issubset(owned_keys):
            return None

        chad_available = False
        for item in state.shop_cards():
            key = str(item.get("key") or item.get("id") or "").lower()
            if key != "j_hanging_chad" or item_type(item) != "JOKER":
                continue
            cost = item_cost(item)
            if cost and cost > money:
                continue
            chad_available = True
            break
        if not chad_available:
            return None

        for index, joker in enumerate(state.jokers):
            if str(joker.get("key") or "").lower() == "j_supernova":
                return ActionProposal(
                    "sell",
                    {"joker": index},
                    44.0,
                    self.name,
                    confidence=0.6,
                    reasons=[
                        "卖出 Supernova 试验 Hanging Chad 小牌型触发",
                        "保留 Sly/Scary Face/Half/Popcorn 核心",
                    ],
                )
        return None

    def _abstract_over_popcorn_chad_sell_proposal(
        self,
        state: GameState,
        money: int,
    ) -> Optional[ActionProposal]:
        owned_keys = {str(joker.get("key") or "").lower() for joker in state.jokers}
        if not self._is_chad_small_hand_build_keys(owned_keys):
            return None

        abstract_available = False
        for item in state.shop_cards():
            key = str(item.get("key") or item.get("id") or "").lower()
            if key != "j_abstract" or item_type(item) != "JOKER":
                continue
            cost = item_cost(item)
            if cost and cost > money:
                continue
            abstract_available = True
            break
        if not abstract_available:
            return None

        for index, joker in enumerate(state.jokers):
            if str(joker.get("key") or "").lower() == "j_popcorn":
                return ActionProposal(
                    "sell",
                    {"joker": index},
                    40.0,
                    self.name,
                    confidence=0.6,
                    reasons=[
                        "卖出衰减 Popcorn 替换为 Abstract Joker",
                        "保留 Sly/Scary Face/Half/Hanging Chad 核心",
                    ],
                )
        return None

    def _sell_dead_joker_proposal(self, state: GameState) -> Optional[ActionProposal]:
        """当Joker因游戏状态变化而失效时（如牌库空→Erosion=0），提议卖出。"""
        for index, joker in enumerate(state.jokers):
            strength = self._joker_strength(joker, state)
            if strength < 0:
                return ActionProposal(
                    "sell",
                    {"joker": index},
                    50.0,  # 高分确保优先执行
                    self.name,
                    confidence=0.95,
                    reasons=[f"卖出已失效 Joker：{item_name(joker) or index}（当前环境无价值）"],
                )
        return None

    def _boss_aware_joker_adjust(self, item: Dict[str, object], state: GameState) -> float:
        """根据即将到来的Boss盲注调整Joker购买评分。"""
        name = state.blind_name.lower()
        joker_key = str(item.get("key") or "").lower()
        adjust = 0.0
        # 花色削弱Boss：降低对应花色Joker评分
        debuff_map = {"the head": "H", "the goad": "S", "the club": "C", "the window": "D"}
        suit_jokers = {"H": "j_lusty_joker", "S": "j_wrathful_joker",
                       "D": "j_greedy_joker", "C": "j_gluttenous_joker"}
        for boss, suit in debuff_map.items():
            if boss in name:
                if joker_key == suit_jokers.get(suit, ""):
                    adjust -= 20.0
        # The Mouth: 倾向专注型Joker
        if "the mouth" in name:
            focus_jokers = {"j_half", "j_photograph", "j_runner", "j_scholar",
                            "j_walkie_talkie", "j_hanging_chad"}
            if joker_key in focus_jokers:
                adjust += 8.0
        return adjust

    def _consumable_buy_score(
        self,
        item: Dict[str, object],
        state: GameState,
        genome: Genome,
    ) -> Optional[float]:
        kind = item_type(item)
        key = str(item.get("key") or item.get("id") or "").lower()
        base = 28.0 * genome.weight("buy_consumable")  # 大幅提升消耗品购买意愿

        if kind == "PLANET":
            if self._is_completed_small_hand_build(state) and not self._is_small_hand_planet(item):
                return None
            # 行星牌是永久升级，基础分更高
            ante_bonus = max(0.0, state.ante - 1) * 3.0
            # 如果手牌等级还很低（<3级），行星牌价值更高
            level_bonus = self._planet_level_bonus(state, item)
            score = base + ante_bonus + level_bonus
            # 临近The Needle等单手Boss时，升行星更紧迫
            if self._approaching_single_hand_boss(state):
                score += 12.0
            return score
        # 支持所有已知塔罗牌购买
        if key in ConsumableAgent._TARGETED_TAROT_COUNTS or key in ConsumableAgent._NO_TARGET_TAROTS:
            score = base
            # Campfire燃料：拥有Campfire时塔罗牌价值提升
            if self._has_campfire(state):
                score += 8.0
            # 临近单手Boss：塔罗牌用于增强关键牌
            if self._approaching_single_hand_boss(state):
                score += 6.0
            # Hermit在缺钱时价值极高
            if key == "c_hermit" and state.money < 10:
                score += 8.0
            return score
        # Campfire模式下，任何廉价消耗品都有燃料价值
        if self._has_campfire(state) and item_cost(item) and item_cost(item) <= 4:
            return base + 6.0
        return None

    def _has_campfire(self, state: GameState) -> bool:
        return any(
            str(joker.get("key") or "").lower() == "j_campfire"
            for joker in state.jokers
        )

    def _approaching_single_hand_boss(self, state: GameState) -> bool:
        """检测是否接近单手Boss（The Needle, The Eye等）。"""
        name = state.blind_name.lower()
        if "the needle" in name:
            return True
        # 提前一个盲注准备：如果是boss盲且可能是The Needle
        if state.ante >= 4 and "boss" in name and state.hands_remaining <= 1:
            return True
        return False

    def _is_completed_small_hand_build(self, state: GameState) -> bool:
        owned_keys = {str(joker.get("key") or "").lower() for joker in state.jokers}
        supernova_build = {
            "j_sly",
            "j_scary_face",
            "j_half",
            "j_supernova",
            "j_popcorn",
        }.issubset(owned_keys)
        return supernova_build or self._is_chad_small_hand_build_keys(owned_keys)

    def _is_chad_small_hand_build_keys(self, owned_keys: set[str]) -> bool:
        core = {
            "j_sly",
            "j_scary_face",
            "j_half",
            "j_hanging_chad",
        }
        return core.issubset(owned_keys) and (
            "j_popcorn" in owned_keys or "j_abstract" in owned_keys
        )

    def _is_small_hand_planet(self, item: Dict[str, object]) -> bool:
        name = item_name(item).lower()
        key = str(item.get("key") or item.get("id") or "").lower()
        return any(
            token in name or token in key
            for token in {"mercury", "venus", "pluto"}
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

    def _joker_strength(
        self,
        item: Dict[str, object],
        state: Optional[GameState] = None,
        genome: Optional[Genome] = None,
    ) -> float:
        key = str(item.get("key") or item.get("id") or "").lower()
        name = item_name(item).lower()
        value = item.get("value")
        effect = ""
        if isinstance(value, dict):
            effect = str(value.get("effect") or "").lower()

        key_scores = {
            "j_abstract": 36.0,
            "j_ancient": 18.0,
            "j_baron": 18.0,
            "j_blueprint": 38.0,
            "j_brainstorm": 36.0,
            "j_castle": 24.0,
            "j_delayed_grat": 6.0,
            "j_dna": 26.0,
            "j_gluttenous_joker": 14.0,
            "j_joker": 18.0,
            "j_lusty_joker": 14.0,
            "j_greedy_joker": 14.0,
            "j_wrathful_joker": 14.0,
            "j_half": 30.0,
            "j_mime": 24.0,
            "j_pareidolia": 18.0,
            "j_photograph": 24.0,
            "j_scholar": 20.0,
            "j_smeared": 22.0,
            "j_sock_and_buskin": 26.0,
            "j_square": 24.0,
            "j_walkie_talkie": 22.0,
            "j_blue_joker": 24.0,
            "j_campfire": 20.0,
            "j_credit_card": 1.0,
            "j_red_card": 4.0,
            "j_rocket": 1.0,
            "j_hallucination": 6.0,
            "j_to_the_moon": 1.0,
            "j_golden_joker": 3.0,
            "j_cloud_9": 3.0,
            "j_business": 1.0,
            "j_business_card": 1.0,
            "j_faceless": 3.0,
            "j_hanging_chad": 28.0,
            "j_ice_cream": 34.0,
            "j_madness": 24.0,
            "j_banner": 26.0,
            "j_gros_michel": 34.0,
            "j_smiley": 20.0,
            "j_trousers": 28.0,
        }
        base = key_scores.get(key, 14.0)

        if "abstract joker" in name:
            base = max(base, 36.0)
        if "ancient joker" in name:
            base = max(base, 18.0)
        if "baron" in name:
            base = max(base, 18.0)
        if "blueprint" in name:
            base = max(base, 38.0)
        if "brainstorm" in name:
            base = max(base, 36.0)
        if "castle" in name:
            base = max(base, 24.0)
        if "dna" in name:
            base = max(base, 26.0)
        if "scholar" in name:
            base = max(base, 20.0)
        if "spare trousers" in name:
            base = max(base, 28.0)
        if "photograph" in name:
            base = max(base, 24.0)
        if "mime" in name:
            base = max(base, 24.0)
        if "pareidolia" in name:
            base = max(base, 18.0)
        if "smeared joker" in name:
            base = max(base, 22.0)
        if "sock and buskin" in name:
            base = max(base, 26.0)
        if "campfire" in name:
            base = max(base, 20.0)
        if "half joker" in name:
            base = max(base, 30.0)
        if "credit card" in name:
            base = min(base, 1.0)
        if "ice cream" in name:
            if state is not None:
                # Ice Cream 每手牌 -4 chips。ante 4+ 开始明显衰减
                decay = max(0, state.ante - 3) * 10.0
                base = max(base, max(4.0, 34.0 - decay))
            else:
                base = max(base, 34.0)
        if "madness" in name:
            base = max(base, 24.0)
        if "banner" in name:
            base = max(base, 26.0)
        if "gros michel" in name:
            base = max(base, 34.0)
        if "smiley face" in name:
            base = max(base, 20.0)
        if "business card" in name:
            base = min(base, 1.0)

        if key not in key_scores:
            if "x" in name or "x" in effect or "倍率" in effect:
                base += 20.0  # X-mult 稀缺，提升但不过分
            elif "mult" in name or "mult" in effect:
                base += 6.0
            if "chip" in name or "chip" in effect or "筹码" in effect:
                base += 4.0
            if "trigger" in effect or "额外触发" in effect:
                base += 6.0
            if "discard" in name or "弃牌" in effect:
                base -= 3.0
            if "$" in effect or "money" in name or "dollar" in name:
                base -= 2.0
            # 纯经济Joker占槽位但无战斗力，严重降分
            if key in {"j_to_the_moon", "j_rocket", "j_golden_joker", "j_cloud_9", "j_business_card", "j_faceless"}:
                base = min(base, 8.0)
            if "to the moon" in name or "rocket" in name:
                base = min(base, 6.0)

        # Stencil：空槽越多越强，满槽时价值极低
        if key == "j_stencil" or "stencil" in name:
            if state is not None:
                empty_slots = state.joker_limit - len(state.jokers)
                base = 8.0 + empty_slots * 8.0  # 0空槽=8, 1空槽=16, 2空槽=24...
            else:
                base = 16.0  # 未知状态保守估计（通常1-2空槽）
        # Mystic Summit 仅在最后手+15 mult，条件严苛
        if key == "j_mystic_summit" or "mystic summit" in name:
            base = min(base, 12.0)
        # Jolly: 仅+8 mult for pairs，太弱
        if key == "j_jolly" or "jolly joker" in name:
            base = min(base, 10.0)

        if state is not None:
            owned_keys = {str(joker.get("key") or "").lower() for joker in state.jokers}
            base += self._archetype_joker_bonus(key, name, effect, state, owned_keys)
            if key == "j_blue_joker" or "blue joker" in name:
                # Blue Joker 是核心筹码来源，配合Half/Chad时不可替代
                deck_remaining = state.deck_card_count if state.deck_card_count > 0 else 52
                base = max(base, 20.0 + deck_remaining * 0.25)  # 52牌=33, 40牌=30
                if {"j_half", "j_hanging_chad"} & owned_keys:
                    base += 8.0  # Half+Chad构筑中Blue=必需筹码基础
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
                # 同时拥有Chad和Half时学者价值大幅提升（终极对子构建）
                if "j_hanging_chad" in owned_keys and "j_half" in owned_keys:
                    base += 6.0
                if self._is_chad_small_hand_build_keys(owned_keys):
                    base = min(base, 25.0)
            if key == "j_banner" or "banner" in name:
                base += min(8.0, max(0, state.discards_remaining) * 2.0)
            if self._is_third_narrow_conditional_joker(key, state):
                base = min(base, 2.0)
            if key == "j_sly" and ({"j_scary_face", "j_half"} & owned_keys):
                base = max(base, 20.0)
            if self._is_chad_small_hand_build_keys(owned_keys):
                if key in {"j_sly", "j_scary_face", "j_half", "j_hanging_chad"}:
                    base = max(base, 42.0)
            # Fortune Teller在没有塔罗牌配合时很弱
            if key == "j_fortune_teller" or "fortune" in name:
                tarot_count = sum(1 for c in state.consumables if item_type(c) in ("TAROT", "CONSUMABLE"))
                if tarot_count == 0 and state.money < 5:
                    base = min(base, 12.0)
            # 牌库耗尽时，依赖牌库的Joker价值归零
            if state.deck_card_count <= 0:
                if key == "j_erosion" or "erosion" in name:
                    base = -10.0  # 强力负面信号，应该卖掉
                if "deck" in effect.lower() or "below" in effect.lower():
                    base = min(base, 2.0)
            # 经济Joker动态估值：剩余局数越多价值越高，但ante 1-2现金紧张时不宜高价买纯经济牌
            if key in {"j_delayed_grat", "j_golden_joker", "j_business_card",
                       "j_to_the_moon", "j_rocket", "j_cloud_9", "j_faceless"}:
                remaining_rounds = max(1, (8 - state.ante) * 3 + (3 - state.round_number % 3))
                economy_bonus = min(remaining_rounds * 0.8, 12.0)
                # 早期现金紧张：ante 1-2时纯经济Joker价值受限
                early_penalty = 0.7 if state.ante <= 2 else 1.0
                if key == "j_delayed_grat":
                    base = max(base, 8.0 + economy_bonus * early_penalty)
                elif key in {"j_golden_joker", "j_business_card"}:
                    base = max(base, 4.0 + economy_bonus * 0.7 * early_penalty)
                else:
                    # Rocket等纯经济Joker不提供战力，保持低估值
                    base = max(base, 1.0 + economy_bonus * 0.25 * early_penalty)
            # 缩放型Joker：按回合数加基础分（已投入多轮不应被轻易替换）
            if key == "j_supernova" or "supernova" in name:
                base = max(base, 22.0 + state.round_number * 1.5)
            if key == "j_ride_the_bus" or "ride the bus" in name:
                base = max(base, 20.0 + state.round_number * 2.0)
            if key == "j_green_joker" or "green joker" in name:
                base = max(base, 18.0 + state.round_number * 1.0)
            # ante 4+：无X-mult的构筑应大幅提升X-mult优先级
            xmult_priority_ante = int(
                genome.weight("xmult_priority_ante", 4.0) if genome is not None else 4
            )
            if state.ante >= xmult_priority_ante and ("x" in name or "x" in effect):
                has_xmult = any(
                    "x" in str(owned.get("key", "") or "").lower()
                    or "x" in str(owned.get("name", "") or "").lower()
                    for owned in state.jokers
                )
                if not has_xmult:
                    base += 20.0  # 无X-mult时大幅提升首张X-mult价值
        return base

    def _archetype_joker_bonus(
        self,
        key: str,
        name: str,
        effect: str,
        state: GameState,
        owned_keys: set[str],
    ) -> float:
        bonus = 0.0

        if key == "j_trousers" or "spare trousers" in name:
            if state.ante <= 3:
                bonus += 8.0
            if owned_keys & {"j_square", "j_mad", "j_clever", "j_sly", "j_jolly"}:
                bonus += 6.0

        if key in {"j_hanging_chad", "j_sock_and_buskin"}:
            if "j_photograph" in owned_keys:
                bonus += 14.0
            if "j_pareidolia" in owned_keys:
                bonus += 6.0

        if key == "j_photograph":
            if owned_keys & {"j_hanging_chad", "j_sock_and_buskin"}:
                bonus += 10.0
            if "j_pareidolia" in owned_keys:
                bonus += 6.0

        if key == "j_midas_mask" and owned_keys & {"j_pareidolia", "j_photograph", "j_sock_and_buskin"}:
            bonus += 8.0

        if key == "j_baron":
            bonus += self._steel_king_route_bonus(state, owned_keys)

        if key in {"j_mime", "j_blueprint", "j_brainstorm", "j_dna"}:
            if "j_baron" in owned_keys or self._steel_king_count(state) > 0:
                bonus += 10.0

        suit_jokers = {
            "H": "j_lusty_joker",
            "D": "j_greedy_joker",
            "S": "j_wrathful_joker",
            "C": "j_gluttenous_joker",
        }
        for suit, joker_key in suit_jokers.items():
            if key == joker_key:
                bonus += self._suit_focus_bonus(state, suit)
        if key in {"j_ancient", "j_smeared", "j_castle"}:
            bonus += self._best_suit_focus_bonus(state) * 0.6

        return bonus

    def _steel_king_route_bonus(self, state: GameState, owned_keys: set[str]) -> float:
        king_count = self._rank_count(state, 13)
        steel_king_count = self._steel_king_count(state)
        if king_count == 0 and steel_king_count == 0:
            return 0.0

        bonus = steel_king_count * 14.0 + max(0, king_count - 1) * 2.0
        if owned_keys & {"j_blueprint", "j_brainstorm", "j_mime", "j_dna"}:
            bonus += 8.0
        return bonus

    def _rank_count(self, state: GameState, rank_value: int) -> int:
        return sum(1 for card in self._profile_cards(state) if card_rank_value(card) == rank_value)

    def _steel_king_count(self, state: GameState) -> int:
        return sum(
            1
            for card in self._profile_cards(state)
            if card_rank_value(card) == 13 and card_enhancement(card) == "STEEL"
        )

    def _suit_focus_bonus(self, state: GameState, suit: str) -> float:
        cards = self._profile_cards(state)
        if not cards:
            return 0.0
        suit_count = sum(1 for card in cards if card_suit(card) == suit)
        ratio = suit_count / len(cards)
        if suit_count >= 5 and ratio >= 0.45:
            return 14.0
        if suit_count >= 4 and ratio >= 0.35:
            return 7.0
        return 0.0

    def _best_suit_focus_bonus(self, state: GameState) -> float:
        return max((self._suit_focus_bonus(state, suit) for suit in ("H", "D", "S", "C")), default=0.0)

    def _profile_cards(self, state: GameState) -> List[Dict[str, object]]:
        cards = list(state.deck_cards)
        if cards:
            return cards
        return list(state.hand)

    def _is_third_narrow_conditional_joker(self, key: str, state: GameState) -> bool:
        if state.ante < 2 or key == "j_sly" or key not in self._NARROW_CONDITIONAL_JOKERS:
            return False
        owned_count = sum(
            1
            for joker in state.jokers
            if str(joker.get("key") or "").lower() in self._NARROW_CONDITIONAL_JOKERS
        )
        return owned_count >= 2


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


def default_agents() -> List[Agent]:
    return [
        RoundAgent(),
        BoosterAgent(),
        ConsumableAgent(),
        HandAgent(),
        JokerOrderAgent(),
        ShopAgent(),
        EconomyAgent(),
    ]
