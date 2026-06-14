import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from balatro_agent.client import BalatroBotClient
from balatro_agent.orchestrator import DefaultOrchestrator
from balatro_agent.runner import Runner
from balatro_agent.search import SearchChoice, SearchStateMismatch


class RunnerTests(unittest.TestCase):
    def test_runner_captures_stable_decision_state_for_scenario_library(self):
        captured = []

        class Library:
            def capture(self, client, state, seed):
                captured.append((state.phase, seed))

        def transport(payload, base_url, timeout):
            if payload["method"] == "gamestate":
                return {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"state": "BLIND_SELECT", "ante": 1, "round": 1},
                }
            if payload["method"] == "select":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": {}}
            raise AssertionError("收到未预期的方法")

        runner = Runner(
            BalatroBotClient(transport=transport),
            DefaultOrchestrator(),
            scenario_library=Library(),
            seed="AGENT1",
        )

        runner.step()

        self.assertEqual(captured, [("BLIND_SELECT", "AGENT1")])

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

    def test_run_logs_terminal_game_over_state(self):
        def transport(payload, base_url, timeout):
            if payload["method"] == "gamestate":
                return {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "state": "GAME_OVER",
                        "won": False,
                        "ante": 1,
                        "round": 2,
                    },
                }
            raise AssertionError("收到未预期的方法")

        client = BalatroBotClient(transport=transport)

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "decisions.jsonl"
            runner = Runner(client, DefaultOrchestrator(), log_path=log_path)

            result = runner.run(max_steps=10)

            self.assertEqual(result["status"], "game_over_loss")
            records = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["state"]["phase"], "GAME_OVER")

    def test_run_continues_after_connection_error_if_state_progressed(self):
        states = iter(
            [
                {"state": "BLIND_SELECT", "ante": 1, "round": 1},
                {"state": "SELECTING_HAND", "ante": 1, "round": 1},
                {"state": "GAME_OVER", "won": False, "ante": 1, "round": 1},
            ]
        )

        def transport(payload, base_url, timeout):
            if payload["method"] == "gamestate":
                state = next(states)
                return {"jsonrpc": "2.0", "id": payload["id"], "result": state}
            if payload["method"] == "select":
                raise ConnectionError("temporary 502")
            raise AssertionError("收到未预期的方法")

        client = BalatroBotClient(transport=transport, retry_delay=0.0)

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "decisions.jsonl"
            runner = Runner(client, DefaultOrchestrator(), log_path=log_path)

            result = runner.run(max_steps=10, sleep_seconds=0.0)

            self.assertEqual(result["status"], "game_over_loss")
            self.assertEqual(result["steps"], 1)
            records = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
            self.assertNotIn("error", records[0])
            self.assertEqual(records[0]["transport_warning"]["type"], "connection")

    def test_run_does_not_count_gamestate_fallback_polls_as_steps(self):
        calls = []
        states = iter(
            [
                {"state": "HAND_PLAYED", "ante": 1, "round": 1},
                {"state": "DRAW_TO_HAND", "ante": 1, "round": 1},
                {
                    "state": "SELECTING_HAND",
                    "ante": 1,
                    "round": 1,
                    "hands": 1,
                    "discards": 0,
                    "hand": [{"value": {"rank": "A", "suit": "S"}}],
                },
                {"state": "GAME_OVER", "won": False, "ante": 1, "round": 1},
            ]
        )

        def transport(payload, base_url, timeout):
            calls.append(payload["method"])
            if payload["method"] == "gamestate":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": next(states)}
            if payload["method"] == "play":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": {"state": "HAND_PLAYED"}}
            raise AssertionError("收到未预期的方法")

        client = BalatroBotClient(transport=transport)
        runner = Runner(client, DefaultOrchestrator())

        result = runner.run(max_steps=10, sleep_seconds=0.0)

        self.assertEqual(result["status"], "game_over_loss")
        self.assertEqual(result["steps"], 1)
        self.assertEqual(calls.count("play"), 1)

    def test_run_waits_through_play_tarot_transition(self):
        calls = []
        states = iter(
            [
                {"state": "PLAY_TAROT", "ante": 2, "round": 4},
                {
                    "state": "SELECTING_HAND",
                    "ante": 2,
                    "round": 4,
                    "hands": 1,
                    "discards": 0,
                    "hand": [{"value": {"rank": "A", "suit": "S"}}],
                },
                {"state": "GAME_OVER", "won": False, "ante": 2, "round": 4},
            ]
        )

        def transport(payload, base_url, timeout):
            calls.append(payload["method"])
            if payload["method"] == "gamestate":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": next(states)}
            if payload["method"] == "play":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": {"state": "HAND_PLAYED"}}
            raise AssertionError("收到未预期的方法")

        client = BalatroBotClient(transport=transport)
        runner = Runner(client, DefaultOrchestrator())

        result = runner.run(max_steps=10, sleep_seconds=0.0)

        self.assertEqual(result["status"], "game_over_loss")
        self.assertEqual(result["steps"], 1)
        self.assertEqual(calls.count("play"), 1)

    def test_run_waits_through_new_round_transition(self):
        calls = []
        states = iter(
            [
                {"state": "NEW_ROUND", "ante": 3, "round": 9},
                {"state": "ROUND_EVAL", "ante": 4, "round": 9, "score": 6312},
                {"state": "GAME_OVER", "won": False, "ante": 4, "round": 9},
            ]
        )

        def transport(payload, base_url, timeout):
            calls.append(payload["method"])
            if payload["method"] == "gamestate":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": next(states)}
            if payload["method"] == "cash_out":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": {"state": "SHOP"}}
            raise AssertionError("收到未预期的方法")

        client = BalatroBotClient(transport=transport)
        runner = Runner(client, DefaultOrchestrator())

        result = runner.run(max_steps=10, sleep_seconds=0.0)

        self.assertEqual(result["status"], "game_over_loss")
        self.assertEqual(calls, ["gamestate", "gamestate", "cash_out", "gamestate"])
        self.assertEqual(result["steps"], 1)

    @patch("balatro_agent.runner.time.sleep")
    def test_run_waits_before_cash_out_round_eval(self, sleep):
        calls = []
        states = iter(
            [
                {"state": "ROUND_EVAL", "ante": 2, "round": 4, "score": 1596},
                {"state": "GAME_OVER", "won": False, "ante": 2, "round": 4},
            ]
        )

        def transport(payload, base_url, timeout):
            calls.append(payload["method"])
            if payload["method"] == "gamestate":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": next(states)}
            if payload["method"] == "cash_out":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": {"state": "SHOP"}}
            raise AssertionError("收到未预期的方法")

        client = BalatroBotClient(transport=transport)
        runner = Runner(client, DefaultOrchestrator())

        result = runner.run(max_steps=10, sleep_seconds=0.0)

        self.assertEqual(result["status"], "game_over_loss")
        self.assertEqual(calls, ["gamestate", "cash_out", "gamestate"])
        sleep.assert_called_once_with(2.0)

    def test_run_uses_planner_selection_and_logs_search_summary(self):
        calls = []
        states = iter(
            [
                {"state": "SHOP", "ante": 1, "round": 2, "money": 10},
                {"state": "GAME_OVER", "won": False, "ante": 1, "round": 2},
            ]
        )

        def transport(payload, base_url, timeout):
            calls.append(payload["method"])
            if payload["method"] == "gamestate":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": next(states)}
            if payload["method"] == "reroll":
                return {"jsonrpc": "2.0", "id": payload["id"], "result": {"state": "SHOP"}}
            raise AssertionError("收到未预期的方法")

        class Planner:
            def choose(self, state, decision):
                return SearchChoice(
                    ActionProposal("reroll", {}, 99.0, "search"),
                    {"candidate_count": 2, "evaluated_count": 2, "branches": []},
                )

        from balatro_agent.model import ActionProposal

        client = BalatroBotClient(transport=transport)
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "decisions.jsonl"
            runner = Runner(client, DefaultOrchestrator(), log_path=log_path, planner=Planner())

            result = runner.run(max_steps=2, sleep_seconds=0.0)

            records = [json.loads(line) for line in log_path.read_text().splitlines()]
        self.assertEqual(result["status"], "game_over_loss")
        self.assertIn("reroll", calls)
        self.assertEqual(records[0]["executed"]["method"], "reroll")
        self.assertEqual(records[0]["search"]["evaluated_count"], 2)

    def test_run_stops_with_infra_error_on_search_state_mismatch(self):
        executed = []

        def transport(payload, base_url, timeout):
            if payload["method"] == "gamestate":
                return {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"state": "SHOP", "ante": 1, "round": 2},
                }
            executed.append(payload["method"])
            return {"jsonrpc": "2.0", "id": payload["id"], "result": {}}

        class Planner:
            def choose(self, state, decision):
                raise SearchStateMismatch("restore mismatch")

        client = BalatroBotClient(transport=transport)
        runner = Runner(client, DefaultOrchestrator(), planner=Planner())

        result = runner.run(max_steps=2, sleep_seconds=0.0)

        self.assertEqual(result["status"], "infra_error")
        self.assertEqual(result["error"]["type"], "search_state_mismatch")
        self.assertEqual(executed, [])


if __name__ == "__main__":
    unittest.main()
