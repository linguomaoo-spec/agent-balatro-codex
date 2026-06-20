"""per-seed elite 档案与胜局先验（阶段 4）。

诊断结论（memory.md 第85行列为开放问题）：AGENT1 的 Delayed/Stencil/Campfire
胜局、AGENT2 的 ante 5 路线从未被吸收进默认策略——每个版本都从零开始手调。
真进化算法必须积累 elite：保存最佳 genome + 关键决策序列 + 最佳分数。

本模块：
- ``EliteRecord``：单个 seed 的 elite 档案（genome、最佳分数、关键决策序列）。
- ``EliteArchive``：跨 seed 的 elite 集合，持久化为 JSON。
- ``key_decisions_from_log``：从 JSONL 抽取"关键决策"（买/卖 Joker、跨 ante
  现金下限等），把胜局经验结构化。
- ``commitment_prior``：把 elite 的目标牌型先验暴露给 commitment 状态机。

设计取舍：elite 档案是研究记忆的机器可读形式，供人或 auto-evolve 复用；
它不直接驱动运行时（运行时仍由 genome + Python 启发式决定），但作为"已知
好路线"的锚点，防止策略漂移或胜局丢失。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from balatro_agent.model import Genome


@dataclass
class KeyDecision:
    """从胜局日志抽取的关键决策。"""

    step: int
    ante: int
    method: str  # buy / sell / play / discard / next_round
    summary: str
    joker_keys: List[str] = field(default_factory=list)
    money: int = 0
    params: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "ante": self.ante,
            "method": self.method,
            "summary": self.summary,
            "joker_keys": self.joker_keys,
            "money": self.money,
            "params": self.params,
        }


@dataclass
class EliteRecord:
    """单 seed 的 elite 档案。"""

    seed: str
    best_score: int = 0
    won: bool = False
    max_ante: int = 0
    genome_weights: Dict[str, float] = field(default_factory=dict)
    key_decisions: List[KeyDecision] = field(default_factory=list)
    target_hand_type: Optional[str] = None  # commitment 先验

    def as_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "best_score": self.best_score,
            "won": self.won,
            "max_ante": self.max_ante,
            "genome_weights": self.genome_weights,
            "key_decisions": [d.as_dict() for d in self.key_decisions],
            "target_hand_type": self.target_hand_type,
        }


class EliteArchive:
    """跨 seed elite 集合，持久化为 JSON。"""

    def __init__(self, records: Optional[Dict[str, EliteRecord]] = None) -> None:
        self.records: Dict[str, EliteRecord] = records or {}

    def update(self, record: EliteRecord) -> bool:
        """更新某 seed 的 elite，仅当新记录更优时接受。返回是否更新。"""
        existing = self.records.get(record.seed)
        if existing is None or _is_better(record, existing):
            self.records[record.seed] = record
            return True
        return False

    def get(self, seed: str) -> Optional[EliteRecord]:
        return self.records.get(seed)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {seed: r.as_dict() for seed, r in self.records.items()}
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    @classmethod
    def load(cls, path: Path) -> "EliteArchive":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        records: Dict[str, EliteRecord] = {}
        for seed, d in data.items():
            decisions = [KeyDecision(**kd) for kd in d.get("key_decisions") or []]
            records[seed] = EliteRecord(
                seed=seed,
                best_score=int(d.get("best_score") or 0),
                won=bool(d.get("won")),
                max_ante=int(d.get("max_ante") or 0),
                genome_weights=dict(d.get("genome_weights") or {}),
                key_decisions=decisions,
                target_hand_type=d.get("target_hand_type"),
            )
        return cls(records)

    def seeds(self) -> List[str]:
        return sorted(self.records)


def _is_better(candidate: EliteRecord, existing: EliteRecord) -> bool:
    """判断 candidate 是否优于 existing。胜局 > max_ante > best_score。"""
    if candidate.won and not existing.won:
        return True
    if not candidate.won and existing.won:
        return False
    if candidate.max_ante != existing.max_ante:
        return candidate.max_ante > existing.max_ante
    return candidate.best_score > existing.best_score


def key_decisions_from_log(log_path: Path, max_decisions: int = 30) -> List[KeyDecision]:
    """从 JSONL 抽取关键决策（买/卖 Joker、出牌）。

    胜局经验固化为结构化决策序列，供 replay 与 commitment 先验复用。
    """
    decisions: List[KeyDecision] = []
    with Path(log_path).open() as fh:
        for step, line in enumerate(fh):
            text = line.strip()
            if not text:
                continue
            try:
                record = json.loads(text)
            except json.JSONDecodeError:
                continue
            action = record.get("action") or {}
            state = record.get("state") or {}
            method = str(action.get("method") or "")
            if method not in ("buy", "sell", "play", "discard"):
                continue
            joker_keys = state.get("joker_keys") or []
            money = int(state.get("money") or 0)
            ante = int(state.get("ante") or 0)
            params = action.get("params") or {}
            summary = f"{method} @ ante {ante}"
            decisions.append(KeyDecision(
                step=step, ante=ante, method=method, summary=summary,
                joker_keys=list(joker_keys), money=money, params=dict(params),
            ))
            if len(decisions) >= max_decisions:
                break
    return decisions


def commitment_prior(archive: EliteArchive, seed: str) -> Optional[str]:
    """从 elite 档案提取目标牌型先验，供 commitment 状态机消费。

    若该 seed 的 elite 记录了 target_hand_type，返回之；否则 None。
    这让胜局路线的牌型专精方向能跨 run 复用，而非每轮从 Joker 信号推断。
    """
    record = archive.get(seed)
    if record is None:
        return None
    return record.target_hand_type


def build_elite_from_log(
    seed: str,
    log_path: Path,
    genome: Optional[Genome] = None,
    target_hand_type: Optional[str] = None,
) -> EliteRecord:
    """从一次运行日志构建 elite 记录。"""
    best_score = 0
    max_ante = 0
    won = False
    with Path(log_path).open() as fh:
        last_state: Dict[str, Any] = {}
        for line in fh:
            text = line.strip()
            if not text:
                continue
            try:
                record = json.loads(text)
            except json.JSONDecodeError:
                continue
            state = record.get("state") or {}
            ante = int(state.get("ante") or 0)
            if ante > max_ante:
                max_ante = ante
            if state.get("won") is True:
                won = True
            last_state = state
        best_score = int(last_state.get("score") or 0)
    return EliteRecord(
        seed=seed,
        best_score=best_score,
        won=won,
        max_ante=max_ante,
        genome_weights=dict(genome.weights) if genome else {},
        key_decisions=key_decisions_from_log(log_path),
        target_hand_type=target_hand_type,
    )
