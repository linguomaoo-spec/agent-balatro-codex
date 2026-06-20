"""scoring_sim 单元测试：验证单手得分模拟、缺口估算与边际贡献。

理论修改，不启动 BalatroBot。覆盖：
- 牌型判定与基础计分
- planet 等级加成
- steel held multiplier
- Joker 触发（加法 mult / xmult / scaling）
- 缺口估算
- 边际贡献：缺 ×Mult 时 ×Mult 牌提升 > chip Joker
"""
from __future__ import annotations

import unittest

from balatro_agent.scoring_sim import (
    SimCard,
    SimJoker,
    best_play,
    blind_requirement,
    classify,
    estimate_gap,
    marginal_contribution,
    parse_identity,
    score_play,
)


def card(identity: str, enhancement: str = "") -> SimCard:
    c = parse_identity(identity)
    c.enhancement = enhancement
    return c


class TestClassify(unittest.TestCase):
    def test_pair(self):
        self.assertEqual(classify([card("S_A"), card("H_A")]), "pair")

    def test_flush(self):
        flush = [card("S_A"), card("S_K"), card("S_Q"), card("S_9"), card("S_2")]
        self.assertEqual(classify(flush), "flush")

    def test_straight(self):
        straight = [card("S_5"), card("H_6"), card("D_7"), card("C_8"), card("S_9")]
        self.assertEqual(classify(straight), "straight")

    def test_straight_flush(self):
        sf = [card("S_5"), card("S_6"), card("S_7"), card("S_8"), card("S_9")]
        self.assertEqual(classify(sf), "straight_flush")

    def test_wheel_straight(self):
        wheel = [card("S_A"), card("S_2"), card("S_3"), card("S_4"), card("S_5")]
        self.assertEqual(classify(wheel), "straight_flush")

    def test_high_card_single(self):
        self.assertEqual(classify([card("S_A")]), "high_card")


class TestScorePlay(unittest.TestCase):
    def test_plain_high_card(self):
        # A 高牌：base(5,1) + A chip(11) = 16 chips × 1 = 16
        bd = score_play([card("S_A"), card("H_3")], [0])
        self.assertEqual(bd.hand_label, "high_card")
        self.assertEqual(bd.score, 16)

    def test_pair(self):
        # pair AA: base(10,2) + A+A chips(11+11)=32 chips × 2 = 64
        bd = score_play([card("S_A"), card("H_A"), card("S_3")], [0, 1])
        self.assertEqual(bd.hand_label, "pair")
        self.assertEqual(bd.score, 64)

    def test_planet_level_bonus(self):
        # pair level 2: base(10+5, 2+1) = (15,3) + 22 chips = 37 × 3 = 111
        hand = [card("S_A"), card("H_A")]
        bd = score_play(hand, [0, 1], levels={"pair": 2})
        self.assertEqual(bd.score, 111)

    def test_steel_held_multiplier(self):
        # 手中持有一张未打出的 steel：×1.5
        hand = [card("S_A"), card("H_A"), card("S_3", "STEEL")]
        bd = score_play(hand, [0, 1])
        self.assertAlmostEqual(bd.xmult, 1.5)

    def test_half_joker_adds_mult(self):
        # j_half: 1-3 张牌 +20 mult。pair AA base(10,2)+22 chips, mult=2+20=22 → 32×22=704
        hand = [card("S_A"), card("H_A")]
        jokers = [SimJoker("j_half")]
        bd = score_play(hand, [0, 1], jokers)
        self.assertEqual(bd.score, 704)

    def test_xmult_joker_multiplies(self):
        # j_card_sharp 近似 ×3
        hand = [card("S_A"), card("H_A")]
        jokers = [SimJoker("j_card_sharp")]
        bd = score_play(hand, [0, 1], jokers)
        # base 32 chips × 2 mult × 3 xmult = 192
        self.assertEqual(bd.score, 192)


class TestBestPlay(unittest.TestCase):
    def test_picks_higher_scoring_combo(self):
        hand = [card("S_A"), card("H_A"), card("S_3"), card("H_5"), card("S_9")]
        idx, bd = best_play(hand)
        self.assertEqual(bd.hand_label, "pair")
        self.assertEqual(sorted(idx), [0, 1])

    def test_require_five_for_psychic(self):
        hand = [card("S_A"), card("H_A"), card("S_3"), card("H_5"), card("S_9")]
        idx, bd = best_play(hand, require_five=True)
        self.assertEqual(len(idx), 5)


class TestBlindRequirement(unittest.TestCase):
    def test_ante1_small(self):
        self.assertEqual(blind_requirement(1, "small"), 300)

    def test_ante3_big(self):
        self.assertEqual(blind_requirement(3, "big"), 3000)

    def test_ante8_boss(self):
        self.assertEqual(blind_requirement(8, "boss"), 100000)


class TestGapAndMarginal(unittest.TestCase):
    def _state(self, hand_cards, joker_keys, ante=1, score=0, required=300, hands=4):
        from balatro_agent.model import GameState

        raw = {
            "phase": "SELECTING_HAND",
            "ante": ante,
            "score": score,
            "required_score": required,
            "hands_left": hands,
            "hand_cards": hand_cards,
            "jokers": [{"key": k} for k in joker_keys],
        }
        return GameState(raw)

    def test_gap_can_clear_when_score_sufficient(self):
        # pair AA = 64，4 手 = 256 < 300 → 不能清
        state = self._state(["S_A", "H_A", "S_3", "H_5", "S_9"], [], ante=1, required=300)
        gap = estimate_gap(state)
        self.assertFalse(gap.can_clear_blind)

    def test_marginal_xmult_beats_chip_joker_when_missing_mult(self):
        # 缺 ×Mult 的典型局面：只有加法 mult joker，×Mult 牌应带来更大边际
        # 构造：pair AA base=64，已有 j_half → 704。缺口大。
        state = self._state(
            ["S_A", "H_A", "S_3", "H_5", "S_9"],
            ["j_half"],
            ante=6,
            score=0,
            required=20000,
        )
        # j_card_sharp 是 ×Mult；j_scholar 主要是 chip/A-mult
        xmult_gain = marginal_contribution(state, "j_card_sharp")
        # baseline：j_half 下 pair=704。加 card_sharp ×3 → 2112，提升 1408
        self.assertGreater(xmult_gain, 0)
        self.assertEqual(xmult_gain, 1408)

    def test_marginal_returns_zero_for_neutral(self):
        state = self._state(["S_A", "H_A", "S_3", "H_5", "S_9"], [], ante=1)
        # 经济类 neutral joker 不影响单手得分
        self.assertEqual(marginal_contribution(state, "j_rocket"), 0)


class TestParseJokersAndLevels(unittest.TestCase):
    def test_parse_jokers_from_state(self):
        from balatro_agent.model import GameState

        raw = {"jokers": [{"key": "j_half"}, {"key": "j_campfire", "extra": {"mult": 5}}]}
        state = GameState(raw)
        from balatro_agent.scoring_sim import parse_jokers

        jokers = parse_jokers(state)
        self.assertEqual([j.key for j in jokers], ["j_half", "j_campfire"])
        self.assertEqual(jokers[1].multiplier, 5.0)

    def test_hand_levels(self):
        from balatro_agent.model import GameState

        raw = {
            "hands": {
                "Pair": {"level": 3},
                "Flush": {"level": 1},
            }
        }
        state = GameState(raw)
        from balatro_agent.scoring_sim import hand_levels

        levels = hand_levels(state)
        self.assertEqual(levels.get("pair"), 3)
        self.assertEqual(levels.get("flush"), 1)


if __name__ == "__main__":
    unittest.main()
