import unittest

from balatro_agent.agents.hand import HandAgent
from balatro_agent.model import GameState, Genome


def _make_hand_state(hand_cards, **overrides):
    """Build minimal SELECTING_HAND state fixture."""
    base = {
        "state": "SELECTING_HAND",
        "hand": hand_cards,
        "jokers": [],
        "chips_required": 300,
        "hands_remaining": 4,
        "discards_remaining": 3,
        "hand_levels": {},
        "consumables": {"cards": [], "limit": 2},
        "deck": {"cards": []},
        "ante": 1,
        "round": 1,
    }
    base.update(overrides)
    return GameState(base)


def _card(key, suit="S", rank=2, value="2"):
    return {
        "key": key,
        "suit": suit,
        "rank": rank,
        "value": value,
        "enhancement": None,
        "seal": None,
        "edition": None,
    }


class HandAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = HandAgent()
        self.genome = Genome.default()

    def test_produces_play_or_discard_proposals(self):
        """With enough cards, produces play or discard actions."""
        hand = [
            _card("c_2s", "S", 2, "2"),
            _card("c_3s", "S", 3, "3"),
            _card("c_4s", "S", 4, "4"),
            _card("c_5s", "S", 5, "5"),
            _card("c_6s", "S", 6, "6"),
            _card("c_7s", "S", 7, "7"),
            _card("c_8s", "S", 8, "8"),
            _card("c_9s", "S", 9, "9"),
        ]
        state = _make_hand_state(hand)
        proposals = self.agent.propose(state, self.genome)
        self.assertGreater(len(proposals), 0)
        methods = {p.method for p in proposals}
        self.assertTrue({"play", "discard"} & methods,
                        f"Expected play or discard in methods: {methods}")

    def test_scores_play_proposals(self):
        """play proposals all have positive scores."""
        hand = [
            _card("c_2h", "H", 2, "2"),
            _card("c_3h", "H", 3, "3"),
            _card("c_4h", "H", 4, "4"),
            _card("c_5h", "H", 5, "5"),
            _card("c_6h", "H", 6, "6"),
            _card("c_7h", "H", 7, "7"),
            _card("c_8h", "H", 8, "8"),
            _card("c_9h", "H", 9, "9"),
        ]
        state = _make_hand_state(hand)
        proposals = self.agent.propose(state, self.genome)
        play_proposals = [p for p in proposals if p.method == "play"]
        self.assertGreater(len(play_proposals), 0)
        for p in play_proposals:
            self.assertGreater(p.score, 0, f"Play proposal should have positive score: {p}")

    def test_flush_detected_with_same_suit_cards(self):
        """Five same-suit cards detected as flush."""
        agent = HandAgent()
        cards = [
            _card("c_2h", "H", 2, "2"),
            _card("c_5h", "H", 5, "5"),
            _card("c_7h", "H", 7, "7"),
            _card("c_9h", "H", 9, "9"),
            _card("c_Kh", "H", 13, "K"),
        ]
        self.assertTrue(agent._is_flush(cards))

    def test_flush_not_detected_with_mixed_suits(self):
        """Mixed suits not detected as flush."""
        agent = HandAgent()
        cards = [
            _card("c_2h", "H", 2, "2"),
            _card("c_5s", "S", 5, "5"),
            _card("c_7h", "H", 7, "7"),
        ]
        self.assertFalse(agent._is_flush(cards))

    def test_straight_detected_with_consecutive_ranks(self):
        """Consecutive ranks detected as straight."""
        agent = HandAgent()
        self.assertTrue(agent._is_straight([2, 3, 4, 5, 6]))

    def test_straight_not_detected_with_gaps(self):
        """Gapped ranks not detected as straight."""
        agent = HandAgent()
        self.assertFalse(agent._is_straight([2, 4, 6, 8, 10]))

    def test_last_hand_produces_play_when_close(self):
        """On last hand with close score, still produces play action."""
        hand = [
            _card("c_Ah", "H", 14, "A"),
            _card("c_Kh", "H", 13, "K"),
            _card("c_Qh", "H", 12, "Q"),
            _card("c_Jh", "H", 11, "J"),
            _card("c_10h", "H", 10, "10"),
            _card("c_9h", "H", 9, "9"),
            _card("c_8h", "H", 8, "8"),
            _card("c_7h", "H", 7, "7"),
        ]
        state = _make_hand_state(hand, hands_remaining=1, chips_required=100)
        proposals = self.agent.propose(state, self.genome)
        play_methods = [p for p in proposals if p.method == "play"]
        self.assertGreater(len(play_methods), 0,
                           "Should have play proposals on last hand when score is close")


class HandAgentCommitmentTests(unittest.TestCase):
    """测试渐进式牌型专精（Progressive Hand-Type Commitment）。"""

    def setUp(self):
        self.agent = HandAgent()
        self.genome = Genome.default()

    def _state(self, ante=1, joker_keys=None, hand_cards=None, **overrides):
        """构建最小GameState用于commitment测试。"""
        jokers = [{"key": k} for k in (joker_keys or [])]
        base = {
            "state": "SELECTING_HAND",
            "hand": hand_cards or [_card("c_Ah", "H", 14, "A"), _card("c_Kh", "H", 13, "K"),
                                   _card("c_Qh", "H", 12, "Q"), _card("c_Jh", "H", 11, "J"),
                                   _card("c_10h", "H", 10, "10"), _card("c_9h", "H", 9, "9"),
                                   _card("c_8h", "H", 8, "8"), _card("c_7h", "H", 7, "7")],
            "jokers": jokers,
            "chips_required": 300,
            "hands_remaining": 4,
            "discards_remaining": 3,
            "hand_levels": {},
            "consumables": {"cards": [], "limit": 2},
            "deck": {"cards": []},
            "ante": ante,
            "round": ante * 3,
        }
        base.update(overrides)
        return GameState(base)

    def test_explore_phase_no_commitment_before_ante_3(self):
        """Ante 1-2 不锁定牌型（探索期）。"""
        state = self._state(ante=2, joker_keys=["j_half", "j_photograph"])
        committed, phase, _ = self.agent._resolve_commitment(state)
        self.assertIsNone(committed, "Ante 2 不应锁定牌型")
        self.assertEqual(phase, "explore")

    def test_no_commitment_without_joker_signals(self):
        """没有足够Joker信号时不应锁定。"""
        state = self._state(ante=4, joker_keys=["j_joker"])  # plain joker 无信号
        committed, phase, _ = self.agent._resolve_commitment(state)
        self.assertIsNone(committed, "无信号Joker不应触发锁定")
        self.assertEqual(phase, "explore")

    def test_commit_pair_with_half_and_sly(self):
        """Half Joker + Sly Joker 应锁定 pair。"""
        state = self._state(ante=4, joker_keys=["j_half", "j_sly"])
        committed, phase, _ = self.agent._resolve_commitment(state)
        self.assertEqual(committed, "pair", f"Half+Sly 应锁定 pair，实际: {committed}")
        self.assertIn(phase, ("commit", "execute"))

    def test_commit_flush_with_suit_jokers(self):
        """花色Joker应锁定 flush。"""
        state = self._state(ante=4, joker_keys=["j_lusty_joker", "j_greedy_joker"])
        committed, phase, _ = self.agent._resolve_commitment(state)
        self.assertEqual(committed, "flush", f"双花色Joker应锁定 flush，实际: {committed}")

    def test_commit_straight_with_runner(self):
        """Runner Joker 应锁定 straight。"""
        state = self._state(ante=5, joker_keys=["j_runner"])
        committed, phase, _ = self.agent._resolve_commitment(state)
        self.assertEqual(committed, "straight", f"Runner应锁定straight，实际: {committed}")

    def test_commit_two_pair_with_trousers(self):
        """Spare Trousers 应锁定 two_pair。"""
        state = self._state(ante=4, joker_keys=["j_trousers", "j_mad"])
        committed, phase, _ = self.agent._resolve_commitment(state)
        self.assertEqual(committed, "two_pair", f"Trousers+Mad应锁定two_pair，实际: {committed}")

    def test_card_sharp_boosts_small_hand_types(self):
        """Card Sharp 强化小牌型（pair/high_card）重复打出。"""
        state = self._state(ante=5, joker_keys=["j_card_sharp", "j_half"])
        committed, phase, _ = self.agent._resolve_commitment(state)
        self.assertIn(committed, ("pair", "high_card"),
                      f"Card Sharp+Half应偏向小牌型，实际: {committed}")

    def test_commitment_bonus_positive_for_matching_type(self):
        """commit 阶段目标牌型获得正加成。"""
        bonus = self.agent._commitment_bonus("pair", "pair", "commit")
        self.assertGreater(bonus, 0, "匹配牌型应有正加成")

    def test_commitment_bonus_zero_for_unrelated_hand_type(self):
        """execute 阶段不相关牌型不加分也不惩罚（避免AGENT1退化）。"""
        # flush 与 pair 不相关，返回0不加分
        bonus = self.agent._commitment_bonus("flush", "pair", "execute")
        self.assertEqual(bonus, 0.0, "不相关牌型不加分")

    def test_commitment_bonus_zero_for_explore_phase(self):
        """explore 阶段无论什么牌型都不加分。"""
        self.assertEqual(self.agent._commitment_bonus("pair", "pair", "explore"), 0.0)
        self.assertEqual(self.agent._commitment_bonus("flush", "pair", "explore"), 0.0)

    def test_sculpt_discard_keeps_pairs_for_pair_commitment(self):
        """pair 锁定后雕塑弃牌应保留对子。"""
        hand = [
            _card("c_Ah", "H", 14, "A"), _card("c_Ad", "D", 14, "A"),  # 一对A
            _card("c_5s", "S", 5, "5"), _card("c_5c", "C", 5, "5"),    # 一对5
            _card("c_3d", "D", 3, "3"), _card("c_7h", "H", 7, "7"),    # 散牌
            _card("c_9s", "S", 9, "9"), _card("c_Jc", "C", 11, "J"),   # 散牌
        ]
        state = self._state(ante=4, joker_keys=["j_half", "j_sly"], hand_cards=hand)
        discard, score = self.agent._commitment_sculpt_discard(state, hand, "pair", "commit")
        self.assertGreater(len(discard), 0, "应该产生弃牌")
        # 弃掉的牌不应包含对子牌（A对、5对的核心2张）
        kept = set(range(len(hand))) - set(discard)
        kept_ranks = [hand[i]["rank"] for i in kept]
        # 至少保留了一对
        from collections import Counter
        rank_counts = Counter(kept_ranks)
        has_pair = any(c >= 2 for c in rank_counts.values())
        self.assertTrue(has_pair, f"雕塑弃牌应保留至少一对，保留: {kept_ranks}")

    def test_sculpt_discard_keeps_suit_for_flush_commitment(self):
        """flush 锁定后雕塑弃牌应保留同花色。"""
        # 6张红心 + 2张黑桃
        hand = [
            _card("c_Ah", "H", 14, "A"), _card("c_Kh", "H", 13, "K"),
            _card("c_Qh", "H", 12, "Q"), _card("c_Jh", "H", 11, "J"),
            _card("c_10h", "H", 10, "10"), _card("c_9h", "H", 9, "9"),
            _card("c_8s", "S", 8, "8"), _card("c_7s", "S", 7, "7"),
        ]
        state = self._state(ante=4, joker_keys=["j_lusty_joker"], hand_cards=hand)
        discard, score = self.agent._commitment_sculpt_discard(state, hand, "flush", "commit")
        kept = set(range(len(hand))) - set(discard)
        # 保留的牌应全是红心
        for i in kept:
            self.assertEqual(hand[i]["suit"], "H",
                             f"flush雕塑应保留同花色，位置{i}是{hand[i]['suit']}")

    def test_supernova_with_half_locks_pair(self):
        """Supernova + Half Joker 应因 consistency 奖励锁定 pair。"""
        state = self._state(ante=5, joker_keys=["j_supernova", "j_half", "j_sly"])
        committed, phase, _ = self.agent._resolve_commitment(state)
        self.assertEqual(committed, "pair",
                         f"Supernova+Half+Sly应锁定pair，Supernova的consistency奖励强化pair信号，实际: {committed}")

    def test_mixed_signals_no_clear_winner_stays_explore(self):
        """冲突信号且无一方足够强时保持探索。"""
        # flush信号: 3.0, straight信号: 2.5 — 两者都低于ante 3门槛(3.5)
        state = self._state(ante=3, joker_keys=["j_lusty_joker", "j_superposition"])
        committed, phase, _ = self.agent._resolve_commitment(state)
        # 两者信号都未达阈值，应保持探索
        self.assertIsNone(committed, f"弱冲突信号应保持探索，实际锁定: {committed}")
        self.assertEqual(phase, "explore")
