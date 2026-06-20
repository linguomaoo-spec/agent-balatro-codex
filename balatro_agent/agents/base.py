from __future__ import annotations
from typing import Any, List, Optional
from balatro_agent.model import ActionProposal, GameState, Genome


class Agent:
    name = "agent"

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        raise NotImplementedError

    def propose_search(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        return self.propose(state, genome)

    def set_seed(self, seed: Optional[str]) -> None:
        """通知 agent 当前运行 seed，供 elite 先验等机制使用。

        默认实现为空；需要 seed 感知的 agent（如 HandAgent 读取胜局先验）
        覆盖此方法。
        """
        return None

    def set_elite_archive(self, archive: Optional[Any]) -> None:
        """注入可选的 per-seed elite 档案。"""
        return None
