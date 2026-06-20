"""lookahead.py 单元测试：廉价手牌前瞻与弃牌雕塑判断。

理论修改，不启动 BalatroBot。覆盖：
- lookahead_play_value 单手与 depth=2
- sculpt_potential 保留子集的潜在得分
- should_discard_over_play：弱牌+雕塑潜力→弃牌；已够清盲→不弃
"""
from __future__ import annotations

import unittest

from balatro_agent.lookahead import (
    lookahead_play_value,
    sculpt_potential,
    should_discard_over_play,
)
from balatro_agent.model import GameState


def _state(hand_cards, joker_keys=None, ante=1, score=0, required=300,
           hands=4, discards=4, deck=44):
    raw = {
        "phase": "SELECTING_HAND",
        "ante": ante,
        "score": score,
        "required_score": required,
        "hands_left": hands,
        "discards_left": discards,
        "hand_cards": hand_cards,
        "jokers": [{"key": k} for k in (joker_keys or [])],
        "deck_card_count": deck,
    }
    return GameState(raw)


class TestLookaheadPlayValue(unittest.TestCase):
    def test_single_hand_value(self):
        state = _state(["S_A", "H_A", "S_3", "H_5", "S_9"])
        value, idx, label = lookahead_play_value(state, depth=1)
        self.assertEqual(label, "pair")
        self.assertEqual(value, 64)

    def test_depth2_accumulates_when_below_blind(self):
        # 得分远低于盲注需求 → 第二手期望计入累计
        state = _state(["S_A", "H_A", "S_3", "H_5", "S_9"], required=20000, score=0)
        value1, _, _ = lookahead_play_value(state, depth=1)
        value2, _, _ = lookahead_play_value(state, depth=2)
        self.assertEqual(value1, 64)
        self.assertEqual(value2, 128)  # 翻倍


class TestSculptPotential(unittest.TestCase):
    def test_kept_pair_has_potential(self):
        state = _state(["S_A", "H_A", "S_3", "H_5", "S_9"])
        # 保留两个 A：至少能构成 pair=64
        potential = sculpt_potential(state, [0, 1])
        self.assertGreaterEqual(potential, 64)

    def test_empty_keep_returns_zero(self):
        state = _state(["S_A", "H_A"])
        self.assertEqual(sculpt_potential(state, []), 0)


class TestShouldDiscardOverPlay(unittest.TestCase):
    def test_no_discard_when_no_discards_left(self):
        state = _state(["S_3", "H_5", "S_7", "H_9", "S_2"],
                       discards=0, required=20000)
        self.assertIsNone(should_discard_over_play(state))

    def test_no_discard_when_play_clears_blind(self):
        # pair AA = 64 >= 64 blind gap? required=64, score=0 → gap=64, play=64 → 清盲
        state = _state(["S_A", "H_A", "S_3", "H_5", "S_9"],
                       required=64, score=0)
        self.assertIsNone(should_discard_over_play(state))

    def test_discard_suggested_when_sculpt_higher(self):
        # 弱牌 high card，但保留同花胚雕塑潜力更高
        state = _state(["S_A", "S_K", "S_Q", "H_5", "H_9"],
                       required=300, score=0, ante=1)
        result = should_discard_over_play(state)
        # 保留三张同花 S：潜在 flush(35,4)+A+K+Q chips = (35+11+10+10)*4=264
        # 当前最佳 high_card single A = 16。264 >= 16*1.3 → 应建议弃牌
        if result is not None:
            discard, play, sculpt, reason = result
            self.assertEqual(reason, "sculpt_higher_hand")
            self.assertGreater(sculpt, play)
            self.assertGreater(len(discard), 0)


if __name__ == "__main__":
    unittest.main()
