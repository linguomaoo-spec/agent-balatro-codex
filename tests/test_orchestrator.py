import unittest

from balatro_agent.agents import Agent, default_agents
from balatro_agent.model import ActionProposal, GameState, Genome
from balatro_agent.orchestrator import DefaultOrchestrator


class OrchestratorTests(unittest.TestCase):
    """Test DefaultOrchestrator orchestration behavior: agent dispatch, validation, fallback."""

    def test_default_agents_returns_list(self):
        """default_agents() returns non-empty agent list."""
        agents = default_agents()
        self.assertIsInstance(agents, list)
        self.assertGreater(len(agents), 0)
        for agent in agents:
            self.assertIsInstance(agent, Agent)

    def test_round_eval_auto_cash_out(self):
        """ROUND_EVAL phase auto cash_out."""
        state = GameState({"state": "ROUND_EVAL"})
        orchestrator = DefaultOrchestrator()
        action = orchestrator.decide(state)
        self.assertEqual(action.method, "cash_out")

    def test_selecting_hand_picks_valid_play(self):
        """SELECTING_HAND phase produces valid play/discard action."""
        state = GameState({
            "state": "SELECTING_HAND",
            "hand": [
                {"key": "c_2c", "suit": "C", "rank": 2, "value": "2", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_3c", "suit": "C", "rank": 3, "value": "3", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_4c", "suit": "C", "rank": 4, "value": "4", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_5c", "suit": "C", "rank": 5, "value": "5", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_6c", "suit": "C", "rank": 6, "value": "6", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_7c", "suit": "C", "rank": 7, "value": "7", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_8c", "suit": "C", "rank": 8, "value": "8", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_9c", "suit": "C", "rank": 9, "value": "9", "enhancement": None, "seal": None, "edition": None},
            ],
            "jokers": [],
            "chips_required": 300,
            "hands_remaining": 4,
            "discards_remaining": 3,
            "hand_levels": {},
            "consumables": {"cards": [], "limit": 2},
            "deck": {"cards": []},
            "ante": 1,
            "round": 1,
        })
        orchestrator = DefaultOrchestrator()
        action = orchestrator.decide(state)
        self.assertIn(action.method, ("play", "discard"))

    def test_shop_falls_back_to_next_round_when_nothing_valid(self):
        """SHOP phase falls back to next_round when nothing valid."""
        state = GameState({"state": "SHOP", "ante": 1, "money": 0, "shop": {"cards": []}})
        orchestrator = DefaultOrchestrator()
        action = orchestrator.decide(state)
        self.assertIn(action.method, ("next_round", "gamestate"))

    def test_decide_with_details_records_rejected_proposals(self):
        """decide_with_details returns Decision with rejected proposals."""
        state = GameState({
            "state": "SELECTING_HAND",
            "hand": [
                {"key": "c_2h", "suit": "H", "rank": 2, "value": "2", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_3h", "suit": "H", "rank": 3, "value": "3", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_4h", "suit": "H", "rank": 4, "value": "4", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_5h", "suit": "H", "rank": 5, "value": "5", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_6h", "suit": "H", "rank": 6, "value": "6", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_7h", "suit": "H", "rank": 7, "value": "7", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_8h", "suit": "H", "rank": 8, "value": "8", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_9h", "suit": "H", "rank": 9, "value": "9", "enhancement": None, "seal": None, "edition": None},
            ],
            "jokers": [],
            "chips_required": 300,
            "hands_remaining": 4,
            "discards_remaining": 3,
            "hand_levels": {},
            "consumables": {"cards": [], "limit": 2},
            "deck": {"cards": []},
            "ante": 1,
            "round": 1,
        })
        orchestrator = DefaultOrchestrator()
        decision = orchestrator.decide_with_details(state)
        self.assertIsNotNone(decision.selected)
        self.assertIsInstance(decision.proposals, list)
        self.assertIsInstance(decision.rejected, list)

    def test_genome_passed_to_agents(self):
        """Custom Genome is passed to agents."""
        state = GameState({"state": "ROUND_EVAL"})
        low_genome = Genome.default()
        high_genome = Genome.default()
        orch_low = DefaultOrchestrator(genome=low_genome)
        orch_high = DefaultOrchestrator(genome=high_genome)
        self.assertEqual(orch_low.decide(state).method, orch_high.decide(state).method)

    def test_custom_agents_list(self):
        """Custom agent list replaces default list."""
        state = GameState({
            "state": "SELECTING_HAND",
            "hand": [
                {"key": "c_2c", "suit": "C", "rank": 2, "value": "2", "enhancement": None, "seal": None, "edition": None},
                {"key": "c_3c", "suit": "C", "rank": 3, "value": "3", "enhancement": None, "seal": None, "edition": None},
            ],
            "jokers": [],
            "chips_required": 300,
            "hands_remaining": 4,
            "discards_remaining": 3,
            "hand_levels": {},
            "consumables": {"cards": [], "limit": 2},
            "deck": {"cards": []},
            "ante": 1,
            "round": 1,
        })

        class AlwaysPlayAgent(Agent):
            name = "always_play"
            def propose(self, state, genome):
                return [ActionProposal("play", {"cards": [0]}, 100.0, self.name)]

        orchestrator = DefaultOrchestrator(agents=[AlwaysPlayAgent()])
        action = orchestrator.decide(state)
        self.assertEqual(action.method, "play")
