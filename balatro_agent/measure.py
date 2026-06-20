"""测量工具：量化评估噪声，建立基于分布的晋升判断。

这是阶段 0 的核心。诊断显示：单次 live eval 的单 seed 分数波动
（memory.md 记录 AGENT1 同代码同 Joker 波动 7344 分）远大于版本间改动幅度，
导致 promotion gate 在 n=1 下基本是随机触发，进化呈现锯齿。

本模块：
- ``aggregate_seed_distributions``：跨多个 eval 目录聚合"同一 commit、同一
  seed"的终局分数分布（均值/标准差/min/max），用以量化噪声。
- ``distribution_gate``：把单次符号比较升级为分布比较——候选必须在 effect
  size（均值差 / 噪声标准差）超过阈值时才视为真实改进，避免把噪声当进步。

设计取舍：
- 不假设能跑 live。``aggregate_seed_distributions`` 直接消费 ``runs/eval/``
  目录下已有的 JSONL（多次运行的同一 seed），由人工或脚本重复运行产生。
- 若历史样本不足以估计分布（n < 2），gate 退化为保守拒绝并标注
  ``insufficient_samples``——宁可误拒噪声，不可误晋升。
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from balatro_agent.analysis import summarize_jsonl_logs


@dataclass
class SeedDistribution:
    seed: str
    samples: List[int] = field(default_factory=list)  # 每次运行的 final_score

    @property
    def n(self) -> int:
        return len(self.samples)

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    @property
    def stdev(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        return statistics.stdev(self.samples)

    @property
    def min(self) -> int:
        return min(self.samples) if self.samples else 0

    @property
    def max(self) -> int:
        return max(self.samples) if self.samples else 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "n": self.n,
            "mean": self.mean,
            "stdev": self.stdev,
            "min": self.min,
            "max": self.max,
            "samples": list(self.samples),
        }


def _seed_from_path(path: str) -> str:
    """从 JSONL 路径提取 seed（文件名去掉 .jsonl）。"""
    return Path(path).stem


def aggregate_seed_distributions(eval_dirs: Sequence[Path]) -> Dict[str, SeedDistribution]:
    """跨多个 eval 目录聚合同一 seed 的终局分数分布。

    每个 eval 目录是一次完整 cohort 运行（如 dev 的 AGENT1/2/3）。
    把多次运行的同一 seed 终局分数聚合，用以估计噪声。
    """
    dist: Dict[str, SeedDistribution] = {}
    for d in eval_dirs:
        d = Path(d)
        if not d.exists():
            continue
        summary = summarize_jsonl_logs(d)
        for run in summary.get("runs") or []:
            seed = _seed_from_path(str(run.get("path") or ""))
            if not seed:
                continue
            score = int(run.get("final_score") or 0)
            dist.setdefault(seed, SeedDistribution(seed=seed)).samples.append(score)
    return dist


@dataclass
class DistributionGateResult:
    promote: bool
    failed_checks: List[str] = field(default_factory=list)
    per_seed: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    method: str = "effect_size"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "promote": self.promote,
            "failed_checks": self.failed_checks,
            "per_seed": self.per_seed,
            "method": self.method,
        }


def distribution_gate(
    baseline: Dict[str, SeedDistribution],
    candidate: Dict[str, SeedDistribution],
    effect_threshold: float = 2.0,
    min_samples: int = 2,
) -> DistributionGateResult:
    """基于分布的晋升判断。

    要求：候选每个 seed 相对 baseline 的均值差 / 合并噪声标准差 >=
    ``effect_threshold``（默认 2σ，即改动幅度显著大于噪声）才判为真实改进；
    任一 seed 的 ante/分数**显著退化**则拒绝。

    若样本不足（n < min_samples），保守拒绝并标注 ``insufficient_samples``，
    因为无法区分信号与噪声——这是阶段 0 的核心约束。

    candidate 通常为单次运行（n=1）；此时 effect size 仍可计算（用 baseline
    的噪声 σ），只有均值差足够大才晋升。
    """
    failures: List[str] = []
    per_seed: Dict[str, Dict[str, Any]] = {}
    seeds = sorted(set(baseline) | set(candidate))

    if not seeds:
        return DistributionGateResult(promote=False, failed_checks=["no_seeds"])

    for seed in seeds:
        b = baseline.get(seed)
        c = candidate.get(seed)
        entry: Dict[str, Any] = {}
        if b is None or c is None:
            failures.append(f"{seed}:missing_distribution")
            per_seed[seed] = {"baseline": None, "candidate": None}
            continue

        entry["baseline_mean"] = b.mean
        entry["baseline_stdev"] = b.stdev
        entry["candidate_mean"] = c.mean
        entry["candidate_n"] = c.n

        # 样本不足时无法判断噪声，保守拒绝
        if b.n < min_samples:
            failures.append(f"{seed}:insufficient_baseline_samples")
            entry["verdict"] = "insufficient_baseline_samples"
            per_seed[seed] = entry
            continue

        # 合并噪声：取 baseline σ（候选多为单次，无法估自身 σ）
        sigma = b.stdev if b.stdev > 0 else 1.0
        mean_delta = c.mean - b.mean
        effect = mean_delta / sigma
        entry["mean_delta"] = mean_delta
        entry["effect_size"] = effect
        entry["threshold"] = effect_threshold

        # 显著退化（负效应超过阈值）→ 拒绝
        if effect <= -effect_threshold:
            failures.append(f"{seed}:significant_regression")
            entry["verdict"] = "regression"
        elif effect >= effect_threshold:
            entry["verdict"] = "improved"
        else:
            # 在噪声范围内：既不判改进也不判退化，但因无显著改进 → 拒绝晋升
            failures.append(f"{seed}:within_noise")
            entry["verdict"] = "within_noise"
        per_seed[seed] = entry

    promote = not failures
    return DistributionGateResult(
        promote=promote, failed_checks=failures, per_seed=per_seed
    )


def detectable_threshold(dist: SeedDistribution, k_sigma: float = 3.0) -> int:
    """返回给定分布下"可检测的改动阈值"：max(k_sigma × σ, 1)。

    用于在调参前预估：改动需产生多大分差才能从噪声中分辨。这是阶段 0
    的关键产出——告诉用户"AGENT3 的 132 分缺口是真信号还是运气"。
    """
    return max(1, int(math.ceil(k_sigma * dist.stdev)))


def measure_report(eval_dirs: Sequence[Path]) -> Dict[str, Any]:
    """生成可读的噪声测量报告。"""
    dist = aggregate_seed_distributions(eval_dirs)
    seeds: Dict[str, Any] = {}
    for seed, d in dist.items():
        seeds[seed] = {
            **d.as_dict(),
            "detectable_threshold_3sigma": detectable_threshold(d, 3.0),
        }
    return {
        "eval_dirs": [str(p) for p in eval_dirs],
        "seed_count": len(dist),
        "seeds": seeds,
    }
