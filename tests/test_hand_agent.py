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
