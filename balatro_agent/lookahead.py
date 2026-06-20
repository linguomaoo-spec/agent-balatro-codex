"""基于模拟器的廉价手牌前瞻（阶段 2）。

诊断显示：eval 时 checkpoint beam 太贵（每手 35–85s），所以 agent 实际是
纯贪心——每个 phase 取最高分提案，不模拟未来几手。这导致"渐进式牌型专精"
只能靠启发式硬编码，碰不上正确路径就卡死。

本模块用 scoring_sim 做廉价（毫秒级）的 1–2 手前瞻：

- ``lookahead_play_value``：对当前局面，模拟"打出最佳牌 → 抽补 → 再打一手"
  的期望得分，用来在 play vs discard 之间比较。
- ``should_discard_over_play``：当前最佳一手得分不足清盲且弃牌能雕塑出更高
  牌型时，返回建议弃牌的牌索引。

设计取舍：只模拟单手得分 + 牌型雕塑潜力，不模拟商店/抽牌概率分布（保持
毫秒级）。这是对 hand agent 贪心决策的**附加信号**，不替代 live beam。
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from balatro_agent.model import GameState
from balatro_agent.scoring_sim import (
    SimCard,
    SimJoker,
    best_play,
    parse_hand,
    parse_jokers,
    hand_levels,
    score_play,
)


def _deck_remaining(state: GameState) -> int:
    """剩余牌库数，兼容完整 deck cards 与摘要 deck_card_count 两种形式。"""
    raw = state.raw if isinstance(state.raw, dict) else {}
    count = raw.get("deck_card_count") or raw.get("deck_cards_remaining")
    if isinstance(count, (int, float)) and count > 0:
        return int(count)
    return state.deck_card_count


def _draw_unknown(deck_remaining: int) -> bool:
    """是否有牌可抽（用于雕塑弃牌后补牌的粗略假设）。"""
    return deck_remaining > 0


def lookahead_play_value(
    state: GameState,
    depth: int = 1,
) -> Tuple[int, List[int], str]:
    """返回 (未来 depth 手的期望累计得分, 最佳打出索引, 牌型)。

    depth=1：当前最佳单手得分。
    depth=2：当前最佳一手 + 假设抽补后下一手的同等期望（粗略，不枚举抽牌）。
    """
    hand = parse_hand(state)
    jokers = parse_jokers(state)
    levels = hand_levels(state)
    deck_remaining = _deck_remaining(state)

    idx, bd = best_play(hand, jokers, levels, deck_remaining=deck_remaining)
    value = bd.score
    if depth <= 1 or not _draw_unknown(deck_remaining):
        return value, idx, bd.hand_label

    # depth=2 粗略近似：下一手期望 ≈ 当前单手得分（不模拟具体抽牌）
    # 仅当当前得分不足以清盲时，多手累计才有意义
    blind = state.blind_requirement
    if blind and value < blind:
        value += bd.score  # 假设第二手同等产出
    return value, idx, bd.hand_label


def sculpt_potential(
    state: GameState,
    keep_indices: Sequence[int],
) -> int:
    """假设保留 keep_indices、丢弃其余并抽补，模拟所得最佳单手得分。

    用作弃牌雕塑的潜在收益估算。抽到的牌假设为"中性"（不计 joker 协同），
    因此这是保守下界，仅用于相对比较。
    """
    hand = parse_hand(state)
    if not hand or not keep_indices:
        return 0
    jokers = parse_jokers(state)
    levels = hand_levels(state)
    deck_remaining = _deck_remaining(state)
    # 保留的牌 + 抽补（用现有牌库中未出现的牌粗略填补，这里直接评估保留部分）
    kept = [hand[i] for i in keep_indices if i < len(hand)]
    if not kept:
        return 0
    # 评估保留牌能构成的最佳牌型（假设抽补能补足）
    idx, bd = best_play(kept, jokers, levels, deck_remaining=deck_remaining)
    return bd.score


def should_discard_over_play(
    state: GameState,
) -> Optional[Tuple[List[int], int, int, str]]:
    """判断当前是否应弃牌而非出牌。

    返回 (discard_indices, play_score, sculpt_score, reason) 或 None。

    条件：
    - 当前最佳一手得分不足以清盲（play_score < blind_gap）
    - 存在一组保留牌，雕塑后潜在得分显著高于当前（>= play_score × 1.3）
    - 还有弃牌次数
    """
    if state.discards_remaining <= 0:
        return None
    hand = parse_hand(state)
    if not hand:
        return None
    jokers = parse_jokers(state)
    levels = hand_levels(state)
    deck_remaining = _deck_remaining(state)

    play_idx, play_bd = best_play(hand, jokers, levels, deck_remaining=deck_remaining)
    play_score = play_bd.score

    blind = state.blind_requirement or 0
    current = state.score
    gap = max(0, blind - current)
    # 当前一手已足以清盲则不弃牌
    if gap > 0 and play_score >= gap:
        return None
    # 分数充裕（play_score 足够大）时不强行雕塑
    if play_score >= max(gap, blind) * 0.7 if (gap or blind) else play_score >= blind:
        pass

    # 枚举"保留一个对子/同花胚"的雕塑方案，取潜在最高
    from itertools import combinations

    best_keep: List[int] = []
    best_potential = play_score
    n = len(hand)
    for size in range(2, min(5, n) + 1):
        for combo in combinations(range(n), size):
            keep = list(combo)
            potential = sculpt_potential(state, keep)
            if potential > best_potential:
                best_potential = potential
                best_keep = keep

    if not best_keep or best_potential < play_score * 1.3:
        return None

    discard = [i for i in range(n) if i not in best_keep]
    if not discard:
        return None
    return (discard[:5], play_score, best_potential, "sculpt_higher_hand")
