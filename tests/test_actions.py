import unittest

from balatro_agent.actions import validate_action
from balatro_agent.model import ActionProposal, GameState


class ActionValidationTests(unittest.TestCase):
    def test_play_rejects_card_index_outside_hand_range(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [{"rank": "A"}, {"rank": "K"}],
            }
        )
        action = ActionProposal("play", {"cards": [0, 2]}, 1.0, "test")

        result = validate_action(action, state)

        self.assertFalse(result.ok)
        self.assertIn("超出", result.reason)

    def test_shop_actions_require_shop_phase(self):
        state = GameState({"state": "SELECTING_HAND", "hand": [{"rank": "A"}]})
        action = ActionProposal("buy", {"card": 0}, 1.0, "test")

        result = validate_action(action, state)

        self.assertFalse(result.ok)
        self.assertIn("SHOP", result.reason)

    def test_buy_requires_only_one_target(self):
        state = GameState({"state": "SHOP", "shop": {"cards": [{}]}})
        action = ActionProposal("buy", {"card": 0, "pack": 0}, 1.0, "test")

        result = validate_action(action, state)

        self.assertFalse(result.ok)
        self.assertIn("必须且只能指定", result.reason)


if __name__ == "__main__":
    unittest.main()
