import random
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from balatro_agent.evolution import (
    EvalResult,
    EvolutionEngine,
    ParetoArchive,
    RunOutcome,
    make_checkpoint_run_factory,
    make_live_run_factory,
    passes_regression_gate,
)
from balatro_agent.model import Genome
from balatro_agent.search import SearchConfig


class EvolutionTests(unittest.TestCase):
    def test_genome_mutation_is_deterministic_with_seeded_rng(self):
        genome = Genome.default()
        first = genome.mutated(random.Random(7), sigma=0.1)
        second = genome.mutated(random.Random(7), sigma=0.1)

        self.assertEqual(first.weights, second.weights)
        self.assertNotEqual(first.weights, genome.weights)

    def test_genome_round_trips_json(self):
        genome = Genome.default().mutated(random.Random(3), sigma=0.05)
        payload = genome.to_json()

        restored = Genome.from_json(payload)

        self.assertEqual(restored.weights, genome.weights)
        self.assertEqual(restored.metadata, genome.metadata)

    def test_old_genome_json_loads_new_gene_defaults(self):
        payload = json.dumps({"weights": {"play": 1.25}, "metadata": {"version": 1}})

        genome = Genome.from_json(payload)

        self.assertEqual(genome.weight("play"), 1.25)
        self.assertEqual(genome.weight("cash_reserve_ante_scale"), 1.5)
        self.assertEqual(genome.weight("xmult_priority_ante"), 4.0)

    def test_mutation_changes_only_a_bounded_subset_and_respects_gene_specs(self):
        genome = Genome.default()

        mutated = genome.mutated(random.Random(7), mutation_rate=0.3)

        changed = [key for key in genome.weights if mutated.weights[key] != genome.weights[key]]
        self.assertGreaterEqual(len(changed), 1)
        self.assertLessEqual(len(changed), max(1, round(len(genome.weights) * 0.3)))
        self.assertEqual(mutated.weight("xmult_priority_ante"), round(mutated.weight("xmult_priority_ante")))
        for key, value in mutated.weights.items():
            lower, upper = Genome.bounds(key)
            self.assertGreaterEqual(value, lower)
            self.assertLessEqual(value, upper)

    def test_crossover_uses_values_from_both_elites(self):
        first = Genome.default()
        second = Genome({key: value + 0.1 for key, value in first.weights.items()})

        child = first.crossover(second, random.Random(3))

        self.assertTrue(any(child.weights[key] == first.weights[key] for key in first.weights))
        self.assertTrue(any(child.weights[key] == second.weights[key] for key in first.weights))

    def test_crossover_keeps_keys_present_in_only_one_parent(self):
        first = Genome({"play": 1.0})
        second = Genome({"discard": 0.5})

        child = first.crossover(second, random.Random(1))

        self.assertEqual(child.weights, {"play": 1.0, "discard": 0.5})

    def test_eval_score_rewards_won_state_even_with_generic_game_over_status(self):
        result = EvalResult(
            Genome.default(),
            runs=[
                {
                    "status": "game_over",
                    "steps": 25,
                    "state": {
                        "ante": 9,
                        "won": True,
                    },
                }
            ],
        )

        self.assertGreaterEqual(result.score, 280.0)

    def test_eval_score_uses_completion_but_not_dead_resources(self):
        genome = Genome.default()
        weaker = EvalResult(
            genome,
            runs=[
                {
                    "status": "game_over_loss",
                    "steps": 70,
                    "state": {
                        "ante": 4,
                        "score": 4000,
                        "required_score": 10000,
                        "money": 999,
                        "jokers": 5,
                        "won": False,
                    },
                }
            ],
        )
        stronger = EvalResult(
            genome,
            runs=[
                {
                    "status": "game_over_loss",
                    "steps": 70,
                    "state": {
                        "ante": 4,
                        "score": 7000,
                        "required_score": 10000,
                        "money": 0,
                        "jokers": 0,
                        "won": False,
                    },
                }
            ],
        )

        self.assertGreater(stronger.score, weaker.score)

        same_progress_rich = EvalResult(
            genome,
            runs=[
                {
                    "status": "game_over_loss",
                    "steps": 70,
                    "state": {
                        "ante": 4,
                        "score": 7000,
                        "required_score": 10000,
                        "money": 999,
                        "jokers": 5,
                    },
                }
            ],
        )
        self.assertEqual(stronger.score, same_progress_rich.score)

    def test_run_outcome_alive_state_outranks_terminal_failure(self):
        alive = RunOutcome.from_run(
            "SCENE",
            {"status": "max_steps", "steps": 4, "state": {"ante": 2}},
        )
        failed = RunOutcome.from_run(
            "SCENE",
            {"status": "game_over_loss", "steps": 1, "state": {"ante": 8}},
        )

        self.assertGreater(alive.rank_key, failed.rank_key)

    def test_run_outcome_ranking_uses_completion_after_ante(self):
        weaker = RunOutcome.from_run(
            "AGENT1",
            {"status": "game_over_loss", "steps": 10, "state": {"ante": 4, "score": 1000, "required_score": 20000}},
        )
        stronger = RunOutcome.from_run(
            "AGENT1",
            {"status": "game_over_loss", "steps": 10, "state": {"ante": 4, "score": 18000, "required_score": 20000}},
        )

        self.assertGreater(stronger.rank_key, weaker.rank_key)

    def test_pareto_archive_keeps_tradeoffs_instead_of_average_winner(self):
        genome = Genome.default()
        first = EvalResult(
            genome,
            runs=[
                {"seed": "AGENT1", "status": "game_over_loss", "state": {"ante": 6, "score": 29000, "required_score": 30000}},
                {"seed": "AGENT2", "status": "game_over_loss", "state": {"ante": 4, "score": 10000, "required_score": 20000}},
            ],
        )
        second = EvalResult(
            genome.mutated(random.Random(2)),
            runs=[
                {"seed": "AGENT1", "status": "game_over_loss", "state": {"ante": 5, "score": 21000, "required_score": 22000}},
                {"seed": "AGENT2", "status": "game_over_loss", "state": {"ante": 5, "score": 9000, "required_score": 11000}},
            ],
        )

        archive = ParetoArchive()
        archive.add(first)
        archive.add(second)

        self.assertEqual(len(archive.results), 2)
        self.assertFalse(first.dominates(second))
        self.assertFalse(second.dominates(first))

    def test_candidate_that_loses_a_win_cannot_dominate(self):
        genome = Genome.default()
        winner = EvalResult(
            genome,
            runs=[{"seed": "AGENT1", "status": "game_over_win", "state": {"ante": 8, "won": True}}],
        )
        loser = EvalResult(
            genome.mutated(random.Random(4)),
            runs=[{"seed": "AGENT1", "status": "game_over_loss", "state": {"ante": 9, "won": False}}],
        )

        self.assertFalse(loser.dominates(winner))
        self.assertGreater(winner.fitness_key, loser.fitness_key)

    def test_evaluate_records_seed_for_per_seed_ranking(self):
        engine = EvolutionEngine(
            lambda genome, seed, log_path: {
                "status": "game_over_loss",
                "state": {"ante": 3},
            }
        )

        result = engine.evaluate(Genome.default(), ["AGENT1"])

        self.assertEqual(result.runs[0]["seed"], "AGENT1")
        self.assertIn("AGENT1", result.outcomes)

    def test_regression_gate_blocks_per_seed_ante_or_error_regression(self):
        genome = Genome.default()
        baseline = EvalResult(
            genome,
            runs=[
                {"seed": "R1", "status": "game_over_win", "state": {"ante": 8, "won": True}},
                {"seed": "R2", "status": "game_over_loss", "state": {"ante": 5}},
            ],
        )
        lower_ante = EvalResult(
            genome,
            runs=[
                {"seed": "R1", "status": "game_over_win", "state": {"ante": 8, "won": True}},
                {"seed": "R2", "status": "game_over_loss", "state": {"ante": 4}},
            ],
        )
        added_error = EvalResult(
            genome,
            runs=[
                {"seed": "R1", "status": "game_over_win", "state": {"ante": 8, "won": True}},
                {"seed": "R2", "status": "game_over_loss", "error_count": 1, "state": {"ante": 5}},
            ],
        )

        self.assertFalse(passes_regression_gate(baseline, lower_ante)["promote"])
        self.assertFalse(passes_regression_gate(baseline, added_error)["promote"])

    def test_staged_evolution_promotes_three_dev_two_regression_and_one_heldout(self):
        calls = []
        scenario_calls = []

        def run_factory(genome, seed, log_path):
            calls.append(seed)
            return {
                "status": "game_over_loss",
                "steps": 10,
                "state": {"ante": 4, "score": 500, "required_score": 1000},
            }

        def scenario_factory(genome, seed, log_path):
            scenario_calls.append(seed)
            return {
                "status": "max_steps",
                "steps": 4,
                "state": {"ante": 2, "score": 250, "required_score": 1000},
            }

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            engine = EvolutionEngine(
                run_factory,
                rng=random.Random(4),
                scenario_run_factory=scenario_factory,
            )

            champion = engine.evolve_staged(
                Genome.default(),
                generations=1,
                population=4,
                scenario_seeds=["SCENE1"],
                dev_seeds=["DEV1"],
                regression_seeds=["REG1"],
                heldout_seeds=["HELD1"],
                output_dir=output_dir,
            )

            self.assertIsInstance(champion, EvalResult)
            self.assertEqual(calls.count("DEV1"), 4)  # baseline + generation top 3
            self.assertEqual(calls.count("REG1"), 3)  # baseline + final top 2
            self.assertEqual(calls.count("HELD1"), 1)
            self.assertEqual(scenario_calls.count("SCENE1"), 4)
            self.assertNotIn("SCENE1", calls)
            self.assertTrue((output_dir / "elite_archive.json").exists())
            self.assertTrue((output_dir / "fitness.json").exists())
            self.assertTrue((output_dir / "regression-gate.json").exists())
            self.assertTrue((output_dir / "heldout.json").exists())

    @patch("balatro_agent.evolution.Runner")
    @patch("balatro_agent.evolution.BalatroBotClient")
    def test_live_run_factory_returns_to_menu_before_start(self, client_cls, runner_cls):
        client = client_cls.return_value
        client.gamestate.return_value = {"state": "SHOP"}
        runner = runner_cls.return_value
        runner.run.return_value = {"status": "max_steps", "steps": 1}
        run_factory = make_live_run_factory("http://127.0.0.1:12346", "RED", "WHITE", 5, 3.0)

        result = run_factory(Genome.default(), "AGENT1", None)

        self.assertEqual(result["status"], "max_steps")
        self.assertEqual(
            client.method_calls[:3],
            [
                call.gamestate(),
                call.call("menu", {}),
                call.start(deck="RED", stake="WHITE", seed="AGENT1"),
            ],
        )

    @patch("balatro_agent.evolution.Runner")
    @patch("balatro_agent.evolution.BalatroBotClient")
    def test_live_run_factory_skips_menu_call_when_already_on_menu(self, client_cls, runner_cls):
        client = client_cls.return_value
        client.gamestate.side_effect = [{"state": "MENU"}, {"state": "BLIND_SELECT"}]
        runner = runner_cls.return_value
        runner.run.return_value = {"status": "max_steps", "steps": 1}
        run_factory = make_live_run_factory("http://127.0.0.1:12346", "RED", "WHITE", 5, 3.0)

        result = run_factory(Genome.default(), "AGENT1", None)

        self.assertEqual(result["status"], "max_steps")
        self.assertNotIn(call.call("menu", {}), client.method_calls)
        client.start.assert_called_once_with(deck="RED", stake="WHITE", seed="AGENT1")

    @patch("balatro_agent.evolution.time.sleep")
    @patch("balatro_agent.evolution.Runner")
    @patch("balatro_agent.evolution.BalatroBotClient")
    def test_live_run_factory_waits_for_start_to_leave_menu(
        self, client_cls, runner_cls, sleep
    ):
        client = client_cls.return_value
        client.gamestate.side_effect = [
            {"state": "MENU"},
            {"state": "MENU"},
            {"state": "BLIND_SELECT"},
        ]
        runner = runner_cls.return_value
        runner.run.return_value = {"status": "max_steps", "steps": 1}
        run_factory = make_live_run_factory("http://127.0.0.1:12346", "RED", "WHITE", 5, 3.0)

        result = run_factory(Genome.default(), "AGENT1", None)

        self.assertEqual(result["status"], "max_steps")
        self.assertEqual(client.gamestate.call_count, 3)
        sleep.assert_called()

    @patch("balatro_agent.evolution.time.sleep")
    @patch("balatro_agent.evolution.Runner")
    @patch("balatro_agent.evolution.BalatroBotClient")
    def test_live_run_factory_reports_start_timeout_instead_of_running_from_menu(
        self, client_cls, runner_cls, sleep
    ):
        client = client_cls.return_value
        client.gamestate.return_value = {"state": "MENU"}
        run_factory = make_live_run_factory("http://127.0.0.1:12346", "RED", "WHITE", 5, 3.0)

        result = run_factory(Genome.default(), "AGENT1", None)

        self.assertEqual(result["status"], "start_timeout")
        runner_cls.assert_not_called()

    @patch("balatro_agent.evolution.CheckpointSearchPlanner")
    @patch("balatro_agent.evolution.Runner")
    @patch("balatro_agent.evolution.BalatroBotClient")
    def test_live_run_factory_injects_search_planner_when_enabled(
        self, client_cls, runner_cls, planner_cls
    ):
        client = client_cls.return_value
        client.gamestate.side_effect = [{"state": "MENU"}, {"state": "BLIND_SELECT"}]
        runner_cls.return_value.run.return_value = {"status": "max_steps", "steps": 1}
        config = SearchConfig(normal_budget=3)
        run_factory = make_live_run_factory(
            "http://127.0.0.1:12346",
            "RED",
            "WHITE",
            5,
            3.0,
            search_config=config,
        )

        run_factory(Genome.default(), "AGENT1", None)

        self.assertIs(runner_cls.call_args.kwargs["planner"], planner_cls.return_value)
        self.assertIs(planner_cls.call_args.args[0], client)
        self.assertIs(planner_cls.call_args.args[3], config)

    @patch("balatro_agent.evolution.Runner")
    @patch("balatro_agent.evolution.BalatroBotClient")
    def test_live_run_factory_passes_scenario_library_and_seed_to_runner(
        self, client_cls, runner_cls
    ):
        client = client_cls.return_value
        client.gamestate.side_effect = [{"state": "MENU"}, {"state": "BLIND_SELECT"}]
        runner_cls.return_value.run.return_value = {"status": "max_steps", "steps": 1}
        library = object()
        run_factory = make_live_run_factory(
            "http://127.0.0.1:12346",
            "RED",
            "WHITE",
            5,
            3.0,
            scenario_library=library,
        )

        run_factory(Genome.default(), "AGENT1", None)

        self.assertIs(runner_cls.call_args.kwargs["scenario_library"], library)
        self.assertEqual(runner_cls.call_args.kwargs["seed"], "AGENT1")

    @patch("balatro_agent.evolution.Runner")
    @patch("balatro_agent.evolution.BalatroBotClient")
    def test_checkpoint_run_factory_loads_scenario_without_starting_a_new_run(
        self, client_cls, runner_cls
    ):
        client = client_cls.return_value
        client.gamestate.return_value = {"state": "SHOP", "ante": 2}
        runner_cls.return_value.run.return_value = {"status": "max_steps", "steps": 4}
        run_factory = make_checkpoint_run_factory(
            "http://127.0.0.1:12346",
            max_steps=6,
            timeout=3.0,
        )

        result = run_factory(Genome.default(), "/tmp/scenario.jkr", None)

        self.assertEqual(result["seed"], "/tmp/scenario.jkr")
        client.load_checkpoint.assert_called_once_with(Path("/tmp/scenario.jkr"))
        client.start.assert_not_called()
        runner_cls.return_value.run.assert_called_once_with(max_steps=6)


if __name__ == "__main__":
    unittest.main()
