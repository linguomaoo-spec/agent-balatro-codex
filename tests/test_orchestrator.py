import unittest

from balatro_agent.model import GameState, Genome
from balatro_agent.orchestrator import DefaultOrchestrator


class OrchestratorTests(unittest.TestCase):
    def test_round_eval_auto_cash_out(self):
        state = GameState({"state": "ROUND_EVAL"})
        orchestrator = DefaultOrchestrator()

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "cash_out")
        self.assertEqual(action.params, {})

    def test_selecting_hand_picks_valid_play(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"id": "c0", "rank": "2"},
                    {"id": "c1", "rank": "2"},
                    {"id": "c2", "rank": "A"},
                    {"id": "c3", "rank": "K"},
                ],
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [0, 1])
        self.assertGreater(action.score, 0)

    def test_shop_prefers_affordable_joker_purchase(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 8,
                "shop": {
                    "cards": [
                        {"name": "Planet", "type": "Consumable", "cost": 3},
                        {"name": "Joker", "type": "Joker", "cost": 4},
                    ],
                    "packs": [{"name": "Arcana Pack", "cost": 4}],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "buy")
        self.assertEqual(action.params, {"card": 1})

    def test_shop_falls_back_to_next_round_when_nothing_valid(self):
        state = GameState({"state": "SHOP", "money": 0, "shop": {"cards": []}})
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "next_round")


if __name__ == "__main__":
    unittest.main()
