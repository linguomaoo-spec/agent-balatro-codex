import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from balatro_agent.client import BalatroBotClient
from balatro_agent.cli import main
from balatro_agent.recorder import ActionRecorder, StateRecorder


class StateRecorderTests(unittest.TestCase):
    def test_action_recorder_writes_single_grouped_action_json(self):
        states = iter(
            [
                {
                    "state": "BLIND_SELECT",
                    "ante": 1,
                    "round": 0,
                    "money": 4,
                    "hands": 5,
                    "discards": 3,
                },
                {
                    "state": "BLIND_SELECT",
                    "ante": 1,
                    "round": 0,
                    "money": 8,
                    "hands": 5,
                    "discards": 3,
                },
                {
                    "state": "SELECTING_HAND",
                    "ante": 1,
                    "round": 1,
                    "money": 8,
                    "hands": 5,
                    "discards": 3,
                    "required_score": 450,
                    "hand": {
                        "cards": [
                            _card(1, "S_A"),
                            _card(2, "D_K"),
                            _card(3, "D_T"),
                            _card(4, "D_7"),
                            _card(5, "C_5"),
                        ]
                    },
                },
                {
                    "state": "DRAW_TO_HAND",
                    "ante": 1,
                    "round": 1,
                    "money": 8,
                    "hands": 5,
                    "discards": 2,
                    "required_score": 450,
                    "hand": {
                        "cards": [
                            _card(1, "S_A"),
                            _card(5, "C_5"),
                            _card(6, "H_4"),
                            _card(7, "H_3"),
                            _card(8, "S_2"),
                        ]
                    },
                },
                {
                    "state": "HAND_PLAYED",
                    "ante": 1,
                    "round": 1,
                    "money": 8,
                    "hands": 4,
                    "discards": 2,
                    "required_score": 450,
                    "hand": {
                        "cards": [
                            _card(1, "S_A", highlighted=True),
                            _card(5, "C_5", highlighted=True),
                            _card(6, "H_4", highlighted=True),
                            _card(7, "H_3", highlighted=True),
                            _card(8, "S_2", highlighted=True),
                        ]
                    },
                },
                {
                    "state": "SHOP",
                    "ante": 1,
                    "round": 1,
                    "money": 16,
                    "hands": 5,
                    "discards": 3,
                    "shop": {"cards": [{"id": 10, "key": "j_crazy", "label": "Crazy Joker", "set": "JOKER"}]},
                    "jokers": {"cards": []},
                },
                {
                    "state": "SHOP",
                    "ante": 1,
                    "round": 1,
                    "money": 12,
                    "hands": 5,
                    "discards": 3,
                    "shop": {"cards": []},
                    "jokers": {
                        "cards": [{"id": 10, "key": "j_crazy", "label": "Crazy Joker", "set": "JOKER"}]
                    },
                },
                {
                    "state": "GAME_OVER",
                    "ante": 1,
                    "round": 2,
                    "money": 12,
                    "hands": 0,
                    "discards": 0,
                    "score": 300,
                    "required_score": 600,
                    "won": False,
                },
            ]
        )

        def transport(payload, base_url, timeout):
            if payload["method"] == "gamestate":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": next(states)}
            raise AssertionError("unexpected method")

        client = BalatroBotClient(transport=transport)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "human-actions.json"
            recorder = ActionRecorder(client, output)

            result = recorder.run(interval_seconds=0.0, max_polls=20)

            payload = json.loads(output.read_text())

        self.assertEqual(result["status"], "game_over_loss")
        self.assertEqual(payload["type"], "human_action_run")
        self.assertFalse(_has_key(payload, "raw"))
        actions = [action for round_record in payload["rounds"] for action in round_record["actions"]]
        self.assertEqual([action["method"] for action in actions], ["skip_blind", "select_blind", "discard", "play", "buy", "game_over"])
        self.assertEqual(actions[0]["reward_money"], 4)
        self.assertEqual(actions[1]["required_score"], 450)
        self.assertEqual(actions[2]["cards"], ["D_K", "D_T", "D_7"])
        self.assertEqual(actions[3]["cards"], ["S_A", "C_5", "H_4", "H_3", "S_2"])
        self.assertEqual(actions[4]["item"], "Crazy Joker")
        self.assertEqual(actions[5]["status"], "game_over_loss")
        self.assertEqual(payload["rounds"][1]["ante"], 1)
        self.assertEqual(payload["rounds"][1]["round"], 1)

    def test_records_inferred_play_and_discard_actions(self):
        states = iter(
            [
                {
                    "state": "SELECTING_HAND",
                    "hands": 5,
                    "discards": 3,
                    "hand": {
                        "cards": [
                            _card(1, "S_A"),
                            _card(2, "H_K"),
                            _card(3, "D_Q"),
                            _card(4, "C_J"),
                            _card(5, "S_9"),
                            _card(6, "H_8"),
                            _card(7, "D_7"),
                            _card(8, "C_6"),
                        ]
                    },
                },
                {
                    "state": "SELECTING_HAND",
                    "hands": 5,
                    "discards": 2,
                    "hand": {
                        "cards": [
                            _card(1, "S_A"),
                            _card(2, "H_K"),
                            _card(3, "D_Q"),
                            _card(4, "C_J"),
                            _card(9, "S_5"),
                            _card(10, "H_4"),
                            _card(11, "D_3"),
                            _card(12, "C_2"),
                        ]
                    },
                },
                {
                    "state": "HAND_PLAYED",
                    "hands": 4,
                    "discards": 2,
                    "hand": {
                        "cards": [
                            _card(1, "S_A", highlighted=True),
                            _card(2, "H_K", highlighted=True),
                            _card(3, "D_Q", highlighted=True),
                            _card(4, "C_J"),
                            _card(9, "S_5"),
                            _card(10, "H_4"),
                            _card(11, "D_3"),
                            _card(12, "C_2"),
                        ]
                    },
                },
            ]
        )

        def transport(payload, base_url, timeout):
            if payload["method"] == "gamestate":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": next(states)}
            raise AssertionError("unexpected method")

        client = BalatroBotClient(transport=transport)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "human-actions.jsonl"
            recorder = StateRecorder(client, output)

            result = recorder.run(interval_seconds=0.0, max_snapshots=3)

            records = [json.loads(line) for line in output.read_text().splitlines()]

        self.assertEqual(result["status"], "max_snapshots")
        self.assertNotIn("action", records[0])
        self.assertEqual(records[1]["action"]["method"], "discard")
        self.assertEqual(records[1]["action"]["card_keys"], ["S_9", "H_8", "D_7", "C_6"])
        self.assertEqual(records[1]["action"]["drawn_card_keys"], ["S_5", "H_4", "D_3", "C_2"])
        self.assertEqual(records[1]["action"]["source"], "hand_delta")
        self.assertEqual(records[2]["action"]["method"], "play")
        self.assertEqual(records[2]["action"]["card_keys"], ["S_A", "H_K", "D_Q"])
        self.assertEqual(records[2]["action"]["source"], "highlighted_hand")

    def test_records_changed_state_snapshots_until_game_over(self):
        states = iter(
            [
                {
                    "state": "SELECTING_HAND",
                    "ante": 1,
                    "round": 1,
                    "score": 0,
                    "required_score": 300,
                },
                {
                    "state": "SELECTING_HAND",
                    "ante": 1,
                    "round": 1,
                    "score": 0,
                    "required_score": 300,
                },
                {
                    "state": "SHOP",
                    "ante": 1,
                    "round": 1,
                    "money": 6,
                    "shop": {"cards": [{"name": "Ice Cream"}]},
                },
                {
                    "state": "GAME_OVER",
                    "won": False,
                    "ante": 1,
                    "round": 2,
                    "score": 250,
                    "required_score": 600,
                },
            ]
        )

        def transport(payload, base_url, timeout):
            if payload["method"] == "gamestate":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": next(states)}
            raise AssertionError("unexpected method")

        client = BalatroBotClient(transport=transport)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "human-run.jsonl"
            recorder = StateRecorder(client, output)

            result = recorder.run(interval_seconds=0.0, max_polls=10)

            records = [json.loads(line) for line in output.read_text().splitlines()]

        self.assertEqual(result["status"], "game_over_loss")
        self.assertEqual(result["polls"], 4)
        self.assertEqual(result["snapshots"], 3)
        self.assertEqual([record["state"]["phase"] for record in records], ["SELECTING_HAND", "SHOP", "GAME_OVER"])
        self.assertEqual(records[0]["snapshot_index"], 0)
        self.assertEqual(records[1]["previous_hash"], records[0]["state_hash"])
        self.assertIn("raw", records[0])
        self.assertTrue(records[2]["terminal"])

    def test_can_write_summary_only_and_stop_after_snapshot_limit(self):
        def transport(payload, base_url, timeout):
            if payload["method"] == "gamestate":
                return {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "state": "BLIND_SELECT",
                        "ante": 1,
                        "round": 1,
                    },
                }
            raise AssertionError("unexpected method")

        client = BalatroBotClient(transport=transport)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "summary-only.jsonl"
            recorder = StateRecorder(client, output, include_raw=False)

            result = recorder.run(interval_seconds=0.0, max_snapshots=1)

            record = json.loads(output.read_text())

        self.assertEqual(result["status"], "max_snapshots")
        self.assertEqual(result["snapshots"], 1)
        self.assertEqual(record["state"]["phase"], "BLIND_SELECT")
        self.assertNotIn("raw", record)

    def test_zero_limits_do_not_poll_game_state(self):
        def transport(payload, base_url, timeout):
            raise AssertionError("gamestate should not be called")

        client = BalatroBotClient(transport=transport)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "empty.jsonl"
            recorder = StateRecorder(client, output)

            result = recorder.run(max_snapshots=0)

        self.assertEqual(result["status"], "max_snapshots")
        self.assertEqual(result["polls"], 0)
        self.assertEqual(result["snapshots"], 0)
        self.assertFalse(output.exists())

    def test_record_cli_writes_jsonl_and_prints_summary(self):
        class FakeClient:
            def gamestate(self):
                return {
                    "state": "SHOP",
                    "ante": 2,
                    "round": 5,
                    "money": 8,
                }

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "cli-record.jsonl"
            stdout = io.StringIO()

            with mock.patch("balatro_agent.cli.BalatroBotClient", return_value=FakeClient()):
                with contextlib.redirect_stdout(stdout):
                    result = main(
                        [
                            "record",
                            "--output",
                            str(output),
                            "--interval",
                            "0",
                            "--max-snapshots",
                            "1",
                        ]
                    )

            payload = json.loads(stdout.getvalue())
            records = [json.loads(line) for line in output.read_text().splitlines()]

        self.assertEqual(result, 0)
        self.assertEqual(payload["status"], "max_snapshots")
        self.assertEqual(payload["snapshots"], 1)
        self.assertEqual(records[0]["state"]["phase"], "SHOP")

    def test_record_actions_cli_writes_single_json(self):
        class FakeClient:
            def __init__(self):
                self.states = iter(
                    [
                        {
                            "state": "BLIND_SELECT",
                            "ante": 1,
                            "round": 0,
                            "money": 4,
                        },
                        {
                            "state": "GAME_OVER",
                            "ante": 1,
                            "round": 1,
                            "money": 4,
                            "score": 10,
                            "required_score": 300,
                            "won": False,
                        },
                    ]
                )

            def gamestate(self):
                return next(self.states)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "actions.json"
            stdout = io.StringIO()

            with mock.patch("balatro_agent.cli.BalatroBotClient", return_value=FakeClient()):
                with contextlib.redirect_stdout(stdout):
                    result = main(
                        [
                            "record-actions",
                            "--output",
                            str(output),
                            "--interval",
                            "0",
                        ]
                    )

            payload = json.loads(stdout.getvalue())
            record = json.loads(output.read_text())

        self.assertEqual(result, 0)
        self.assertEqual(payload["status"], "game_over_loss")
        self.assertEqual(record["type"], "human_action_run")
        self.assertEqual(record["rounds"][0]["actions"][0]["method"], "game_over")


def _card(card_id, key, highlighted=False):
    card = {
        "id": card_id,
        "key": key,
        "value": {"rank": key.split("_", 1)[1], "suit": key.split("_", 1)[0]},
    }
    if highlighted:
        card["state"] = {"highlight": True}
    return card


def _has_key(value, key):
    if isinstance(value, dict):
        return key in value or any(_has_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_has_key(item, key) for item in value)
    return False


if __name__ == "__main__":
    unittest.main()
