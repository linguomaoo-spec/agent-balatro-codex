"""模拟器层进化（阶段 3）。

诊断结论：``EvolutionEngine`` 依赖 live/checkpoint 运行工厂，单次评估昂贵且
噪声大（见 measure.py 量化），因此真实进化跑不起来，策略迭代退化为人手调参。

本模块提供**基于 scoring_sim 的廉价适应度**：在固定 scenario 库（从历史
JSONL 抽取的 SELECTING_HAND 状态）上评估 genome，让进化算法在模拟器层跑
成千上万代，live eval 降级为验证器。

- ``SimScenario``：一个评估场景（状态快照 + 标签）。
- ``make_sim_run_factory``：返回符合 RunFactory 签名的函数，用模拟器对
  scenario 库算期望单手得分，产出与 live 兼容的 run dict（含 final_score、
  state、status），使 EvolutionEngine.evolve 无需 BalatroBot 即可运行。
- ``load_scenarios_from_logs``：从历史 JSONL 抽取场景库。

设计取舍：模拟器适应度衡量"在给定局面下，genome 驱动的商店/手牌决策能否
产出更高单手得分"。它不替代 live，但作为快速过滤层，只有模拟器选出的
top-1 才进入 live 验证。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from balatro_agent.model import GameState, Genome
from balatro_agent.scoring_sim import (
    best_play,
    estimate_gap,
    hand_levels,
    parse_hand,
    parse_jokers,
)


RunFactory = Callable[[Genome, Optional[str], Optional[Path]], Dict[str, Any]]


@dataclass
class SimScenario:
    """一个评估场景：从某真实局面抽取的状态快照。"""

    label: str
    raw: Dict[str, Any]

    def state(self) -> GameState:
        return GameState(self.raw)


def load_scenarios_from_logs(
    log_dir: Path,
    phase: str = "SELECTING_HAND",
    limit: int = 50,
) -> List[SimScenario]:
    """从历史 JSONL 抽取场景库。

    日志记录的是 state.summary()，含 hand_cards/joker_keys/分数等。这些摘要
    状态足以驱动模拟器评估，从而把历史经验固化为可重复的适应度场景。
    """
    scenarios: List[SimScenario] = []
    for jsonl in sorted(Path(log_dir).glob("*.jsonl")):
        with jsonl.open() as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    record = json.loads(text)
                except json.JSONDecodeError:
                    continue
                state = record.get("state") or {}
                if str(state.get("phase") or "").upper() != phase:
                    continue
                scenarios.append(SimScenario(label=f"{jsonl.stem}:{len(scenarios)}", raw=dict(state)))
                if len(scenarios) >= limit:
                    return scenarios
    return scenarios


def _genome_affects_sim(genome: Genome, state: GameState) -> float:
    """评估 genome 在该场景下的决策质量。

    关键连接：genome 权重驱动 orchestrator 的 play/discard/buy 选择，
    模拟器评估**所选行动**的得分。因此 genome 变化能改变适应度——
    这让模拟器层进化成为真正的优化器（而非纯静态分数）。
    """
    from balatro_agent.orchestrator import DefaultOrchestrator
    from balatro_agent.scoring_sim import score_play

    try:
        decision = DefaultOrchestrator(genome).decide_with_details(state)
    except Exception:
        return _genome_affects_sim_static(genome, state)
    selected = decision.selected
    method = selected.method

    # 出牌：用模拟器评估所选牌的真实得分
    if method == "play":
        try:
            hand = parse_hand(state)
            jokers = parse_jokers(state)
            levels = hand_levels(state)
        except Exception:
            return 0.0
        cards = selected.params.get("cards") or selected.params.get("indices") or []
        if not hand or not cards:
            return 0.0
        bd = score_play(hand, list(cards), jokers, levels,
                        deck_remaining=state.deck_card_count)
        score = bd.score
        # 可清盲奖励
        blind = state.blind_requirement
        if blind and bd.score >= max(1, blind - state.score):
            score += blind
        return score

    # 弃牌：用 lookahead 雕塑潜力
    if method == "discard":
        from balatro_agent.lookahead import sculpt_potential
        params = selected.params.get("cards") or selected.params.get("indices") or []
        keep = [i for i in range(len(parse_hand(state))) if i not in params]
        return float(sculpt_potential(state, keep))

    # 商店/其他：用缺口可清性作为基线信号
    return _genome_affects_sim_static(genome, state)


def _genome_affects_sim_static(genome: Genome, state: GameState) -> float:
    """静态兜底：不经过决策，用缺口估算。"""
    try:
        gap = estimate_gap(state)
    except Exception:
        return 0.0
    score = gap.expected_single_hand_score
    if gap.can_clear_blind:
        score += gap.blind_required
    risk = genome.weight("risk", 1.0)
    value_hand = genome.weight("value_hand", 1.0)
    return score * (0.9 + 0.1 * min(2.0, risk)) * (0.9 + 0.1 * min(2.0, value_hand))


def make_sim_run_factory(
    scenarios: List[SimScenario],
) -> RunFactory:
    """返回基于 scenario 库的廉价评估工厂。

    对每个 scenario 调用模拟器评估 genome，聚合为与 live 兼容的 run dict。
    """

    def run_once(genome: Genome, seed: Optional[str], log_path: Optional[Path]) -> Dict[str, Any]:
        if not scenarios:
            return {
                "status": "infra_error",
                "steps": 0,
                "seed": seed,
                "error": {"type": "no_scenarios"},
            }
        scores: List[float] = []
        clears = 0
        last_state: Dict[str, Any] = {}
        for sc in scenarios:
            try:
                state = sc.state()
                gap = estimate_gap(state)
                scores.append(_genome_affects_sim(genome, state))
                if gap.can_clear_blind:
                    clears += 1
                last_state = state.summary()
            except Exception:
                scores.append(0.0)
        mean_score = sum(scores) / len(scores) if scores else 0.0
        # 产出 live 兼容结构：final_score 作为适应度信号，won 反映清盲比例
        won = clears > len(scenarios) / 2
        return {
            "status": "game_over_win" if won else "game_over_loss",
            "steps": len(scenarios),
            "seed": seed,
            "score": int(mean_score),
            "state": {**last_state, "score": int(mean_score),
                       "required_score": max(1, int(mean_score))},
            "sim_clears": clears,
            "sim_total": len(scenarios),
        }

    return run_once


def sim_fitness(genome: Genome, scenarios: List[SimScenario]) -> float:
    """单值适应度：genome 在场景库上的平均模拟得分。"""
    if not scenarios:
        return 0.0
    return sum(_genome_affects_sim(genome, sc.state()) for sc in scenarios) / len(scenarios)
