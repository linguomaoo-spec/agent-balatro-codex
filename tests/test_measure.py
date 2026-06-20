"""measure.py 单元测试：分布聚合、effect-size gate、可检测阈值。

理论修改，不启动 BalatroBot。覆盖：
- 跨目录聚合同 seed 分数分布
- 样本不足时保守拒绝（insufficient_samples）
- 显著退化拒绝、噪声内拒绝、显著改进接受
- 可检测阈值 = 3σ
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from balatro_agent.measure import (
    SeedDistribution,
    aggregate_seed_distributions,
    detectable_threshold,
    distribution_gate,
    measure_report,
)


def _write_eval(dir_path: Path, seed_scores: dict):
    """写一个最小 eval 目录：每 seed 一份 JSONL，含终局 final_score。"""
    dir_path.mkdir(parents=True, exist_ok=True)
    for seed, score in seed_scores.items():
        records = [
            {
                "state": {"phase": "SELECTING_HAND", "ante": 1, "score": 0,
                           "required_score": 300, "money": 4, "jokers": 0},
                "action": {"method": "play", "params": {}, "score": 1.0,
                            "agent": "hand"},
                "executed": "play",
                "terminal": False,
            },
            {
                "state": {"phase": "GAME_OVER", "ante": 6, "score": score,
                           "required_score": 30000, "money": 1, "jokers": 5,
                           "won": False},
                "action": {"method": "gamestate", "params": {}, "score": 0.0,
                            "agent": "fallback"},
                "executed": "gamestate",
                "terminal": True,
            },
        ]
        with (dir_path / f"{seed}.jsonl").open("w") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")


class TestAggregate(unittest.TestCase):
    def test_aggregates_across_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _write_eval(tmp / "run1", {"AGENT1": 27950, "AGENT2": 17804})
            _write_eval(tmp / "run2", {"AGENT1": 20606, "AGENT2": 17804})
            _write_eval(tmp / "run3", {"AGENT1": 25000, "AGENT2": 13225})
            dist = aggregate_seed_distributions([tmp / "run1", tmp / "run2", tmp / "run3"])
            self.assertEqual(dist["AGENT1"].n, 3)
            self.assertEqual(dist["AGENT1"].samples, [27950, 20606, 25000])
            self.assertAlmostEqual(dist["AGENT1"].mean, (27950 + 20606 + 25000) / 3)
            self.assertGreater(dist["AGENT1"].stdev, 0)
            self.assertEqual(dist["AGENT2"].samples, [17804, 17804, 13225])

    def test_skips_missing_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _write_eval(tmp / "run1", {"AGENT1": 100})
            dist = aggregate_seed_distributions([tmp / "run1", tmp / "nonexistent"])
            self.assertIn("AGENT1", dist)


class TestDistributionGate(unittest.TestCase):
    def _dist(self, samples):
        d = SeedDistribution(seed="S")
        d.samples = list(samples)
        return d

    def test_insufficient_samples_rejected(self):
        # baseline n=1 无法估计噪声 → 保守拒绝
        baseline = {"AGENT1": self._dist([27950])}
        candidate = {"AGENT1": self._dist([30000])}
        result = distribution_gate(baseline, candidate)
        self.assertFalse(result.promote)
        self.assertTrue(any("insufficient" in f for f in result.failed_checks))

    def test_within_noise_rejected(self):
        # baseline σ 大，候选均值差在噪声内（effect < 2σ）→ 拒绝
        baseline = {"AGENT1": self._dist([27950, 20606, 25000])}  # mean≈24519, σ≈3679
        candidate = {"AGENT1": self._dist([26000])}  # Δ≈1481, effect≈0.4 < 2 → within noise
        result = distribution_gate(baseline, candidate)
        self.assertFalse(result.promote)
        self.assertTrue(any("within_noise" in f for f in result.failed_checks))

    def test_significant_improvement_accepted(self):
        # 候选均值远超 baseline（>2σ）→ 接受
        baseline = {"AGENT1": self._dist([20000, 21000, 19000])}  # mean=20000, σ=1000
        candidate = {"AGENT1": self._dist([50000])}  # Δ=30000, effect=30
        result = distribution_gate(baseline, candidate)
        self.assertTrue(result.promote)
        self.assertEqual(result.per_seed["AGENT1"]["verdict"], "improved")

    def test_regression_rejected(self):
        baseline = {"AGENT1": self._dist([50000, 51000, 49000])}  # σ=1000
        candidate = {"AGENT1": self._dist([10000])}  # Δ=-40000, effect=-40
        result = distribution_gate(baseline, candidate)
        self.assertFalse(result.promote)
        self.assertTrue(any("regression" in f for f in result.failed_checks))

    def test_missing_seed_rejected(self):
        baseline = {"AGENT1": self._dist([1, 2, 3])}
        candidate = {"AGENT2": self._dist([100])}
        result = distribution_gate(baseline, candidate)
        self.assertFalse(result.promote)


class TestDetectableThreshold(unittest.TestCase):
    def _dist(self, samples):
        d = SeedDistribution(seed="S")
        d.samples = list(samples)
        return d

    def test_threshold_is_3sigma(self):
        d = self._dist([20000, 21000, 19000])  # σ=1000
        self.assertEqual(detectable_threshold(d, 3.0), 3000)

    def test_threshold_floored_at_1(self):
        d = SeedDistribution(seed="S")  # σ=0
        self.assertEqual(detectable_threshold(d, 3.0), 1)


class TestMeasureReport(unittest.TestCase):
    def test_report_includes_thresholds(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _write_eval(tmp / "r1", {"AGENT1": 20000, "AGENT1b": 0})
            _write_eval(tmp / "r2", {"AGENT1": 26000, "AGENT1b": 0})
            report = measure_report([tmp / "r1", tmp / "r2"])
            self.assertIn("AGENT1", report["seeds"])
            self.assertIn("detectable_threshold_3sigma", report["seeds"]["AGENT1"])


if __name__ == "__main__":
    unittest.main()
