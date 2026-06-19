from __future__ import annotations
from collections import defaultdict
from math import comb
from itertools import combinations
from typing import Dict, Iterable, List, Tuple
from balatro_agent.actions import BLIND_SELECT, SELECTING_HAND
from balatro_agent.agents.base import Agent
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

    # 渐进式牌型专精：Joker → 目标牌型信号强度
    # 每个Joker输出若干 (hand_type, signal_strength) 对
    # "__consistency__" 表示鼓励重复打同一牌型
    # "__repeat__" 表示同一牌型再次打出时有额外收益
    _JOKER_HAND_TYPE_SIGNAL: Dict[str, List[Tuple[str, float]]] = {
        "j_half": [("pair", 3.0), ("high_card", 2.5), ("three_kind", 2.0)],
        "j_sly": [("pair", 3.0), ("two_pair", 2.0)],
        "j_photograph": [("pair", 2.5), ("high_card", 2.5)],
        "j_hanging_chad": [("high_card", 3.0), ("pair", 2.0)],
        "j_scholar": [("pair", 2.5), ("high_card", 2.5)],
        "j_walkie_talkie": [("two_pair", 2.5), ("pair", 1.5)],
        "j_runner": [("straight", 3.5)],
        "j_superposition": [("straight", 2.5)],
        "j_lusty_joker": [("flush", 3.0)],
        "j_greedy_joker": [("flush", 3.0)],
        "j_wrathful_joker": [("flush", 3.0)],
        "j_gluttenous_joker": [("flush", 3.0)],
        "j_ancient": [("flush", 2.5)],
        "j_smeared": [("flush", 2.0)],
        "j_card_sharp": [("__repeat__", 4.0)],
        "j_supernova": [("__consistency__", 3.5)],
        "j_mad": [("two_pair", 2.0)],
        "j_ride_the_bus": [("two_pair", 2.0), ("straight", 1.5)],
        "j_even_steven": [("pair", 1.5)],
        "j_odd_todd": [("pair", 1.5)],
        "j_green_joker": [("pair", 1.5)],
        "j_trousers": [("two_pair", 3.0)],
        "j_square": [("pair", 1.5), ("high_card", 1.5)],
        "j_scary_face": [("pair", 1.5), ("high_card", 1.5)],
        "j_jolly": [("pair", 1.5)],
        "j_clever": [("two_pair", 1.5), ("pair", 1.0)],
        "j_droll": [("flush", 1.5)],
        "j_zany": [("three_kind", 1.5)],
        "j_wily": [("three_kind", 1.5)],
        "j_mystic_summit": [("pair", 1.0), ("high_card", 1.5)],
    }

    # 手牌类型 → 雕塑弃牌时的保留优先级策略
    _COMMITMENT_SCULPT_STRATEGY: Dict[str, str] = {
        "pair": "keep_pairs",
        "two_pair": "keep_pairs",
        "three_kind": "keep_groups",
        "four_kind": "keep_groups",
        "full_house": "keep_pairs",
        "flush": "keep_suit",
        "straight": "keep_connected",
        "straight_flush": "keep_suit",
        "high_card": "keep_high",
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

    def _resolve_commitment(self, state: GameState) -> Tuple[Optional[str], str, float]:
        """渐进式牌型专精：根据当前ante和Joker信号返回 (committed_hand_type, phase, confidence)。

        phase ∈ {"explore", "commit", "execute"}
        - explore (ante 1-2): 不锁定，灵活探索
        - commit (ante 3-5): 根据Joker信号锁定目标牌型
        - execute (ante 6+):  全力打造，强雕塑弃牌
        """
        ante = state.ante
        joker_keys = set(self._joker_keys(state))

        if ante < 3:
            return None, "explore", 0.0

        # 汇总所有Joker的牌型信号
        signal_scores: Dict[str, float] = defaultdict(float)
        consistency_bonus = 0.0
        repeat_bonus = 0.0

        for key in joker_keys:
            signals = self._JOKER_HAND_TYPE_SIGNAL.get(key, [])
            for hand_type, strength in signals:
                if hand_type == "__consistency__":
                    consistency_bonus += strength
                elif hand_type == "__repeat__":
                    repeat_bonus += strength
                else:
                    signal_scores[hand_type] = signal_scores.get(hand_type, 0) + strength

        # __consistency__ Joker（如Supernova）强化已有最高分牌型
        if consistency_bonus > 0 and signal_scores:
            best_type = max(signal_scores, key=signal_scores.get)
            signal_scores[best_type] += consistency_bonus * 0.8

        # __repeat__ Joker（如Card Sharp）强化小牌型（更容易重复打出）
        if repeat_bonus > 0:
            for small_type in ("pair", "high_card", "two_pair"):
                if small_type in signal_scores:
                    signal_scores[small_type] += repeat_bonus

        if not signal_scores:
            return None, "explore", 0.0

        # 选出信号最强的牌型
        best_type = max(signal_scores, key=signal_scores.get)
        best_score = signal_scores[best_type]
        total_score = sum(signal_scores.values()) + 1.0  # avoid div by zero
        confidence = best_score / total_score

        # 需要信号足够集中才锁定
        phase = "explore"
        if ante >= 6:
            # execute: 降低锁定门槛，即使信号不完美也要选择一个方向
            if best_score >= 2.5:
                phase = "execute"
            elif best_score >= 1.5 and confidence >= 0.25:
                phase = "execute"
        elif ante >= 3:
            # commit: 需要较强信号
            if best_score >= 5.0 and confidence >= 0.30:
                phase = "commit"
            elif best_score >= 3.5 and confidence >= 0.35:
                phase = "commit"

        if phase == "explore":
            return None, "explore", 0.0

        return best_type, phase, confidence

    def _commitment_bonus(self, hand_label: str, committed_type: Optional[str], phase: str) -> float:
        """返回目标牌型的额外评分加成。"""
        if committed_type is None or phase == "explore":
            return 0.0

        base_bonus = {
            "commit": 25.0,
            "execute": 55.0,
        }.get(phase, 0.0)

        if hand_label == committed_type:
            return base_bonus
        # 与目标牌型相近的牌型也有一点加成（如 pair 对 two_pair）
        if committed_type == "pair" and hand_label in ("two_pair", "three_kind"):
            return base_bonus * 0.3
        if committed_type == "two_pair" and hand_label == "pair":
            return base_bonus * 0.4
        if committed_type == "straight" and hand_label == "straight_flush":
            return base_bonus * 0.5
        if committed_type == "flush" and hand_label == "straight_flush":
            return base_bonus * 0.5
        if committed_type == "three_kind" and hand_label in ("pair", "two_pair", "four_kind"):
            return base_bonus * 0.3
        # execute阶段：对偏离目标牌型的大牌型也给予惩罚
        if phase == "execute" and hand_label not in {
            committed_type,
            "high_card",  # 高牌是最后手段，不惩罚
        }:
            # 检查hand_label是否包含committed elements
            related = False
            if committed_type in ("pair", "two_pair") and hand_label in ("pair", "two_pair", "three_kind"):
                related = True
            if committed_type in ("flush", "straight_flush") and hand_label in ("flush", "straight_flush"):
                related = True
            if committed_type in ("straight", "straight_flush") and hand_label in ("straight", "straight_flush"):
                related = True
            if not related:
                return -15.0  # 轻微惩罚偏离牌型

        return 0.0

    def _commitment_sculpt_discard(
        self,
        state: GameState,
        hand: List[Dict[str, object]],
        committed_type: str,
        phase: str,
    ) -> Tuple[List[int], float]:
        """在锁定目标牌型后，弃牌时优先保留有助于目标牌型的牌。"""
        if not hand or len(hand) <= 2:
            return [], float("-inf")

        strategy = self._COMMITMENT_SCULPT_STRATEGY.get(committed_type, "")
        if not strategy:
            return [], float("-inf")

        keep_indices: List[int] = []

        if strategy == "keep_pairs":
            # 保留所有能形成对子的牌组
            rank_groups: Dict[int, List[int]] = defaultdict(list)
            for i, card in enumerate(hand):
                rv = card_rank_value(card)
                if rv > 0:
                    rank_groups[rv].append(i)
            for indices in rank_groups.values():
                if len(indices) >= 2:
                    keep_indices.extend(indices[:2])
            # 保留高分单牌做补充
            kept_set = set(keep_indices)
            premium = sorted(
                (i for i in range(len(hand)) if i not in kept_set and card_rank_value(hand[i]) >= 10),
                key=lambda i: card_rank_value(hand[i]),
                reverse=True,
            )
            keep_indices.extend(premium[:3])

        elif strategy == "keep_groups":
            # 保留最大的同点数组
            rank_groups: Dict[int, List[int]] = defaultdict(list)
            for i, card in enumerate(hand):
                rv = card_rank_value(card)
                if rv > 0:
                    rank_groups[rv].append(i)
            best = max(rank_groups.values(), key=len, default=[])
            keep_indices.extend(best)

        elif strategy == "keep_suit":
            # 保留最多同花色的牌
            suit_groups: Dict[str, List[int]] = defaultdict(list)
            for i, card in enumerate(hand):
                suit = card_suit(card)
                if suit:
                    suit_groups[suit].append(i)
            best_suit_group = max(suit_groups.values(), key=len, default=[])
            keep_indices.extend(best_suit_group[:5])

        elif strategy == "keep_connected":
            # 保留可能形成顺子的牌
            ranked = sorted(
                (i for i, card in enumerate(hand) if card_rank_value(card) > 0),
                key=lambda i: card_rank_value(hand[i]),
            )
            # 找最长连续序列
            best_run: List[int] = []
            current_run: List[int] = []
            prev_rank = -99
            for i in ranked:
                rv = card_rank_value(hand[i])
                if rv == prev_rank + 1 or (prev_rank == 5 and rv == 14):
                    current_run.append(i)
                elif rv == prev_rank:
                    continue  # 相同点数保留一个
                else:
                    if len(current_run) > len(best_run):
                        best_run = current_run
                    current_run = [i]
                prev_rank = rv
            if len(current_run) > len(best_run):
                best_run = current_run
            keep_indices.extend(best_run[:5])

        elif strategy == "keep_high":
            # 保留高点数牌
            ranked = sorted(
                range(len(hand)),
                key=lambda i: card_rank_value(hand[i]),
                reverse=True,
            )
            keep_indices = ranked[:max(2, len(hand) - 5)]

        if not keep_indices or len(keep_indices) >= len(hand):
            return [], float("-inf")

        keep_indices = sorted(set(keep_indices))
        discard = [i for i in range(len(hand)) if i not in keep_indices]
        discard = discard[: min(5, len(discard))]

        # 评估雕塑后手牌中目标牌型的潜力
        kept_cards = [hand[i] for i in keep_indices]
        sculpt_score = self._sculpt_potential_score(state, kept_cards, committed_type)

        # execute阶段雕塑意愿更强
        bonus = 45.0 if phase == "execute" else 20.0
        return discard, sculpt_score + bonus

    def _sculpt_potential_score(
        self,
        state: GameState,
        kept_cards: List[Dict[str, object]],
        committed_type: str,
    ) -> float:
        """评估保留牌组对目标牌型的潜力分数。"""
        if not kept_cards:
            return 0.0

        rank_values = [card_rank_value(c) for c in kept_cards]
        rank_counts: Dict[int, int] = defaultdict(int)
        for rv in rank_values:
            if rv > 0:
                rank_counts[rv] += 1

        score = sum(rank_values) * 0.2

        if committed_type in ("pair", "two_pair"):
            pairs = sum(1 for c in rank_counts.values() if c >= 2)
            score += pairs * 35.0
        elif committed_type in ("three_kind", "four_kind", "full_house"):
            max_group = max(rank_counts.values(), default=0)
            score += max_group * 40.0
        elif committed_type in ("flush", "straight_flush"):
            suit_counts: Dict[str, int] = defaultdict(int)
            for c in kept_cards:
                suit = card_suit(c)
                if suit:
                    suit_counts[suit] += 1
            max_suit = max(suit_counts.values(), default=0)
            score += max_suit * 35.0
        elif committed_type == "straight":
            longest = self._longest_run(rank_values)
            score += longest * 38.0

        return score

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

        # 渐进式牌型专精：锁定目标牌型
        committed_type, commit_phase, commit_conf = self._resolve_commitment(state)

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
                # 渐进式牌型专精：目标牌型加权
                base_score += self._commitment_bonus(hand_label, committed_type, commit_phase)
                # The Mouth: 极度强化Joker方向，确保一直选同一种牌型
                if mouth_boss:
                    base_score += joker_prefs.get(hand_label, 0) * 2.0
                    # The Mouth + commitment: 两者叠加，极端强化目标牌型
                    if committed_type and commit_phase != "explore":
                        base_score += self._commitment_bonus(hand_label, committed_type, "execute") * 0.5
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

        # 渐进式牌型专精：在commit/execute阶段用弃牌雕塑手牌
        committed_type, commit_phase, _ = self._resolve_commitment(state)
        if committed_type and commit_phase in ("commit", "execute") and hands_remaining >= 2:
            sculpt_discard, sculpt_score = self._commitment_sculpt_discard(
                state, hand, committed_type, commit_phase
            )
            if sculpt_discard and sculpt_score > play_score * 0.5:
                # 检查当前出牌是否已经是目标牌型
                if hand_label != committed_type:
                    return sculpt_discard, max(sculpt_score, play_score + 35.0)
                # execute阶段：即使已是目标牌型，若分数不足仍雕塑
                if commit_phase == "execute":
                    shortfall = max(0.0, float(state.blind_requirement - state.score))
                    if play_score < shortfall * 0.7 and hands_remaining > 2:
                        return sculpt_discard, max(sculpt_score, play_score + 30.0)

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
