import unittest

from balatro_agent.model import GameState


class GameStateTests(unittest.TestCase):
    def test_summary_includes_won_when_present(self):
        state = GameState({"state": "GAME_OVER", "won": True})

        self.assertTrue(state.won)
        self.assertTrue(state.summary()["won"])

    def test_summary_includes_area_counts(self):
        state = GameState(
            {
                "state": "SHOP",
                "jokers": [{}, {}],
                "consumables": [{}],
            }
        )

        self.assertEqual(state.summary()["jokers"], 2)
        self.assertEqual(state.summary()["consumables"], 1)

    def test_parses_current_balatrobot_schema_aliases(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante_num": 3,
                "round_num": 7,
                "round": {
                    "hands_left": 2,
                    "discards_left": 1,
                    "chips": 120,
                },
                "blinds": {
                    "current": {
                        "score": 300,
                    }
                },
                "hand": {
                    "cards": [
                        {"value": {"rank": "A"}},
                        {"value": {"rank": "K"}},
                    ]
                },
                "jokers": {
                    "cards": [
                        {"key": "j_joker"},
                    ]
                },
            }
        )

        self.assertEqual(state.ante, 3)
        self.assertEqual(state.round_number, 7)
        self.assertEqual(state.hands_remaining, 2)
        self.assertEqual(state.discards_remaining, 1)
        self.assertEqual(state.score, 120)
        self.assertEqual(state.blind_requirement, 300)
        self.assertEqual(len(state.hand), 2)
        self.assertEqual(len(state.jokers), 1)


if __name__ == "__main__":
    unittest.main()
