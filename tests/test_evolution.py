import random
import unittest

from balatro_agent.evolution import EvalResult
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


if __name__ == "__main__":
    unittest.main()
