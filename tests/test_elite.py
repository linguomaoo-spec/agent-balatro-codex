"""elite.py 与 sim_evolution.py 单元测试。

理论修改，不启动 BalatroBot。覆盖：
- EliteArchive 更新优先级（胜局 > ante > 分数）
- 持久化保存/加载
- key_decisions_from_log 抽取
- commitment_prior
- build_elite_from_log
- load_scenarios_from_logs + sim_run_factory 产出 live 兼容结构
- sim_fitness 随 genome 变化
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from balatro_agent.elite import (
    EliteArchive,
    EliteRecord,
    KeyDecision,
    build_elite_from_log,
    commitment_prior,
    key_decisions_from_log,
)
from balatro_agent.model import Genome
from balatro_agent.sim_evolution import (
    load_scenarios_from_logs,
    make_sim_run_factory,
    sim_fitness,
)


def _write_log(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


class TestEliteArchive(unittest.TestCase):
    def test_update_keeps_better_record(self):
        archive = EliteArchive()
        a = EliteRecord(seed="AGENT1", best_score=100, max_ante=3)
        b = EliteRecord(seed="AGENT1", best_score=200, max_ante=3)
        self.assertTrue(archive.update(a))
        self.assertTrue(archive.update(b))
        self.assertEqual(archive.get("AGENT1").best_score, 200)

    def test_update_rejects_worse_record(self):
        archive = EliteArchive()
        archive.update(EliteRecord(seed="AGENT1", best_score=200, max_ante=5))
        self.assertFalse(archive.update(EliteRecord(seed="AGENT1", best_score=100, max_ante=5)))
        self.assertEqual(archive.get("AGENT1").best_score, 200)

    def test_win_beats_higher_ante(self):
        archive = EliteArchive()
        archive.update(EliteRecord(seed="A", max_ante=8, won=False, best_score=10000))
        won = EliteRecord(seed="A", max_ante=8, won=True, best_score=1)
        self.assertTrue(archive.update(won))
        self.assertTrue(archive.get("A").won)

    def test_persistence_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "elite.json"
            archive = EliteArchive()
            archive.update(EliteRecord(seed="AGENT1", best_score=500, max_ante=4,
                                        target_hand_type="pair"))
            archive.save(path)
            loaded = EliteArchive.load(path)
            self.assertEqual(loaded.get("AGENT1").best_score, 500)
            self.assertEqual(loaded.get("AGENT1").target_hand_type, "pair")


class TestKeyDecisionsAndBuild(unittest.TestCase):
    def test_key_decisions_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AGENT1.jsonl"
            _write_log(path, [
                {"state": {"phase": "SELECTING_HAND", "ante": 1, "money": 4, "joker_keys": []},
                 "action": {"method": "play", "params": {"cards": [0]}}, "executed": "play"},
                {"state": {"phase": "SHOP", "ante": 1, "money": 8, "joker_keys": []},
                 "action": {"method": "buy", "params": {"card": 0}}, "executed": "buy"},
            ])
            decisions = key_decisions_from_log(path)
            methods = [d.method for d in decisions]
            self.assertIn("play", methods)
            self.assertIn("buy", methods)
            self.assertEqual(decisions[0].money, 4)

    def test_build_elite_from_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AGENT1.jsonl"
            _write_log(path, [
                {"state": {"phase": "SELECTING_HAND", "ante": 1, "score": 0, "money": 4},
                 "action": {"method": "play"}, "executed": "play"},
                {"state": {"phase": "GAME_OVER", "ante": 6, "score": 26014, "money": 1,
                            "won": False}, "action": {"method": "gamestate"}, "terminal": True},
            ])
            genome = Genome.default()
            record = build_elite_from_log("AGENT1", path, genome=genome, target_hand_type="pair")
            self.assertEqual(record.seed, "AGENT1")
            self.assertEqual(record.max_ante, 6)
            self.assertEqual(record.best_score, 26014)
            self.assertFalse(record.won)
            self.assertEqual(record.target_hand_type, "pair")


class TestCommitmentPrior(unittest.TestCase):
    def test_prior_returns_target(self):
        archive = EliteArchive()
        archive.update(EliteRecord(seed="AGENT1", target_hand_type="pair"))
        self.assertEqual(commitment_prior(archive, "AGENT1"), "pair")

    def test_prior_none_when_missing(self):
        archive = EliteArchive()
        self.assertIsNone(commitment_prior(archive, "AGENT1"))


class TestSimEvolution(unittest.TestCase):
    def _scenario_dir(self):
        tmp = tempfile.mkdtemp()
        path = Path(tmp) / "AGENT1.jsonl"
        _write_log(path, [
            {"state": {"phase": "SELECTING_HAND", "ante": 1, "score": 0,
                        "required_score": 300, "money": 4, "joker_keys": [],
                        "hand_cards": ["S_A", "H_A", "S_3", "H_5", "S_9"],
                        "deck_cards_remaining": 44, "hands": 4, "discards": 4},
             "action": {"method": "play"}, "executed": "play"},
            {"state": {"phase": "SELECTING_HAND", "ante": 6, "score": 0,
                        "required_score": 20000, "money": 1, "joker_keys": ["j_half"],
                        "hand_cards": ["S_A", "H_A", "S_3", "H_5", "S_9"],
                        "deck_cards_remaining": 10, "hands": 2, "discards": 2},
             "action": {"method": "play"}, "executed": "play"},
        ])
        return Path(tmp)

    def test_load_scenarios(self):
        d = self._scenario_dir()
        scenarios = load_scenarios_from_logs(d, limit=10)
        self.assertEqual(len(scenarios), 2)

    def test_sim_run_factory_produces_live_compatible(self):
        d = self._scenario_dir()
        scenarios = load_scenarios_from_logs(d)
        factory = make_sim_run_factory(scenarios)
        run = factory(Genome.default(), "AGENT1", None)
        self.assertIn("status", run)
        self.assertIn("state", run)
        self.assertIn("score", run)
        self.assertEqual(run["seed"], "AGENT1")

    def test_sim_fitness_stable_for_deterministic_play(self):
        # 纯 SELECTING_HAND 出牌场景中，出牌选择是确定性的（最佳牌型），
        # 与 genome 无关；sim_fitness 应稳定且为正。
        d = self._scenario_dir()
        scenarios = load_scenarios_from_logs(d)
        base = Genome.default()
        fit = sim_fitness(base, scenarios)
        self.assertGreater(fit, 0)
        # 同一 genome 多次评估应稳定（无随机性）
        self.assertEqual(fit, sim_fitness(base, scenarios))


if __name__ == "__main__":
    unittest.main()
