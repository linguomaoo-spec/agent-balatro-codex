import unittest
import json
import tempfile
from pathlib import Path

from balatro_agent.model import ActionProposal, Decision, GameState, Genome
from balatro_agent.orchestrator import DefaultOrchestrator
from balatro_agent.cli import build_parser
from balatro_agent.search import (
    CheckpointScenarioLibrary,
    CheckpointSearchPlanner,
    SearchConfig,
    SearchStateMismatch,
    StateValue,
)


class StateValueTests(unittest.TestCase):
    def test_won_state_outranks_alive_and_lost_states(self):
        value = StateValue(Genome.default())
        won = GameState({"state": "GAME_OVER", "won": True, "ante": 1})
        alive = GameState({"state": "SHOP", "ante": 8, "round": 22, "money": 99})
        lost = GameState({"state": "GAME_OVER", "won": False, "ante": 9, "money": 999})

        self.assertGreater(value.evaluate(won), value.evaluate(alive))
        self.assertGreater(value.evaluate(alive), value.evaluate(lost))

    def test_progress_outranks_secondary_resources(self):
        value = StateValue(Genome.default())
        later = GameState({"state": "SHOP", "ante": 5, "round": 13, "money": 0})
        richer = GameState(
            {
                "state": "SHOP",
                "ante": 4,
                "round": 12,
                "money": 999,
                "jokers": {"cards": [{}, {}, {}, {}, {}]},
            }
        )

        self.assertGreater(value.evaluate(later), value.evaluate(richer))

    def test_same_progress_uses_blind_completion_before_resources(self):
        value = StateValue(Genome.default())
        closer = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 4,
                "round": 12,
                "score": 9000,
                "required_score": 10000,
                "money": 0,
            }
        )
        richer = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 4,
                "round": 12,
                "score": 1000,
                "required_score": 10000,
                "money": 999,
            }
        )

        self.assertGreater(value.evaluate(closer), value.evaluate(richer))


class SearchConfigTests(unittest.TestCase):
    def test_loads_search_config_and_cli_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "search.json"
            path.write_text(
                json.dumps(
                    {
                        "normal_budget": 5,
                        "priority_budget": 10,
                        "horizons": {"SHOP": 7},
                    }
                )
            )

            config = SearchConfig.load(path)

            self.assertEqual(config.normal_budget, 5)
            self.assertEqual(config.priority_budget, 10)
            self.assertEqual(config.horizons["SHOP"], 7)
            self.assertEqual(config.horizons["SMODS_BOOSTER_OPENED"], 4)
        for command in ("run", "eval", "evolve"):
            args = build_parser().parse_args([command, "--search", "--search-config", "custom.json"])
            self.assertTrue(args.search)
            self.assertEqual(args.search_config, Path("custom.json"))
        evolve = build_parser().parse_args(["evolve"])
        self.assertEqual(evolve.population, 8)
        self.assertEqual(evolve.seed_config, Path("config/eval-seeds.json"))


class CheckpointScenarioLibraryTests(unittest.TestCase):
    def test_captures_categorized_unique_scenarios_with_a_hard_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeCheckpointClient({"state": "MENU"})
            library = CheckpointScenarioLibrary(Path(tmp), max_scenarios=3)
            states = [
                GameState({"state": "SELECTING_HAND", "ante": 1, "round": 1}),
                GameState({"state": "SELECTING_HAND", "ante": 1, "round": 2, "blind": {"boss": True}}),
                GameState({"state": "SHOP", "ante": 2, "round": 3}),
                GameState({"state": "SHOP", "ante": 5, "round": 12}),
            ]

            captured = [library.capture(client, state, "AGENT1") for state in states]

            self.assertEqual(captured, [True, True, True, False])
            self.assertEqual([item["category"] for item in library.entries], ["hand", "boss", "shop_early"])
            self.assertEqual(len(library.checkpoints()), 3)
            self.assertTrue((Path(tmp) / "manifest.json").exists())

    def test_reserves_capacity_per_category_instead_of_filling_with_hands(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeCheckpointClient({"state": "MENU"})
            library = CheckpointScenarioLibrary(Path(tmp), max_scenarios=6)

            for round_number in range(1, 5):
                library.capture(
                    client,
                    GameState({"state": "SELECTING_HAND", "ante": 1, "round": round_number}),
                    "AGENT1",
                )
            library.capture(client, GameState({"state": "SHOP", "ante": 2, "round": 4}), "AGENT1")

            self.assertEqual([entry["category"] for entry in library.entries], ["hand", "shop_early"])

    def test_deduplicates_the_same_state_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeCheckpointClient({"state": "MENU"})
            library = CheckpointScenarioLibrary(Path(tmp))
            state = GameState({"state": "BLIND_SELECT", "ante": 1, "round": 1})

            self.assertTrue(library.capture(client, state, "AGENT1"))
            self.assertFalse(library.capture(client, state, "AGENT1"))
            self.assertEqual(len(library.entries), 1)

            library.freeze()
            later = GameState({"state": "SHOP", "ante": 5, "round": 12})
            self.assertFalse(library.capture(client, later, "AGENT1"))


class FakeCheckpointClient:
    def __init__(self, root, save_error=False, corrupt_restore=False, fail_load_at=None):
        self.state = dict(root)
        self.saved = None
        self.save_error = save_error
        self.corrupt_restore = corrupt_restore
        self.executed = []
        self.load_count = 0
        self.fail_load_at = fail_load_at

    def save_checkpoint(self, path: Path):
        if self.save_error:
            raise ConnectionError("save failed")
        self.saved = dict(self.state)

    def load_checkpoint(self, path: Path):
        self.load_count += 1
        if self.load_count == self.fail_load_at:
            raise ConnectionError("load failed")
        self.state = dict(self.saved)
        if self.corrupt_restore and self.load_count > 1:
            self.state["money"] = 999

    def gamestate(self):
        return dict(self.state)

    def execute(self, action):
        self.executed.append(action.method)
        self.state["money"] = int(action.params.get("value", 0))
        return dict(self.state)


class NoopRolloutOrchestrator:
    def __init__(self):
        self.calls = 0

    def decide_with_details(self, state):
        self.calls += 1
        action = ActionProposal("gamestate", {}, 0.0, "rollout")
        return Decision(state, action, [action], [])


class SearchPlannerTests(unittest.TestCase):
    def _decision(self, state, count=8, duplicate=False):
        proposals = [
            ActionProposal("buy", {"card": index, "value": index}, 100 - index, "shop")
            for index in range(count)
        ]
        if duplicate:
            proposals.append(proposals[0])
        return Decision(state, proposals[0], proposals, [])

    def test_ordinary_search_deduplicates_and_limits_to_six_branches(self):
        state = GameState({"state": "BLIND_SELECT", "ante": 1, "round": 1, "money": 0})
        client = FakeCheckpointClient(state.raw)
        planner = CheckpointSearchPlanner(
            client,
            NoopRolloutOrchestrator(),
            Genome.default(),
            SearchConfig(normal_budget=6, priority_budget=12, horizons={"BLIND_SELECT": 0}),
        )

        result = planner.choose(state, self._decision(state, count=8, duplicate=True))

        self.assertEqual(result.summary["candidate_count"], 8)
        self.assertEqual(result.summary["evaluated_count"], 6)
        self.assertEqual(len(result.summary["branches"]), 6)
        self.assertEqual(client.load_count, 7)
        self.assertEqual(client.state, state.raw)

    def test_shop_search_uses_priority_budget(self):
        state = GameState({"state": "SHOP", "ante": 2, "round": 4, "money": 0})
        client = FakeCheckpointClient(state.raw)
        planner = CheckpointSearchPlanner(
            client,
            NoopRolloutOrchestrator(),
            Genome.default(),
            SearchConfig(normal_budget=6, priority_budget=12, horizons={"SHOP": 0}),
        )

        result = planner.choose(state, self._decision(state, count=14))

        self.assertEqual(result.summary["evaluated_count"], 12)

    def test_current_boss_in_blinds_schema_uses_priority_budget(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 2,
                "round": 6,
                "blinds": {"boss": {"status": "CURRENT", "type": "BOSS"}},
            }
        )
        client = FakeCheckpointClient(state.raw)
        planner = CheckpointSearchPlanner(
            client,
            NoopRolloutOrchestrator(),
            Genome.default(),
            SearchConfig(normal_budget=2, priority_budget=4, horizons={"SELECTING_HAND": 0}),
        )

        result = planner.choose(state, self._decision(state, count=6))

        self.assertEqual(result.summary["evaluated_count"], 4)

    def test_rollout_uses_base_orchestrator_without_recursive_search(self):
        state = GameState({"state": "BLIND_SELECT", "ante": 1, "round": 1})
        client = FakeCheckpointClient(state.raw)
        rollout = NoopRolloutOrchestrator()
        planner = CheckpointSearchPlanner(
            client,
            rollout,
            Genome.default(),
            SearchConfig(normal_budget=2, priority_budget=2, horizons={"BLIND_SELECT": 2}),
        )

        planner.choose(state, self._decision(state, count=2))

        self.assertEqual(rollout.calls, 4)

    def test_save_failure_falls_back_to_original_selection(self):
        state = GameState({"state": "SHOP", "ante": 1, "round": 1})
        client = FakeCheckpointClient(state.raw, save_error=True)
        planner = CheckpointSearchPlanner(client, NoopRolloutOrchestrator(), Genome.default())
        decision = self._decision(state, count=2)

        result = planner.choose(state, decision)

        self.assertEqual(result.selected, decision.selected)
        self.assertEqual(result.summary["fallback_reason"], "checkpoint_save_failed")

    def test_mismatched_final_restore_raises_infra_error(self):
        state = GameState({"state": "SHOP", "ante": 1, "round": 1, "money": 0})
        client = FakeCheckpointClient(state.raw, corrupt_restore=True)
        planner = CheckpointSearchPlanner(
            client,
            NoopRolloutOrchestrator(),
            Genome.default(),
            SearchConfig(horizons={"SHOP": 0}),
        )

        with self.assertRaises(SearchStateMismatch):
            planner.choose(state, self._decision(state, count=2))

    def test_failed_final_restore_raises_state_mismatch(self):
        state = GameState({"state": "SHOP", "ante": 1, "round": 1})
        client = FakeCheckpointClient(state.raw, fail_load_at=3)
        planner = CheckpointSearchPlanner(
            client,
            NoopRolloutOrchestrator(),
            Genome.default(),
            SearchConfig(normal_budget=2, priority_budget=2, horizons={"SHOP": 0}),
        )

        with self.assertRaises(SearchStateMismatch):
            planner.choose(state, self._decision(state, count=2))

    def test_branch_load_failure_counts_toward_disabling_search(self):
        state = GameState({"state": "SHOP", "ante": 1, "round": 1})
        client = FakeCheckpointClient(state.raw, fail_load_at=1)
        planner = CheckpointSearchPlanner(
            client,
            NoopRolloutOrchestrator(),
            Genome.default(),
            SearchConfig(
                normal_budget=2,
                priority_budget=2,
                horizons={"SHOP": 0},
                disable_after_failures=1,
            ),
        )
        decision = self._decision(state, count=2)

        planner.choose(state, decision)
        fallback = planner.choose(state, decision)

        self.assertTrue(planner.disabled)
        self.assertEqual(fallback.summary["fallback_reason"], "search_disabled")


class SearchCandidateTests(unittest.TestCase):
    def test_search_decision_expands_hand_candidates_without_changing_default_decision(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 2,
                "round": 4,
                "hands": 4,
                "discards": 3,
                "hand": [
                    {"value": {"rank": "A", "suit": "S"}},
                    {"value": {"rank": "A", "suit": "H"}},
                    {"value": {"rank": "K", "suit": "S"}},
                    {"value": {"rank": "Q", "suit": "S"}},
                    {"value": {"rank": "J", "suit": "S"}},
                    {"value": {"rank": "T", "suit": "S"}},
                    {"value": {"rank": "9", "suit": "D"}},
                    {"value": {"rank": "2", "suit": "C"}},
                ],
            }
        )
        orchestrator = DefaultOrchestrator()

        regular = orchestrator.decide_with_details(state)
        expanded = orchestrator.decide_with_details(state, search=True)

        self.assertLessEqual(len([p for p in expanded.proposals if p.method == "play"]), 4)
        self.assertLessEqual(len([p for p in expanded.proposals if p.method == "discard"]), 2)
        self.assertGreater(len(expanded.proposals), len(regular.proposals))
        self.assertEqual(regular.selected, orchestrator.decide_with_details(state).selected)


if __name__ == "__main__":
    unittest.main()
