import random
import unittest
from unittest.mock import call, patch

from balatro_agent.evolution import EvalResult, make_live_run_factory
from balatro_agent.model import Genome


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

    def test_eval_score_distinguishes_same_ante_losses_by_score_and_resources(self):
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
                        "money": 10,
                        "jokers": 2,
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
                        "money": 40,
                        "jokers": 5,
                        "won": False,
                    },
                }
            ],
        )

        self.assertGreater(stronger.score, weaker.score)

    @patch("balatro_agent.evolution.Runner")
    @patch("balatro_agent.evolution.BalatroBotClient")
    def test_live_run_factory_returns_to_menu_before_start(self, client_cls, runner_cls):
        client = client_cls.return_value
        runner = runner_cls.return_value
        runner.run.return_value = {"status": "max_steps", "steps": 1}
        run_factory = make_live_run_factory("http://127.0.0.1:12346", "RED", "WHITE", 5, 3.0)

        result = run_factory(Genome.default(), "AGENT1", None)

        self.assertEqual(result["status"], "max_steps")
        self.assertEqual(
            client.method_calls[:2],
            [
                call.call("menu", {}),
                call.start(deck="RED", stake="WHITE", seed="AGENT1"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
