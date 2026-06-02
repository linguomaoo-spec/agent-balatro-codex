import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from balatro_agent.client import BalatroBotClient
from balatro_agent.cli import main
from balatro_agent.recorder import StateRecorder


class StateRecorderTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
