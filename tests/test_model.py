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

    def test_summary_includes_hand_and_shop_details_for_debugging(self):
        state = GameState(
            {
                "state": "SHOP",
                "hand": {
                    "cards": [
                        {"key": "S_A", "value": {"rank": "A", "suit": "S"}},
                        {"value": {"rank": "K", "suit": "H"}},
                    ]
                },
                "jokers": {
                    "cards": [
                        {"key": "j_blue_joker"},
                    ]
                },
                "shop": {
                    "cards": [
                        {"label": "Earth", "set": "PLANET"},
                    ]
                },
            }
        )

        summary = state.summary()

        self.assertEqual(summary["hand_cards"], ["S_A", "H_K"])
        self.assertEqual(summary["joker_keys"], ["j_blue_joker"])
        self.assertEqual(summary["shop_cards"], ["Earth"])

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

    def test_parses_current_blind_requirement_from_status_marked_blinds(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "blinds": {
                    "small": {"status": "CURRENT", "score": 5000},
                    "big": {"status": "UPCOMING", "score": 7500},
                    "boss": {"status": "UPCOMING", "score": 10000},
                },
            }
        )

        self.assertEqual(state.blind_requirement, 5000)

    def test_parses_current_blind_name_from_status_marked_blinds(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "blinds": {
                    "small": {"status": "DEFEATED", "name": "Small Blind"},
                    "boss": {"status": "CURRENT", "name": "The Psychic", "score": 4000},
                },
            }
        )

        self.assertEqual(state.blind_name, "The Psychic")

    def test_parses_deck_and_discard_pile_cards_for_draw_odds(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "deck": {
                    "cards": [
                        {"value": {"rank": "9", "suit": "C"}},
                        {"value": {"rank": "T", "suit": "D"}},
                    ]
                },
                "discard_pile": [
                    {"value": {"rank": "A", "suit": "H"}},
                ],
            }
        )

        self.assertEqual(state.deck_card_count, 2)
        self.assertEqual(state.discard_pile_card_count, 1)
        self.assertEqual(state.summary()["deck_cards_remaining"], 2)
        self.assertEqual(state.summary()["discard_pile_cards"], ["H_A"])


if __name__ == "__main__":
    unittest.main()
