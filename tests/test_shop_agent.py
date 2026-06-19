import unittest

from balatro_agent.agents.shop import ShopAgent
from balatro_agent.model import GameState, Genome


def _make_shop_state(**overrides):
    """Build minimal SHOP state fixture."""
    base = {
        "state": "SHOP",
        "ante": 1,
        "money": 10,
        "shop": {"cards": []},
        "jokers": [],
        "consumables": {"cards": [], "limit": 2},
        "hand": [],
        "deck": {"cards": []},
    }
    base.update(overrides)
    return GameState(base)


class ShopAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = ShopAgent()
        self.genome = Genome.default()

    def test_produces_no_proposals_on_wrong_phase(self):
        """Returns empty list when not in SHOP phase."""
        state = _make_shop_state(state="SELECTING_HAND")
        proposals = self.agent.propose(state, self.genome)
        self.assertEqual(len(proposals), 0)

    def test_empty_shop_returns_no_buy(self):
        """Empty shop produces no buy proposals (next_round handled by RoundAgent)."""
        state = _make_shop_state()
        proposals = self.agent.propose(state, self.genome)
        buy_proposals = [p for p in proposals if p.method == "buy"]
        self.assertEqual(len(buy_proposals), 0,
                         "Empty shop should have no buy proposals")

    def test_produces_buy_for_affordable_joker(self):
        """Affordable joker produces buy action."""
        state = _make_shop_state(
            money=10,
            shop={
                "cards": [
                    {"key": "j_joker", "name": "Joker", "cost": 2, "type": "Joker"}
                ]
            },
        )
        proposals = self.agent.propose(state, self.genome)
        methods = {p.method for p in proposals}
        self.assertIn("buy", methods)

    def test_does_not_buy_when_broke(self):
        """No buy proposals when broke."""
        state = _make_shop_state(
            money=0,
            shop={
                "cards": [
                    {"key": "j_joker", "name": "Joker", "cost": 2, "type": "Joker"}
                ]
            },
        )
        proposals = self.agent.propose(state, self.genome)
        buy_proposals = [p for p in proposals if p.method == "buy"]
        self.assertEqual(len(buy_proposals), 0,
                         "Should not propose buying with no money")

    def test_joker_strength_positive_for_known_joker(self):
        """Known joker has positive strength score."""
        state = _make_shop_state(ante=1)
        score = self.agent._joker_strength(
            {"key": "j_gros_michel", "name": "Gros Michel", "type": "Joker"},
            state,
        )
        self.assertGreater(score, 0)

    def test_joker_strength_positive_for_unknown_key(self):
        """Unknown joker key still has positive base strength (default 14)."""
        state = _make_shop_state(ante=1)
        score = self.agent._joker_strength(
            {"key": "j_nonexistent_xyz", "name": "???", "type": "Joker"},
            state,
        )
        # Unknown jokers get a base of 14, which is positive
        self.assertGreater(score, 0)
