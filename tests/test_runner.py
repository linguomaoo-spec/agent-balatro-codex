import json
import tempfile
import unittest
from pathlib import Path

from balatro_agent.client import BalatroBotClient
from balatro_agent.orchestrator import DefaultOrchestrator
from balatro_agent.runner import Runner


class RunnerTests(unittest.TestCase):
    def test_step_reads_state_executes_action_and_logs_decision(self):
        calls = []

        def transport(payload, base_url, timeout):
            calls.append(payload)
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
            if payload["method"] == "select":
                return {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"state": "SELECTING_HAND"},
                }
            raise AssertionError("收到未预期的方法")

        client = BalatroBotClient(transport=transport)

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "decisions.jsonl"
            runner = Runner(client, DefaultOrchestrator(), log_path=log_path)

            result = runner.step()

            self.assertEqual(result.method, "select")
            self.assertEqual([call["method"] for call in calls], ["gamestate", "select"])
            log_record = json.loads(log_path.read_text().strip())
            self.assertEqual(log_record["action"]["method"], "select")
            self.assertEqual(log_record["state"]["phase"], "BLIND_SELECT")

    def test_run_returns_win_status_when_game_over_state_is_won(self):
        def transport(payload, base_url, timeout):
            if payload["method"] == "gamestate":
                return {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "state": "GAME_OVER",
                        "won": True,
                        "ante": 9,
                    },
                }
            raise AssertionError("收到未预期的方法")

        client = BalatroBotClient(transport=transport)
        runner = Runner(client, DefaultOrchestrator())

        result = runner.run(max_steps=10)

        self.assertEqual(result["status"], "game_over_win")
        self.assertTrue(result["state"]["won"])


if __name__ == "__main__":
    unittest.main()
