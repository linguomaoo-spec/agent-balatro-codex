import unittest

from balatro_agent.agents import EconomyAgent, HandAgent, ShopAgent
from balatro_agent.model import GameState, Genome
from balatro_agent.orchestrator import DefaultOrchestrator


class OrchestratorTests(unittest.TestCase):
    def test_cash_reserve_ante_scale_gene_changes_shop_exit_score(self):
        state = GameState({"state": "SHOP", "ante": 6, "money": 0, "shop": {"cards": []}})
        low = Genome.default()
        high = Genome(dict(low.weights))
        low.weights["cash_reserve_ante_scale"] = 0.0
        high.weights["cash_reserve_ante_scale"] = 4.0

        low_score = EconomyAgent().propose(state, low)[0].score
        high_score = EconomyAgent().propose(state, high)[0].score

        self.assertGreater(high_score, low_score)

    def test_consumable_empty_slot_bonus_gene_changes_tarot_buy_score(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 2,
                "money": 20,
                "consumables": {"cards": [], "limit": 2},
                "shop": {
                    "cards": [
                        {"key": "c_empress", "set": "TAROT", "name": "The Empress", "cost": 3}
                    ]
                },
            }
        )
        low = Genome.default()
        high = Genome(dict(low.weights))
        low.weights["consumable_empty_slot_bonus"] = 1.0
        high.weights["consumable_empty_slot_bonus"] = 2.0

        low_score = next(p.score for p in ShopAgent().propose(state, low) if p.method == "buy")
        high_score = next(p.score for p in ShopAgent().propose(state, high) if p.method == "buy")

        self.assertGreater(high_score, low_score)
    def test_round_eval_auto_cash_out(self):
        state = GameState({"state": "ROUND_EVAL"})
        orchestrator = DefaultOrchestrator()

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "cash_out")
        self.assertEqual(action.params, {})

    def test_selecting_hand_picks_valid_play(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"id": "c0", "rank": "2"},
                    {"id": "c1", "rank": "2"},
                    {"id": "c2", "rank": "A"},
                    {"id": "c3", "rank": "K"},
                ],
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [0, 1])
        self.assertGreater(action.score, 0)

    def test_selecting_hand_prefers_made_flush_over_high_cards(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "A", "suit": "S"}},
                    {"value": {"rank": "K", "suit": "D"}},
                    {"value": {"rank": "2", "suit": "H"}},
                    {"value": {"rank": "5", "suit": "H"}},
                    {"value": {"rank": "7", "suit": "H"}},
                    {"value": {"rank": "9", "suit": "H"}},
                    {"value": {"rank": "J", "suit": "H"}},
                ],
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [6, 5, 4, 3, 2])

    def test_selecting_hand_treats_wild_card_as_flush_bridge(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "A", "suit": "H"}},
                    {"value": {"rank": "K", "suit": "H"}},
                    {"value": {"rank": "Q", "suit": "H"}},
                    {"value": {"rank": "J", "suit": "H"}},
                    {"value": {"rank": "9", "suit": "S"}, "modifier": {"enhancement": "WILD"}},
                ],
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(sorted(action.params["cards"]), [0, 1, 2, 3, 4])

    def test_selecting_hand_prefers_discard_for_strong_straight_flush_draw(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "K", "suit": "C"}},
                    {"value": {"rank": "2", "suit": "D"}},
                    {"value": {"rank": "6", "suit": "H"}},
                    {"value": {"rank": "7", "suit": "H"}},
                    {"value": {"rank": "8", "suit": "H"}},
                    {"value": {"rank": "9", "suit": "H"}},
                    {"value": {"rank": "3", "suit": "S"}},
                    {"value": {"rank": "4", "suit": "C"}},
                ],
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "discard")
        self.assertEqual(action.params["cards"], [0, 1, 6, 7])

    def test_selecting_hand_uses_deck_odds_to_avoid_dead_flush_draw(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "2", "suit": "H"}},
                    {"value": {"rank": "5", "suit": "H"}},
                    {"value": {"rank": "8", "suit": "H"}},
                    {"value": {"rank": "K", "suit": "H"}},
                    {"value": {"rank": "9", "suit": "D"}},
                    {"value": {"rank": "9", "suit": "S"}},
                    {"value": {"rank": "Q", "suit": "C"}},
                    {"value": {"rank": "J", "suit": "D"}},
                ],
                "deck": {
                    "cards": [
                        {"value": {"rank": "9", "suit": "C"}},
                        {"value": {"rank": "9", "suit": "D"}},
                        {"value": {"rank": "A", "suit": "S"}},
                        {"value": {"rank": "T", "suit": "C"}},
                        {"value": {"rank": "7", "suit": "D"}},
                    ]
                },
                "discard_pile": [
                    {"value": {"rank": "A", "suit": "H"}},
                    {"value": {"rank": "Q", "suit": "H"}},
                ],
                "hands": 4,
                "discards": 3,
                "blind": {"chips": 1200},
                "score": 0,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "discard")
        self.assertNotIn(4, action.params["cards"])
        self.assertNotIn(5, action.params["cards"])
        self.assertTrue({0, 1, 2} & set(action.params["cards"]))

    def test_selecting_hand_orders_highest_scoring_card_first_with_hanging_chad(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "2", "suit": "H"}},
                    {"value": {"rank": "2", "suit": "D"}},
                    {"value": {"rank": "A", "suit": "S"}},
                    {"value": {"rank": "A", "suit": "C"}},
                    {"value": {"rank": "3", "suit": "S"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                    ]
                },
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [2, 3, 0, 1])

    def test_selecting_hand_rearranges_trigger_card_before_playing_with_hanging_chad(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "A", "suit": "S"}},
                    {"value": {"rank": "K", "suit": "D"}},
                    {"value": {"rank": "A", "suit": "C"}, "enhancement": "MULT"},
                    {"value": {"rank": "4", "suit": "H"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                    ]
                },
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "rearrange")
        self.assertEqual(action.params, {"hand": [2, 0, 1, 3]})

    def test_selecting_hand_plays_five_cards_for_psychic_boss(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "blind": {"name": "The Psychic", "chips": 4000},
                "score": 0,
                "hands": 4,
                "discards": 4,
                "hand": [
                    {"value": {"rank": "A", "suit": "S"}},
                    {"value": {"rank": "A", "suit": "C"}},
                    {"value": {"rank": "Q", "suit": "H"}},
                    {"value": {"rank": "J", "suit": "H"}},
                    {"value": {"rank": "J", "suit": "D"}},
                    {"value": {"rank": "7", "suit": "D"}},
                    {"value": {"rank": "6", "suit": "C"}},
                    {"value": {"rank": "3", "suit": "D"}},
                ],
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(len(action.params["cards"]), 5)

    def test_hand_agent_adds_club_bonus_for_gluttonous_joker(self):
        agent = HandAgent()
        state = GameState({"jokers": {"cards": [{"key": "j_gluttenous_joker"}]}})
        club_hand = [{"value": {"rank": "8", "suit": "C"}}]
        heart_hand = [{"value": {"rank": "8", "suit": "H"}}]

        club_bonus = agent._joker_play_bonus(state, club_hand, [0])
        heart_bonus = agent._joker_play_bonus(state, heart_hand, [0])

        self.assertGreater(club_bonus, heart_bonus)

    def test_hand_agent_adds_rank_bonus_for_walkie_talkie(self):
        agent = HandAgent()
        state = GameState({"jokers": {"cards": [{"key": "j_walkie_talkie"}]}})
        ten_hand = [{"value": {"rank": "T", "suit": "S"}}]
        jack_hand = [{"value": {"rank": "J", "suit": "S"}}]

        ten_bonus = agent._joker_play_bonus(state, ten_hand, [0])
        jack_bonus = agent._joker_play_bonus(state, jack_hand, [0])

        self.assertGreater(ten_bonus, jack_bonus)

    def test_hand_agent_uses_current_hand_levels_from_state(self):
        agent = HandAgent()
        state = GameState(
            {
                "hands": {
                    "Pair": {"chips": 10, "mult": 2, "level": 1, "played": 0, "played_this_round": 0, "order": 11},
                    "Full House": {"chips": 80, "mult": 8, "level": 3, "played": 0, "played_this_round": 0, "order": 6},
                }
            }
        )

        full_house_bonus = agent._hand_value_bonus(state, "full_house")
        pair_bonus = agent._hand_value_bonus(state, "pair")

        self.assertGreater(full_house_bonus, pair_bonus)

    def test_selecting_hand_prefers_mult_enhanced_pair(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "2", "suit": "C"}, "modifier": {"enhancement": "MULT"}},
                    {"value": {"rank": "2", "suit": "D"}, "modifier": {"enhancement": "MULT"}},
                    {"value": {"rank": "4", "suit": "H"}},
                    {"value": {"rank": "K", "suit": "S"}},
                    {"value": {"rank": "A", "suit": "H"}},
                ],
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [0, 1])

    def test_selecting_hand_prefers_short_pair_when_half_joker_is_active(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "A", "suit": "C"}},
                    {"value": {"rank": "A", "suit": "D"}},
                    {"value": {"rank": "K", "suit": "S"}},
                    {"value": {"rank": "K", "suit": "H"}},
                    {"value": {"rank": "2", "suit": "C"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_half", "label": "Half Joker"},
                    ]
                },
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [0, 1])

    def test_selecting_hand_prefers_discard_when_weak_pair_cannot_meet_current_blind(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante_num": 4,
                "round_num": 10,
                "round": {
                    "hands_left": 4,
                    "discards_left": 4,
                    "chips": 0,
                },
                "blinds": {
                    "small": {"status": "CURRENT", "score": 5000},
                    "big": {"status": "UPCOMING", "score": 7500},
                    "boss": {"status": "UPCOMING", "score": 10000},
                },
                "hand": {
                    "cards": [
                        {"value": {"rank": "K", "suit": "S"}},
                        {"value": {"rank": "K", "suit": "C"}, "modifier": {"enhancement": "MULT"}},
                        {"value": {"rank": "Q", "suit": "S"}},
                        {"value": {"rank": "J", "suit": "C"}},
                        {"value": {"rank": "T", "suit": "C"}},
                        {"value": {"rank": "7", "suit": "C"}},
                        {"value": {"rank": "4", "suit": "D"}},
                        {"value": {"rank": "2", "suit": "D"}},
                    ]
                },
                "jokers": {
                    "cards": [
                        {"key": "j_gluttenous_joker"},
                        {"key": "j_blue_joker"},
                        {"key": "j_hanging_chad"},
                        {"key": "j_walkie_talkie"},
                    ]
                },
                "hands": {
                    "Pair": {"chips": 10, "mult": 2, "level": 1},
                    "Straight": {"chips": 30, "mult": 4, "level": 1},
                    "Flush": {"chips": 35, "mult": 4, "level": 1},
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "discard")
        # Joker感知: Gluttonous会倾向保留梅花牌，新行为同样合理
        self.assertIn(action.params["cards"], ([5, 6, 7], [0, 6, 7]))

    def test_selecting_hand_can_discard_on_last_hand_when_pressure_is_high(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante_num": 4,
                "round_num": 11,
                "round": {
                    "hands_left": 1,
                    "discards_left": 3,
                    "chips": 6802,
                },
                "blinds": {
                    "small": {"status": "CURRENT", "score": 7500},
                },
                "hand": {
                    "cards": [
                        {"value": {"rank": "K", "suit": "C"}},
                        {"value": {"rank": "Q", "suit": "C"}},
                        {"value": {"rank": "T", "suit": "C"}},
                        {"value": {"rank": "8", "suit": "S"}},
                        {"value": {"rank": "5", "suit": "H"}},
                        {"value": {"rank": "4", "suit": "D"}},
                        {"value": {"rank": "2", "suit": "D"}},
                        {"value": {"rank": "2", "suit": "S"}},
                    ]
                },
                "jokers": {
                    "cards": [
                        {"key": "j_gluttenous_joker"},
                        {"key": "j_blue_joker"},
                        {"key": "j_hanging_chad"},
                        {"key": "j_walkie_talkie"},
                        {"key": "j_four_fingers"},
                    ]
                },
                "hands": {
                    "Pair": {"chips": 10, "mult": 2, "level": 1},
                    "Flush": {"chips": 50, "mult": 6, "level": 2},
                    "Straight": {"chips": 50, "mult": 6, "level": 2},
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "discard")

    def test_selecting_hand_uses_last_discard_to_break_half_joker_pair_tunnel(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 6,
                "round": 17,
                "score": 21292,
                "blind": {"chips": 30000},
                "hands": 1,
                "discards": 4,
                "hand": [
                    {"value": {"rank": "A", "suit": "H"}},
                    {"value": {"rank": "A", "suit": "D"}},
                    {"value": {"rank": "Q", "suit": "S"}},
                    {"value": {"rank": "9", "suit": "C"}},
                    {"value": {"rank": "6", "suit": "S"}},
                    {"value": {"rank": "5", "suit": "D"}},
                    {"value": {"rank": "3", "suit": "H"}},
                    {"value": {"rank": "3", "suit": "D"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_blue_joker", "label": "Blue Joker"},
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_walkie_talkie", "label": "Walkie Talkie"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                    ],
                    "limit": 5,
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "discard")
        self.assertEqual(action.params["cards"], [2, 3, 4, 5])

    def test_selecting_hand_does_not_chain_pressure_discards_until_empty(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 6,
                "round": 17,
                "score": 21292,
                "blind": {"chips": 30000},
                "hands": 1,
                "discards": 3,
                "hand": [
                    {"value": {"rank": "A", "suit": "H"}},
                    {"value": {"rank": "A", "suit": "D"}},
                    {"value": {"rank": "J", "suit": "H"}},
                    {"value": {"rank": "J", "suit": "C"}},
                    {"value": {"rank": "8", "suit": "H"}},
                    {"value": {"rank": "5", "suit": "C"}},
                    {"value": {"rank": "3", "suit": "H"}},
                    {"value": {"rank": "3", "suit": "D"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_blue_joker", "label": "Blue Joker"},
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_walkie_talkie", "label": "Walkie Talkie"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                    ],
                    "limit": 5,
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [0, 1])

    def test_selecting_hand_prefers_single_ace_when_scholar_is_active(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "A", "suit": "C"}},
                    {"value": {"rank": "K", "suit": "S"}},
                    {"value": {"rank": "Q", "suit": "S"}},
                    {"value": {"rank": "6", "suit": "C"}},
                    {"value": {"rank": "6", "suit": "D"}},
                    {"value": {"rank": "5", "suit": "C"}},
                    {"value": {"rank": "3", "suit": "D"}},
                    {"value": {"rank": "2", "suit": "S"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                        {"key": "j_scholar", "label": "Scholar"},
                    ]
                },
                "hands": 4,
                "discards": 4,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [0])

    def test_selecting_hand_prefers_single_face_card_when_photograph_is_active(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "K", "suit": "S"}},
                    {"value": {"rank": "Q", "suit": "S"}},
                    {"value": {"rank": "8", "suit": "S"}},
                    {"value": {"rank": "8", "suit": "C"}},
                    {"value": {"rank": "6", "suit": "C"}},
                    {"value": {"rank": "5", "suit": "C"}},
                    {"value": {"rank": "3", "suit": "D"}},
                    {"value": {"rank": "2", "suit": "S"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                        {"key": "j_photograph", "label": "Photograph"},
                    ]
                },
                "hands": 4,
                "discards": 4,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [0])

    def test_selecting_hand_prefers_scholar_ace_over_photograph_face_card(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "A", "suit": "H"}},
                    {"value": {"rank": "K", "suit": "S"}},
                    {"value": {"rank": "Q", "suit": "S"}},
                    {"value": {"rank": "8", "suit": "C"}},
                    {"value": {"rank": "6", "suit": "C"}},
                    {"value": {"rank": "5", "suit": "C"}},
                    {"value": {"rank": "3", "suit": "D"}},
                    {"value": {"rank": "2", "suit": "S"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                        {"key": "j_scholar", "label": "Scholar"},
                        {"key": "j_photograph", "label": "Photograph"},
                    ]
                },
                "hands": 4,
                "discards": 4,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [0])

    def test_selecting_hand_does_not_discard_scholar_ace_on_last_hand(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 5,
                "round": 14,
                "score": 7714,
                "blind": {"chips": 16500},
                "hand": [
                    {"value": {"rank": "A", "suit": "C"}},
                    {"value": {"rank": "8", "suit": "S"}},
                    {"value": {"rank": "8", "suit": "C"}},
                    {"value": {"rank": "6", "suit": "C"}},
                    {"value": {"rank": "6", "suit": "D"}},
                    {"value": {"rank": "5", "suit": "C"}},
                    {"value": {"rank": "3", "suit": "D"}},
                    {"value": {"rank": "2", "suit": "S"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                        {"key": "j_scholar", "label": "Scholar"},
                        {"key": "j_photograph", "label": "Photograph"},
                    ]
                },
                "hands": 1,
                "discards": 4,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [0])

    def test_selecting_hand_discards_low_trash_in_photograph_pressure_spot(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 5,
                "round": 14,
                "score": 4704,
                "blind": {"chips": 16500},
                "hand": [
                    {"value": {"rank": "K", "suit": "S"}},
                    {"value": {"rank": "Q", "suit": "S"}},
                    {"value": {"rank": "8", "suit": "S"}},
                    {"value": {"rank": "8", "suit": "C"}},
                    {"value": {"rank": "6", "suit": "C"}},
                    {"value": {"rank": "5", "suit": "C"}},
                    {"value": {"rank": "3", "suit": "D"}},
                    {"value": {"rank": "2", "suit": "S"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                        {"key": "j_scholar", "label": "Scholar"},
                        {"key": "j_photograph", "label": "Photograph"},
                    ]
                },
                "hands": 3,
                "discards": 4,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "discard")
        self.assertEqual(action.params["cards"], [4, 5, 6, 7])

    def test_selecting_hand_prefers_four_of_a_kind_over_single_face_high_card(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 5,
                "round": 13,
                "score": 3550,
                "blind": {"chips": 11000},
                "hand": [
                    {"value": {"rank": "K", "suit": "D"}},
                    {"value": {"rank": "Q", "suit": "H"}},
                    {"value": {"rank": "J", "suit": "D"}},
                    {"value": {"rank": "T", "suit": "D"}},
                    {"value": {"rank": "9", "suit": "S"}},
                    {"value": {"rank": "9", "suit": "H"}},
                    {"value": {"rank": "9", "suit": "C"}},
                    {"value": {"rank": "9", "suit": "D"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                        {"key": "j_scholar", "label": "Scholar"},
                        {"key": "j_photograph", "label": "Photograph"},
                    ]
                },
                "hands": 3,
                "discards": 0,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        hand_label = HandAgent()._classify_play(state.hand, action.params["cards"])
        # Half Joker奖励≤3张牌，three_kind有时比four_kind更好
        self.assertIn(hand_label, {"straight", "four_kind", "three_kind"})

    def test_selecting_hand_avoids_full_house_tunnel_with_half_joker_on_wall(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 4,
                "blind": {"name": "The Wall", "chips": 20000},
                "current_round": {"score": 15247, "hands_left": 1, "discards_left": 0},
                "jokers": {
                    "cards": [
                        {"key": "j_sly", "label": "Sly Joker"},
                        {"key": "j_scary_face", "label": "Scary Face"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_supernova", "label": "Supernova"},
                        {"key": "j_popcorn", "label": "Popcorn"},
                    ],
                    "limit": 5,
                },
                "hand": [
                    {"value": {"rank": "T", "suit": "H"}},
                    {"value": {"rank": "T", "suit": "D"}},
                    {"value": {"rank": "4", "suit": "S"}},
                    {"value": {"rank": "3", "suit": "H"}},
                    {"value": {"rank": "3", "suit": "C"}},
                    {"value": {"rank": "3", "suit": "D"}},
                    {"value": {"rank": "2", "suit": "H"}},
                    {"value": {"rank": "2", "suit": "D"}},
                ],
                "hands": {
                    "Pair": {"chips": 30, "mult": 3, "level": 2},
                    "Three of a Kind": {"chips": 30, "mult": 3, "level": 1},
                    "Full House": {"chips": 40, "mult": 4, "level": 1},
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertLessEqual(len(action.params["cards"]), 3)

    def test_selecting_hand_prefers_full_house_over_single_high_card_on_last_hand(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 5,
                "round": 14,
                "score": 12958,
                "blind": {"chips": 16500},
                "hand": [
                    {"value": {"rank": "K", "suit": "S"}},
                    {"value": {"rank": "J", "suit": "D"}},
                    {"value": {"rank": "9", "suit": "S"}},
                    {"value": {"rank": "8", "suit": "S"}},
                    {"value": {"rank": "8", "suit": "C"}},
                    {"value": {"rank": "8", "suit": "D"}},
                    {"value": {"rank": "6", "suit": "H"}},
                    {"value": {"rank": "6", "suit": "D"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                        {"key": "j_scholar", "label": "Scholar"},
                        {"key": "j_photograph", "label": "Photograph"},
                    ]
                },
                "hands": 1,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        hand_label = HandAgent()._classify_play(state.hand, action.params["cards"])
        self.assertIn(hand_label, {"three_kind", "full_house"})

    def test_selecting_hand_keeps_scholar_ace_when_three_pairs_need_upgrade(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 5,
                "round": 15,
                "score": 0,
                "blind": {"chips": 22000},
                "hand": [
                    {"value": {"rank": "A", "suit": "C"}},
                    {"value": {"rank": "J", "suit": "H"}},
                    {"value": {"rank": "J", "suit": "C"}},
                    {"value": {"rank": "6", "suit": "S"}},
                    {"value": {"rank": "6", "suit": "H"}},
                    {"value": {"rank": "4", "suit": "S"}},
                    {"value": {"rank": "4", "suit": "C"}},
                    {"value": {"rank": "2", "suit": "C"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                        {"key": "j_scholar", "label": "Scholar"},
                        {"key": "j_photograph", "label": "Photograph"},
                    ]
                },
                "hands": 4,
                "discards": 4,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "discard")
        self.assertEqual(action.params["cards"], [7])

    def test_selecting_hand_prefers_single_face_over_face_pair_with_photograph(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 5,
                "round": 15,
                "score": 0,
                "blind": {"chips": 22000},
                "hand": [
                    {"value": {"rank": "J", "suit": "H"}},
                    {"value": {"rank": "J", "suit": "C"}},
                    {"value": {"rank": "7", "suit": "D"}},
                    {"value": {"rank": "6", "suit": "S"}},
                    {"value": {"rank": "6", "suit": "H"}},
                    {"value": {"rank": "4", "suit": "S"}},
                    {"value": {"rank": "4", "suit": "C"}},
                    {"value": {"rank": "3", "suit": "S"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                        {"key": "j_scholar", "label": "Scholar"},
                        {"key": "j_photograph", "label": "Photograph"},
                    ]
                },
                "hands": 4,
                "discards": 1,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [0])

    def test_selecting_hand_uses_last_discard_when_plain_two_pair_cannot_clear_blind(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 1,
                "round": 1,
                "score": 164,
                "blind": {"chips": 300},
                "hand": [
                    {"value": {"rank": "Q", "suit": "D"}},
                    {"value": {"rank": "J", "suit": "D"}},
                    {"value": {"rank": "8", "suit": "D"}},
                    {"value": {"rank": "7", "suit": "H"}},
                    {"value": {"rank": "7", "suit": "C"}},
                    {"value": {"rank": "4", "suit": "C"}},
                    {"value": {"rank": "2", "suit": "H"}},
                    {"value": {"rank": "2", "suit": "C"}},
                ],
                "hands": 1,
                "discards": 4,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "discard")
        self.assertEqual(action.params["cards"], [3, 4, 5, 6, 7])

    def test_selecting_hand_plays_made_pair_when_last_hand_is_close_with_jokers(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "ante": 5,
                "round": 13,
                "score": 10209,
                "blind": {"chips": 11000},
                "hand": [
                    {"value": {"rank": "A", "suit": "C"}},
                    {"value": {"rank": "A", "suit": "D"}},
                    {"value": {"rank": "K", "suit": "D"}},
                    {"value": {"rank": "J", "suit": "C"}},
                    {"value": {"rank": "T", "suit": "H"}},
                    {"value": {"rank": "9", "suit": "S"}},
                    {"value": {"rank": "5", "suit": "C"}},
                    {"value": {"rank": "4", "suit": "S"}},
                ],
                "jokers": {
                    "cards": [
                        {"key": "j_joker", "label": "Joker"},
                        {"key": "j_ice_cream", "label": "Ice Cream"},
                        {"key": "j_madness", "label": "Madness"},
                        {"key": "j_smiley", "label": "Smiley Face"},
                    ]
                },
                "hands": 1,
                "discards": 1,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "play")
        self.assertEqual(action.params["cards"], [0, 1])

    def test_shop_prefers_affordable_joker_purchase(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 8,
                "shop": {
                    "cards": [
                        {"name": "Planet", "type": "Consumable", "cost": 3},
                        {"name": "Joker", "type": "Joker", "cost": 4},
                    ],
                    "packs": [{"name": "Arcana Pack", "cost": 4}],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "buy")
        self.assertEqual(action.params, {"card": 1})

    def test_shop_prefers_stronger_joker_over_cheaper_weak_joker(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 9,
                "shop": {
                    "cards": [
                        {"key": "j_blue_joker", "label": "Blue Joker", "type": "Joker", "cost": 5},
                        {
                            "key": "j_delayed_grat",
                            "label": "Delayed Gratification",
                            "type": "Joker",
                            "cost": 4,
                            "value": {"effect": "每把弃牌获得$2"},
                        },
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "buy")
        self.assertEqual(action.params, {"card": 0})

    def test_shop_skips_joker_purchase_when_slots_are_full(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 8,
                "jokers": {
                    "cards": [{"key": f"j_{index}"} for index in range(5)],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"name": "Walkie Talkie", "type": "Joker", "cost": 4},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "next_round")

    def test_shop_sells_weakest_joker_to_make_room_for_stronger_joker(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 8,
                "jokers": {
                    "cards": [
                        {"key": "j_gluttenous_joker", "label": "Gluttonous Joker"},
                        {"key": "j_delayed_grat", "label": "Delayed Gratification"},
                        {"key": "j_blue_joker", "label": "Blue Joker"},
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_walkie_talkie", "label": "Walkie Talkie"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {
                            "key": "j_cavendish",
                            "label": "Cavendish",
                            "type": "Joker",
                            "cost": 4,
                            "value": {"effect": "X3 Mult"},
                        },
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "sell")
        # 经济Joker动态估值后Delayed价值提升，应卖Gluttonous(index 0)而非Delayed
        self.assertEqual(action.params, {"joker": 0})

    def test_shop_sells_gluttonous_for_abstract_joker_when_slots_are_full(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 28,
                "jokers": {
                    "cards": [
                        {"key": "j_gluttenous_joker", "label": "Gluttonous Joker"},
                        {"key": "j_blue_joker", "label": "Blue Joker"},
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_walkie_talkie", "label": "Walkie Talkie"},
                        {"key": "j_half", "label": "Half Joker"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_abstract", "label": "Abstract Joker", "type": "Joker", "cost": 7},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "sell")
        self.assertEqual(action.params, {"joker": 0})

    def test_shop_does_not_sell_gluttonous_for_ancient_joker_when_slots_are_full(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 30,
                "jokers": {
                    "cards": [
                        {"key": "j_gluttenous_joker", "label": "Gluttonous Joker"},
                        {"key": "j_blue_joker", "label": "Blue Joker"},
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_walkie_talkie", "label": "Walkie Talkie"},
                        {"key": "j_half", "label": "Half Joker"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_ancient", "label": "Ancient Joker", "type": "Joker", "cost": 8},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertNotEqual(action.method, "sell")

    def test_shop_sells_walkie_for_scholar_in_pair_build_when_slots_are_full(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 4,
                "money": 31,
                "jokers": {
                    "cards": [
                        {"key": "j_blue_joker", "label": "Blue Joker"},
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_walkie_talkie", "label": "Walkie Talkie"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_scholar", "label": "Scholar", "type": "Joker", "cost": 6},
                        {"key": "c_earth", "name": "Earth", "set": "PLANET", "type": "Planet", "cost": 3},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "sell")
        self.assertEqual(action.params, {"joker": 2})

    def test_shop_sells_walkie_for_photograph_with_hanging_chad_when_slots_are_full(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 5,
                "money": 30,
                "jokers": {
                    "cards": [
                        {"key": "j_blue_joker", "label": "Blue Joker"},
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_walkie_talkie", "label": "Walkie Talkie"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_todo_list", "label": "To Do List", "type": "Joker", "cost": 4},
                        {"key": "j_photograph", "label": "Photograph", "type": "Joker", "cost": 5},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "sell")
        self.assertEqual(action.params, {"joker": 2})

    def test_shop_skips_credit_card_when_it_would_only_fill_a_slot(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 4,
                "jokers": {
                    "cards": [
                        {"key": "j_lusty_joker", "label": "Lusty Joker"},
                        {"key": "j_supernova", "label": "Supernova"},
                        {"key": "j_joker", "label": "Joker"},
                        {"key": "j_mad", "label": "Mad Joker"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_credit_card", "label": "Credit Card", "type": "Joker", "cost": 1},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "next_round")

    def test_shop_prefers_direct_scoring_joker_over_red_card_without_pack_plan(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 1,
                "money": 9,
                "jokers": {"cards": [], "limit": 5},
                "shop": {
                    "cards": [
                        {
                            "key": "j_red_card",
                            "label": "Red Card",
                            "type": "Joker",
                            "cost": 5,
                            "value": {"effect": "+3 Mult when any Booster Pack is skipped"},
                        },
                        {"key": "j_sly", "label": "Sly Joker", "type": "Joker", "cost": 3},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "buy")
        self.assertEqual(action.params, {"card": 1})

    def test_shop_does_not_buy_rocket_over_planet_or_saving_cash(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 1,
                "money": 6,
                "jokers": {
                    "cards": [
                        {"key": "j_red_card", "label": "Red Card"},
                        {"key": "j_sly", "label": "Sly Joker"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "c_uranus", "label": "Uranus", "set": "PLANET", "cost": 3},
                        {"key": "j_rocket", "label": "Rocket", "type": "Joker", "cost": 6},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertNotEqual(action.params, {"card": 1})

    def test_shop_sells_credit_card_for_ice_cream_when_slots_are_full(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 2,
                "money": 5,
                "jokers": {
                    "cards": [
                        {"key": "j_lusty_joker", "label": "Lusty Joker"},
                        {"key": "j_supernova", "label": "Supernova"},
                        {"key": "j_joker", "label": "Joker"},
                        {"key": "j_mad", "label": "Mad Joker"},
                        {"key": "j_credit_card", "label": "Credit Card"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_ice_cream", "label": "Ice Cream", "type": "Joker", "cost": 5},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "sell")
        self.assertEqual(action.params, {"joker": 4})

    def test_shop_prefers_gros_michel_over_smiley_face(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 12,
                "jokers": {
                    "cards": [
                        {"key": "j_joker", "label": "Joker"},
                        {"key": "j_ice_cream", "label": "Ice Cream"},
                        {"key": "j_madness", "label": "Madness"},
                        {"key": "j_banner", "label": "Banner"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_smiley", "label": "Smiley Face", "type": "Joker", "cost": 5},
                        {"key": "j_gros_michel", "label": "Gros Michel", "type": "Joker", "cost": 5},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "buy")
        self.assertEqual(action.params, {"card": 1})

    def test_shop_keeps_banner_over_smiley_face_when_slots_are_full(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 5,
                "money": 29,
                "discards": 4,
                "jokers": {
                    "cards": [
                        {"key": "j_joker", "label": "Joker", "value": {"effect": "+4倍率"}},
                        {"key": "j_ice_cream", "label": "Ice Cream"},
                        {"key": "j_madness", "label": "Madness", "value": {"effect": "X倍率，每回合摧毁一张小丑牌"}},
                        {"key": "j_banner", "label": "Banner", "value": {"effect": "每次剩余弃牌获得筹码"}},
                        {"key": "j_gros_michel", "label": "Gros Michel", "value": {"effect": "+15倍率"}},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_smiley", "label": "Smiley Face", "type": "Joker", "cost": 5, "value": {"effect": "人头牌给予倍率"}},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertNotEqual(action.method, "sell")

    def test_shop_sells_plain_joker_for_late_banner_when_slots_are_full(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 4,
                "money": 26,
                "discards": 4,
                "jokers": {
                    "cards": [
                        {"key": "j_supernova", "label": "Supernova", "value": {"effect": "+倍率"}},
                        {"key": "j_joker", "label": "Joker", "value": {"effect": "+4倍率"}},
                        {"key": "j_mad", "label": "Mad Joker", "value": {"effect": "两对给予倍率"}},
                        {"key": "j_ice_cream", "label": "Ice Cream"},
                        {"key": "j_raised_fist", "label": "Raised Fist", "value": {"effect": "最低牌给予倍率"}},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_banner", "label": "Banner", "type": "Joker", "cost": 5},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "sell")
        self.assertEqual(action.params, {"joker": 1})

    def test_shop_sells_plain_joker_for_late_gros_michel_when_slots_are_full(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 5,
                "money": 26,
                "jokers": {
                    "cards": [
                        {"key": "j_supernova", "label": "Supernova", "value": {"effect": "+倍率"}},
                        {"key": "j_joker", "label": "Joker", "value": {"effect": "+4倍率"}},
                        {"key": "j_mad", "label": "Mad Joker", "value": {"effect": "两对给予倍率"}},
                        {"key": "j_ice_cream", "label": "Ice Cream"},
                        {"key": "j_raised_fist", "label": "Raised Fist", "value": {"effect": "最低牌给予倍率"}},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_gros_michel", "label": "Gros Michel", "type": "Joker", "cost": 5},
                        {"key": "j_smiley", "label": "Smiley Face", "type": "Joker", "cost": 5},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "sell")
        self.assertEqual(action.params, {"joker": 1})

    def test_shop_uses_planet_consumable_before_leaving(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 0,
                "consumables": {
                    "cards": [
                        {"key": "c_earth", "set": "PLANET", "name": "Earth"},
                    ],
                    "limit": 2,
                },
                "shop": {"cards": []},
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "use")
        self.assertEqual(action.params, {"consumable": 0})

    def test_selecting_hand_uses_lovers_on_highest_priority_card(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "7", "suit": "H"}},
                    {"value": {"rank": "A", "suit": "C"}},
                    {"value": {"rank": "9", "suit": "H"}},
                    {"value": {"rank": "K", "suit": "S"}},
                ],
                "consumables": {
                    "cards": [
                        {"key": "c_lovers", "set": "TAROT", "name": "The Lovers"},
                    ],
                    "limit": 2,
                },
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "use")
        self.assertEqual(action.params, {"consumable": 0, "cards": [1]})

    def test_selecting_hand_uses_empress_on_two_high_cards(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "7", "suit": "H"}},
                    {"value": {"rank": "A", "suit": "C"}},
                    {"value": {"rank": "9", "suit": "H"}},
                    {"value": {"rank": "K", "suit": "S"}},
                ],
                "consumables": {
                    "cards": [
                        {"key": "c_empress", "set": "TAROT", "name": "The Empress"},
                    ],
                    "limit": 2,
                },
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "use")
        self.assertEqual(action.params, {"consumable": 0, "cards": [1, 3]})

    def test_selecting_hand_uses_magician_on_two_high_cards(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "7", "suit": "H"}},
                    {"value": {"rank": "A", "suit": "C"}},
                    {"value": {"rank": "9", "suit": "H"}},
                    {"value": {"rank": "K", "suit": "S"}},
                ],
                "consumables": {
                    "cards": [
                        {"key": "c_magician", "set": "TAROT", "name": "The Magician"},
                    ],
                    "limit": 2,
                },
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "use")
        self.assertEqual(action.params, {"consumable": 0, "cards": [1, 3]})

    def test_selecting_hand_uses_tarot_before_medium_strength_two_pair(self):
        state = GameState(
            {
                "state": "SELECTING_HAND",
                "hand": [
                    {"value": {"rank": "A", "suit": "C"}},
                    {"value": {"rank": "A", "suit": "D"}},
                    {"value": {"rank": "K", "suit": "S"}},
                    {"value": {"rank": "K", "suit": "H"}},
                    {"value": {"rank": "5", "suit": "C"}},
                ],
                "consumables": {
                    "cards": [
                        {"key": "c_empress", "set": "TAROT", "name": "The Empress"},
                    ],
                    "limit": 2,
                },
                "hands": 4,
                "discards": 3,
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "use")
        self.assertEqual(action.params, {"consumable": 0, "cards": [0, 1]})

    def test_shop_prefers_reroll_when_flush_with_cash_in_late_ante(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 4,
                "money": 99,
                "jokers": {
                    "cards": [{"key": f"j_{index}"} for index in range(5)],
                    "limit": 5,
                },
                "shop": {"cards": []},
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "reroll")

    def test_shop_prefers_next_round_when_jokers_are_full_and_cash_is_not_high(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 5,
                "money": 15,
                "jokers": {
                    "cards": [{"key": f"j_{index}"} for index in range(5)],
                    "limit": 5,
                },
                "shop": {"cards": []},
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "next_round")

    def test_shop_can_reroll_past_weak_shop_when_jokers_are_full_but_cash_is_still_good(self):
        # 动态现金储备下 ante 4 需要更高现金才能触发重掷
        state = GameState(
            {
                "state": "SHOP",
                "ante": 4,
                "money": 40,
                "jokers": {
                    "cards": [{"key": f"j_{index}"} for index in range(5)],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"name": "The Lovers", "set": "TAROT", "cost": 3},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "reroll")

    def test_shop_rerolls_agent2_weak_full_jokers_with_sufficient_cash(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 3,
                "money": 35,
                "discards": 4,
                "jokers": {
                    "cards": [
                        {"key": "j_clever", "label": "Clever Joker"},
                        {"key": "j_mystic_summit", "label": "Mystic Summit"},
                        {"key": "j_sly", "label": "Sly Joker"},
                        {"key": "j_droll", "label": "Droll Joker"},
                        {"key": "j_zany", "label": "Zany Joker"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_scary_face", "label": "Scary Face", "type": "Joker", "cost": 4},
                        {"key": "j_splash", "label": "Splash", "type": "Joker", "cost": 3},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "reroll")

    def test_shop_does_not_reroll_agent2_weak_full_jokers_with_fifteen_cash(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 3,
                "money": 15,
                "discards": 4,
                "jokers": {
                    "cards": [
                        {"key": "j_clever", "label": "Clever Joker"},
                        {"key": "j_mystic_summit", "label": "Mystic Summit"},
                        {"key": "j_sly", "label": "Sly Joker"},
                        {"key": "j_droll", "label": "Droll Joker"},
                        {"key": "j_zany", "label": "Zany Joker"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_scary_face", "label": "Scary Face", "type": "Joker", "cost": 4},
                        {"key": "j_splash", "label": "Splash", "type": "Joker", "cost": 3},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "next_round")

    def test_shop_preserves_scary_juggler_timing_in_late_ante_three(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 3,
                "round": 8,
                "money": 25,
                "discards": 4,
                "jokers": {
                    "cards": [
                        {"key": "j_hack", "label": "Hack"},
                        {"key": "j_misprint", "label": "Misprint"},
                        {"key": "j_sly", "label": "Sly Joker"},
                        {"key": "j_juggler", "label": "Juggler"},
                        {"key": "j_scary_face", "label": "Scary Face"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "c_fool", "label": "The Fool", "set": "TAROT", "cost": 4},
                        {"key": "j_midas_mask", "label": "Midas Mask", "type": "Joker", "cost": 7},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        # 消耗品购买增强后应购买The Fool塔罗牌
        self.assertEqual(action.method, "buy")
        self.assertEqual(action.params, {"card": 0})

    def test_shop_preserves_completed_small_hand_build_before_popcorn_window(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 4,
                "round": 9,
                "money": 29,
                "discards": 4,
                "jokers": {
                    "cards": [
                        {"key": "j_sly", "label": "Sly Joker"},
                        {"key": "j_juggler", "label": "Juggler"},
                        {"key": "j_scary_face", "label": "Scary Face"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_supernova", "label": "Supernova"},
                    ],
                    "limit": 5,
                },
                "shop": {"cards": []},
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "next_round")

    def test_shop_skips_off_plan_planet_after_small_hand_build_is_complete(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 4,
                "round": 11,
                "money": 32,
                "discards": 4,
                "jokers": {
                    "cards": [
                        {"key": "j_sly", "label": "Sly Joker"},
                        {"key": "j_scary_face", "label": "Scary Face"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_supernova", "label": "Supernova"},
                        {"key": "j_popcorn", "label": "Popcorn"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "c_saturn", "label": "Saturn", "set": "PLANET", "cost": 3},
                        {"key": "j_hologram", "label": "Hologram", "type": "Joker", "cost": 7},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "next_round")

    def test_shop_tests_hanging_chad_over_supernova_in_small_hand_build(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 4,
                "round": 10,
                "money": 24,
                "discards": 4,
                "jokers": {
                    "cards": [
                        {"key": "j_sly", "label": "Sly Joker"},
                        {"key": "j_scary_face", "label": "Scary Face"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_supernova", "label": "Supernova"},
                        {"key": "j_popcorn", "label": "Popcorn"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "c_hermit", "label": "The Hermit", "set": "TAROT", "cost": 3},
                        {"key": "j_hanging_chad", "label": "Hanging Chad", "type": "Joker", "cost": 4},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "sell")
        self.assertEqual(action.params["joker"], 3)

    def test_shop_replaces_popcorn_with_abstract_in_chad_small_hand_build(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 5,
                "round": 13,
                "money": 29,
                "jokers": {
                    "cards": [
                        {"key": "j_sly", "label": "Sly Joker"},
                        {"key": "j_scary_face", "label": "Scary Face"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_popcorn", "label": "Popcorn"},
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_8_ball", "label": "8 Ball", "type": "Joker", "cost": 5},
                        {"key": "j_abstract", "label": "Abstract Joker", "type": "Joker", "cost": 4},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "sell")
        self.assertEqual(action.params["joker"], 3)

    def test_shop_keeps_sly_in_chad_small_hand_build_over_scholar(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 5,
                "round": 14,
                "money": 36,
                "jokers": {
                    "cards": [
                        {"key": "j_sly", "label": "Sly Joker"},
                        {"key": "j_scary_face", "label": "Scary Face"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_popcorn", "label": "Popcorn"},
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "c_jupiter", "label": "Jupiter", "set": "PLANET", "cost": 3},
                        {"key": "j_scholar", "label": "Scholar", "type": "Joker", "cost": 4},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertNotEqual(action.method, "sell")

    def test_shop_keeps_scary_face_in_abstract_chad_build_over_scholar(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 5,
                "round": 13,
                "money": 35,
                "jokers": {
                    "cards": [
                        {"key": "j_sly", "label": "Sly Joker"},
                        {"key": "j_scary_face", "label": "Scary Face"},
                        {"key": "j_half", "label": "Half Joker"},
                        {"key": "j_hanging_chad", "label": "Hanging Chad"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "c_jupiter", "label": "Jupiter", "set": "PLANET", "cost": 3},
                        {"key": "j_scholar", "label": "Scholar", "type": "Joker", "cost": 4},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertNotEqual(action.method, "sell")

    def test_shop_prefers_misprint_over_third_chip_joker_in_agent2_shape(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 2,
                "money": 8,
                "discards": 4,
                "jokers": {
                    "cards": [
                        {"key": "j_clever", "label": "Clever Joker"},
                        {"key": "j_hack", "label": "Hack"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_misprint", "label": "Misprint", "type": "Joker", "cost": 4},
                        {
                            "key": "j_mystic_summit",
                            "label": "Mystic Summit",
                            "type": "Joker",
                            "cost": 5,
                            "value": {"effect": "+15 Mult when 0 discards remaining"},
                        },
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "buy")
        self.assertEqual(action.params["card"], 0)

    def test_shop_prefers_sly_over_business_card_in_agent2_shape(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 2,
                "money": 13,
                "discards": 4,
                "jokers": {
                    "cards": [
                        {"key": "j_clever", "label": "Clever Joker"},
                        {"key": "j_hack", "label": "Hack"},
                        {"key": "j_misprint", "label": "Misprint"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_business", "label": "Business Card", "type": "Joker", "cost": 4},
                        {"key": "j_sly", "label": "Sly Joker", "type": "Joker", "cost": 4},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "buy")
        self.assertEqual(action.params["card"], 1)

    def test_shop_rearranges_jokers_chip_mult_xmult_order_before_next_round(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 0,
                "jokers": {
                    "cards": [
                        {"key": "j_card_sharp", "label": "Card Sharp"},
                        {"key": "j_blue_joker", "label": "Blue Joker"},
                        {"key": "j_abstract", "label": "Abstract Joker"},
                    ],
                    "limit": 5,
                },
                "shop": {"cards": []},
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "rearrange")
        self.assertEqual(action.params, {"jokers": [1, 2, 0]})

    def test_shop_skips_third_narrow_droll_in_agent2_shape(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 2,
                "money": 15,
                "discards": 4,
                "jokers": {
                    "cards": [
                        {"key": "j_clever", "label": "Clever Joker"},
                        {"key": "j_hack", "label": "Hack"},
                        {"key": "j_misprint", "label": "Misprint"},
                        {"key": "j_sly", "label": "Sly Joker"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_droll", "label": "Droll Joker", "type": "Joker", "cost": 4},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "next_round")

    def test_shop_keeps_sly_when_scary_face_build_needs_pair_chips(self):
        state = GameState(
            {
                "state": "SHOP",
                "ante": 4,
                "money": 27,
                "jokers": {
                    "cards": [
                        {"key": "j_misprint", "label": "Misprint"},
                        {"key": "j_sly", "label": "Sly Joker"},
                        {"key": "j_droll", "label": "Droll Joker"},
                        {"key": "j_scary_face", "label": "Scary Face"},
                        {"key": "j_popcorn", "label": "Popcorn"},
                    ],
                    "limit": 5,
                },
                "shop": {
                    "cards": [
                        {"key": "j_half", "label": "Half Joker", "type": "Joker", "cost": 5},
                        {"key": "j_supernova", "label": "Supernova", "type": "Joker", "cost": 5},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "sell")
        self.assertNotEqual(action.params["joker"], 1)

    def test_shop_skips_tarot_purchase_when_consumable_slots_are_full(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 8,
                "consumables": {
                    "cards": [
                        {"key": "c_lovers", "set": "TAROT"},
                        {"key": "c_empress", "set": "TAROT"},
                    ],
                    "limit": 2,
                },
                "shop": {
                    "cards": [
                        {"name": "The Hermit", "set": "TAROT", "cost": 3},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "next_round")

    def test_shop_skips_unsupported_tarot_purchase(self):
        state = GameState(
            {
                "state": "SHOP",
                "money": 24,
                "shop": {
                    "cards": [
                        {"name": "The Hermit", "set": "TAROT", "cost": 3},
                    ],
                },
            }
        )
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        # 不应购买不支持的塔罗牌，可以重掷寻找有用道具
        self.assertNotEqual(action.method, "buy")

    def test_shop_falls_back_to_next_round_when_nothing_valid(self):
        state = GameState({"state": "SHOP", "money": 0, "shop": {"cards": []}})
        orchestrator = DefaultOrchestrator(Genome.default())

        action = orchestrator.decide(state)

        self.assertEqual(action.method, "next_round")


if __name__ == "__main__":
    unittest.main()
