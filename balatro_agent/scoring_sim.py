"""廉价单手得分模拟器（scoring_sim）。

这是诊断 2026-06-20 进化锯齿问题后新增的核心能力。现有 hand.py 中的
``_score_play`` / ``_estimated_plain_score`` 是**排序启发式代理**，不是
Balatro 真实计分公式；因此商店决策无法回答"这张牌能把清掉剩余 ante 的
概率提高多少"，所有失败都卡在"缺 ×Mult"上。

本模块用标准 Balatro 计分公式实现纯 Python 单手得分模拟：

    final = (base_chips + card_chips + joker_added_chips)
          * (base_mult + joker_added_mult)
          * prod(joker_xmult)
          * held_steel_multiplier

设计取舍（见 research/memory.md 与 2026-06-20 运行诊断）：

- 只模拟**单手得分**，不模拟商店抽牌随机性。瓶颈是"我的牌组能不能打够
  分"，单手模拟已足以回答"该买哪张牌"和"该打哪一手"。
- 卡牌与 Joker 用标准化数据结构表示（``SimCard`` / ``SimJoker``），既能
  从 GameState 的完整 raw 状态解析，也能从 JSONL 摘要的 ``hand_cards``
  身份串（如 ``"S_A"``）重建，从而可在历史日志上回算验证。
- 不依赖 BalatroBot、不联网、纯函数、毫秒级，可在模拟器层跑成千上万次
  评估（阶段 3 进化算法的廉价适应度）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from balatro_agent.model import (
    GameState,
    card_enhancement,
    card_rank_value,
    card_suit,
)


# 标准牌型基础分（chips, mult），与 Balatro 官方一致。
HAND_BASE: Dict[str, Tuple[int, int]] = {
    "straight_flush": (100, 8),
    "four_kind": (60, 7),
    "full_house": (40, 4),
    "flush": (35, 4),
    "straight": (30, 4),
    "three_kind": (30, 3),
    "two_pair": (20, 2),
    "pair": (10, 2),
    "high_card": (5, 1),
}

# 每升一级 planet 增加的 (chips, mult)。近似官方曲线，用于缺口估算。
HAND_LEVEL_STEP: Dict[str, Tuple[int, int]] = {
    "straight_flush": (40, 3),
    "four_kind": (30, 3),
    "full_house": (25, 2),
    "flush": (15, 2),
    "straight": (15, 2),
    "three_kind": (20, 2),
    "two_pair": (15, 1),
    "pair": (5, 1),
    "high_card": (5, 1),
}

# Planet → 目标牌型（与 booster/consumable 的 _HAND_TYPE_TO_PLANET 对齐）。
PLANET_TO_HAND: Dict[str, str] = {
    "mercury": "pair",
    "uranus": "two_pair",
    "saturn": "straight",  # 注意：three_kind 的 planet 也叫 saturn，这里取 straight
    "jupiter": "flush",
    "mars": "full_house",
    "neptune": "straight_flush",
    "pluto": "high_card",
    "earth": "three_kind",
    "venus": "flush",
    "ceres": "straight",
}

# 点数 → 筹码值（Balatro 标准卡牌筹码）。
def rank_chip(rank_value: int) -> int:
    if rank_value == 14:
        return 11
    if rank_value >= 10:
        return 10
    return max(0, rank_value)


@dataclass
class SimCard:
    """标准化卡牌。identity 如 "S_A"。"""

    suit: str
    rank_value: int
    enhancement: str = ""

    @property
    def identity(self) -> str:
        rank = {11: "J", 12: "Q", 13: "K", 14: "A"}.get(self.rank_value)
        if rank is None:
            rank = str(self.rank_value)
        return f"{self.suit}_{rank}"

    @property
    def chip(self) -> int:
        """打出该牌时贡献的筹码。"""
        base = rank_chip(self.rank_value)
        if self.enhancement == "BONUS":
            return base + 30
        return base

    @property
    def mult_bonus(self) -> float:
        """打出该牌时贡献的加法倍率。"""
        if self.enhancement == "MULT":
            return 4.0
        if self.enhancement == "GLASS":
            return 0.0  # glass 不加 mult，靠触发
        return 0.0

    @property
    def is_face(self) -> bool:
        return self.rank_value in (11, 12, 13)

    @property
    def is_even(self) -> bool:
        return self.rank_value in (2, 4, 6, 8, 10)

    @property
    def is_odd(self) -> bool:
        return self.rank_value in (3, 5, 7, 9, 14)


@dataclass
class SimJoker:
    """标准化 Joker。key 如 "j_half"。

    模拟器只覆盖与"单手得分"相关的触发模型；非计分 Joker（经济类）记为
    neutral（无得分贡献），由 economy agent 评分处理，不在此处伪造倍率。
    """

    key: str
    multiplier: float = 1.0  # scaling joker 的累计倍率（如 campfire 烧数）

    def contributes_score(self) -> bool:
        return self.key not in _NEUTRAL_JOKERS


# 经济/辅助类 Joker：不在单手计分中产生 chips/mult，模拟器忽略。
_NEUTRAL_JOKERS = {
    "j_delayed_grat",
    "j_credit_card",
    "j_rocket",
    "j_to_the_moon",
    "j_golden_joker",
    "j_cloud_9",
    "j_business",
    "j_business_card",
    "j_faceless",
    "j_hallucination",
    "j_red_card",
    "j_banner",  # banner 依赖剩余弃牌，按状态动态算，不静态计入
    "j_egg",
    "j_matador",
    "j_mail_in_rebate",
    "j_to_a_million",
}


@dataclass
class ScoreBreakdown:
    hand_label: str
    chips: float
    mult: float
    xmult: float
    score: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "hand_label": self.hand_label,
            "chips": self.chips,
            "mult": self.mult,
            "xmult": self.xmult,
            "score": self.score,
        }


def parse_identity(identity: str) -> SimCard:
    """从 "S_A"/"H_10"/"C_K" 身份串重建 SimCard（无 enhancement）。"""
    text = str(identity).strip().upper()
    if "_" in text:
        suit_part, rank_part = text.split("_", 1)
    else:
        # 回退：末尾字符作花色
        suit_part = text[-1] if text else ""
        rank_part = text[:-1]
    rank_map = {"A": 14, "K": 13, "Q": 12, "J": 11, "T": 10}
    rank_value = rank_map.get(rank_part)
    if rank_value is None:
        try:
            rank_value = int(rank_part)
        except (TypeError, ValueError):
            rank_value = 0
    suit = suit_part if suit_part in ("H", "D", "C", "S") else ""
    return SimCard(suit=suit, rank_value=rank_value)


def _identity_from_card(raw: Any) -> str:
    """从 BalatroBot 卡牌字典或身份串提取 identity。

    BalatroBot 完整卡牌优先用 key/suit+rank；JSONL 摘要或测试 fixture
    可能给 {'value': 'S_A'} 或裸 "S_A" 串，此时回退到 value/identity 字段。
    """
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        key = str(raw.get("key") or "")
        if key:
            # c_xxx 是消耗品，卡牌 key 形如 "S_A" 或 "H_A"
            if "_" in key and key[0] in "HDCS":
                return key
        identity = raw.get("identity") or raw.get("value") or raw.get("label") or raw.get("id")
        if identity and isinstance(identity, str):
            return identity
    return ""


def parse_card(raw: Dict[str, Any]) -> SimCard:
    """从 BalatroBot 完整卡牌字典解析 SimCard。"""
    suit = card_suit(raw)
    rank_value = card_rank_value(raw)
    enhancement = card_enhancement(raw)
    # 若 suit 无效或 rank 未解析（身份串形式 {'value':'S_A'}），回退到 identity
    if suit not in ("H", "D", "C", "S") or rank_value <= 0:
        identity = _identity_from_card(raw)
        if identity:
            sim = parse_identity(identity)
            sim.enhancement = enhancement
            return sim
    return SimCard(suit=suit, rank_value=rank_value, enhancement=enhancement)


def parse_jokers(state: GameState) -> List[SimJoker]:
    """从 GameState 的 jokers 列表解析 SimJoker 列表。"""
    out: List[SimJoker] = []
    for raw in state.jokers:
        key = str(raw.get("key") or raw.get("id") or "").lower()
        multiplier = 1.0
        # campfire 等可读取累计倍率（若上游提供 extra）
        extra = raw.get("extra") if isinstance(raw, dict) else None
        if isinstance(extra, dict) and isinstance(extra.get("mult"), (int, float)):
            if key == "j_campfire":
                multiplier = max(1.0, float(extra["mult"]))
        out.append(SimJoker(key=key, multiplier=multiplier))
    return out


def parse_hand(state: GameState) -> List[SimCard]:
    """从 GameState 解析手牌。优先完整 raw，回退摘要身份串。

    支持三种形式：完整卡牌字典、{'value':'S_A'} 摘要字典、裸身份串。
    """
    raw_hand = state.hand
    if raw_hand:
        first = raw_hand[0]
        if isinstance(first, dict) and ("suit" in first or "key" in first):
            return [parse_card(c) for c in raw_hand]
        if isinstance(first, dict):
            # {'value': 'S_A'} 形式：尝试 parse_card 回退到 identity
            parsed = [parse_card(c) for c in raw_hand]
            if all(c.rank_value > 0 for c in parsed):
                return parsed
    # 摘要路径：summary.hand_cards 是身份串列表
    summary = state.raw.get("hand_cards") if isinstance(state.raw, dict) else None
    if isinstance(summary, list):
        return [parse_identity(str(c)) for c in summary]
    # 退化：raw hand 本身就是身份串
    return [parse_identity(str(c)) for c in raw_hand]


def hand_levels(state: GameState) -> Dict[str, int]:
    """从 GameState 解析各牌型等级（planet level）。"""
    hands = state.raw.get("hands") if isinstance(state.raw, dict) else None
    if not isinstance(hands, dict):
        return {}
    levels: Dict[str, int] = {}
    name_to_key = {
        "Straight Flush": "straight_flush",
        "Four of a Kind": "four_kind",
        "Full House": "full_house",
        "Flush": "flush",
        "Straight": "straight",
        "Three of a Kind": "three_kind",
        "Two Pair": "two_pair",
        "Pair": "pair",
        "High Card": "high_card",
    }
    for name, key in name_to_key.items():
        entry = hands.get(name)
        if isinstance(entry, dict):
            level = entry.get("level", 1)
            try:
                levels[key] = int(level)
            except (TypeError, ValueError):
                levels[key] = 1
    return levels


def classify(cards: Sequence[SimCard], allow_kickers: bool = False) -> str:
    """复刻 hand._classify_play 的牌型判定（对 SimCard）。"""
    if not cards or any(c.rank_value <= 0 for c in cards):
        return "invalid"
    rank_groups: Dict[int, int] = {}
    rank_values: List[int] = []
    for c in cards:
        rank_groups[c.rank_value] = rank_groups.get(c.rank_value, 0) + 1
        rank_values.append(c.rank_value)
    counts = sorted(rank_groups.values(), reverse=True)
    is_flush = len(cards) == 5 and len({c.suit for c in cards if c.suit}) == 1
    is_straight = len(cards) == 5 and _is_straight(rank_values)
    if is_flush and is_straight:
        return "straight_flush"
    if counts == [4] or (allow_kickers and len(cards) == 5 and counts[:1] == [4]):
        return "four_kind"
    if counts == [3, 2]:
        return "full_house"
    if is_flush:
        return "flush"
    if is_straight:
        return "straight"
    if counts == [3] or (allow_kickers and len(cards) == 5 and counts[:1] == [3]):
        return "three_kind"
    if counts == [2, 2] or (allow_kickers and len(cards) == 5 and counts[:2] == [2, 2]):
        return "two_pair"
    if counts == [2] or (allow_kickers and len(cards) == 5 and counts[:1] == [2]):
        return "pair"
    if len(cards) == 1:
        return "high_card"
    if allow_kickers and len(cards) == 5:
        return "high_card"
    return "invalid"


def _is_straight(rank_values: Sequence[int]) -> bool:
    values = sorted(set(rank_values))
    if len(values) != 5:
        return False
    if values[-1] - values[0] == 4:
        return True
    # A-2-3-4-5 wheel
    return values == [2, 3, 4, 5, 14]


def _held_steel_multiplier(hand: Sequence[SimCard], played_indices: Iterable[int]) -> float:
    played = set(played_indices)
    held_steel = sum(
        1
        for i, c in enumerate(hand)
        if i not in played and c.enhancement == "STEEL"
    )
    return 1.5 ** held_steel


def _joker_added_chips_mult(
    jokers: Sequence[SimJoker],
    played: Sequence[SimCard],
    hand_label: str,
    deck_remaining: int = 0,
) -> Tuple[float, float, float]:
    """返回 (added_chips, added_mult, xmult_product)。

    只建模常见计分 Joker 的单手触发。未覆盖的 Joker 记为 neutral。
    这是**有意的近似**：模拟器用于缺口估算与边际比较，不追求像素级复刻，
    覆盖率随需扩展（见 research/memory.md 工作假设）。

    deck_remaining 用于 blue_joker（每张剩余牌库 +2 chips）。
    hanging_chad 会重触发最左侧打出牌一次：该牌的 chips 与其触发的
    joker 加成翻倍。本函数对 first-card 相关触发按 ×2 计算。
    """
    added_chips = 0.0
    added_mult = 0.0
    xmult = 1.0
    keys = {j.key for j in jokers}
    first = played[0] if played else None
    played_ranks = [c.rank_value for c in played]
    # hanging_chad 重触发最左侧打出牌：首牌相关加成翻倍
    retrigger = 2 if "j_hanging_chad" in keys else 1

    # 加法 chips
    if "j_scholar" in keys:
        ace_count = sum(1 for r in played_ranks if r == 14)
        added_chips += 20.0 * ace_count
    if "j_walkie_talkie" in keys:
        added_chips += 15.0 * sum(1 for r in played_ranks if r in (10, 4))
    if "j_blue_joker" in keys:
        # 每张剩余牌库 +2 chips
        added_chips += 2.0 * max(0, deck_remaining)
    if "j_castle" in keys:
        added_chips += 20.0  # 近似
    if "j_banner" in keys:
        added_mult += 0.0  # 动态：调用方应传入剩余弃牌修正，此处保守 0
    if "j_square" in keys and hand_label == "pair":
        added_mult += 4.0
    if "j_stone" in keys:
        added_chips += 25.0

    # 加法 mult
    if "j_half" in keys and 1 <= len(played) <= 3:
        added_mult += 20.0 * retrigger
    if "j_sly" in keys and hand_label in ("pair", "two_pair"):
        added_mult += 8.0
    if "j_jolly" in keys and hand_label == "pair":
        added_mult += 8.0
    if "j_droll" in keys and hand_label == "flush":
        added_mult += 10.0
    if "j_gros_michel" in keys:
        added_mult += 15.0
    if "j_clever" in keys and hand_label == "two_pair":
        added_mult += 8.0
    if "j_wily" in keys and hand_label == "three_kind":
        added_mult += 10.0
    if "j_zany" in keys and hand_label == "three_kind":
        added_mult += 12.0
    if "j_mad" in keys and hand_label == "two_pair":
        added_mult += 10.0
    if "j_ride_the_bus" in keys:
        # 近似：假设触发
        added_mult += 8.0
    if "j_green_joker" in keys:
        added_mult += 6.0
    if "j_trousers" in keys and hand_label == "two_pair":
        added_mult += 12.0
    if "j_red_card" in keys:
        added_mult += 3.0  # 近似
    if "j_ice_cream" in keys:
        added_mult += 50.0  # 起始，衰减由调用方修正
    if "j_smiley" in keys:
        added_mult += 5.0 * sum(1 for c in played if c.is_face)
    if "j_scary_face" in keys:
        added_mult += 4.0 * sum(1 for c in played if c.is_face)
    if "j_scholar" in keys:
        for r in played_ranks:
            if r == 14:
                added_mult += 4.0 * retrigger if r == played_ranks[0] else 4.0
    if "j_photograph" in keys and first is not None and first.is_face:
        added_mult += 8.0 * retrigger
    if "j_hanging_chad" in keys and first is not None:
        # 首牌重触发：joker 加成已在 retrigger 中翻倍；此处补 chip 重复
        added_chips += first.chip  # 首牌筹码再计一次
    if "j_rough_gem" in keys:
        added_chips += 0.0  # 经济，忽略
    if "j_arrow_head" in keys:
        added_chips += 50.0 * sum(1 for c in played if c.suit == "C")
    if "j_onyx" in keys:
        added_chips += 50.0 * sum(1 for c in played if c.suit == "S")
    if "j_gluttenous_joker" in keys:
        added_mult += 3.0 * sum(1 for c in played if c.suit == "C")
    if "j_lusty_joker" in keys:
        xmult *= 1.5 ** sum(1 for c in played if c.suit == "H")
    if "j_greedy_joker" in keys:
        xmult *= 1.5 ** sum(1 for c in played if c.suit == "D")
    if "j_wrathful_joker" in keys:
        xmult *= 1.5 ** sum(1 for c in played if c.suit == "S")
    if "j_ancient" in keys:
        xmult *= 1.5 ** sum(1 for c in played if c.suit == "H")  # 近似
    if "j_even_steven" in keys and all(c.is_even for c in played):
        added_mult += 4.0
    if "j_odd_todd" in keys and all(c.is_odd for c in played):
        added_mult += 5.0
    if "j_runner" in keys and hand_label == "straight":
        added_mult += 15.0
    if "j_supernova" in keys:
        added_mult += 3.0  # 近似累计
    if "j_card_sharp" in keys:
        xmult *= 3.0  # 近似：假设重打同牌型
    if "j_abstract" in keys:
        added_mult += 3.0
    if "j_mime" in keys:
        # 近似：复制 retrigger，对已有 mult 翻倍效应简化为 +50%
        added_mult *= 1.5

    # scaling xmult
    if "j_campfire" in keys:
        for j in jokers:
            if j.key == "j_campfire":
                xmult *= max(1.0, 1.0 + 0.5 * j.multiplier)
    if "j_steel_joker" in keys:
        for j in jokers:
            if j.key == "j_steel_joker":
                xmult *= max(1.0, 1.0 + 0.2 * j.multiplier)

    # 静态 xmult jokers
    if "j_joker" in keys:
        added_mult += 4.0
    if "j_loyalty_card" in keys:
        xmult *= 4.0  # 近似周期触发
    if "j_8_ball" in keys:
        pass  # 经济/概率，忽略
    if "j_magic_trick" in keys:
        pass

    return added_chips, added_mult, xmult


def score_play(
    hand: Sequence[SimCard],
    played_indices: Sequence[int],
    jokers: Sequence[SimJoker] = (),
    levels: Optional[Dict[str, int]] = None,
    allow_kickers: bool = False,
    deck_remaining: int = 0,
) -> ScoreBreakdown:
    """对给定手牌与打出索引计算单手得分。

    levels: 牌型 → planet 等级。缺失视为 1。
    deck_remaining: 剩余牌库数，用于 blue_joker 等。
    """
    levels = levels or {}
    played = [hand[i] for i in played_indices]
    hand_label = classify(played, allow_kickers=allow_kickers)
    if hand_label == "invalid":
        return ScoreBreakdown("invalid", 0.0, 0.0, 1.0, 0)

    base_chips, base_mult = HAND_BASE[hand_label]
    level = max(1, int(levels.get(hand_label, 1)))
    step_chips, step_mult = HAND_LEVEL_STEP.get(hand_label, (5, 1))
    base_chips += step_chips * (level - 1)
    base_mult += step_mult * (level - 1)

    card_chips = sum(c.chip for c in played)
    card_mult = sum(c.mult_bonus for c in played)

    added_chips, added_mult, xmult = _joker_added_chips_mult(
        jokers, played, hand_label, deck_remaining=deck_remaining
    )

    total_chips = base_chips + card_chips + added_chips
    total_mult = base_mult + card_mult + added_mult
    steel_mult = _held_steel_multiplier(hand, played_indices)

    final = max(0.0, total_chips) * max(0.0, total_mult) * xmult * steel_mult
    return ScoreBreakdown(
        hand_label=hand_label,
        chips=total_chips,
        mult=total_mult,
        xmult=xmult * steel_mult,
        score=int(round(final)),
    )


def best_play(
    hand: Sequence[SimCard],
    jokers: Sequence[SimJoker] = (),
    levels: Optional[Dict[str, int]] = None,
    require_five: bool = False,
    deck_remaining: int = 0,
) -> Tuple[List[int], ScoreBreakdown]:
    """在手牌中枚举选出最佳打出组合（最高得分）。"""
    from itertools import combinations

    levels = levels or {}
    best_indices: List[int] = []
    best_bd = ScoreBreakdown("high_card", 0.0, 0.0, 1.0, 0)
    n = len(hand)
    if n == 0:
        return best_indices, best_bd
    max_size = min(5, n)
    sizes = [5] if require_five else range(1, max_size + 1)
    for size in sizes:
        for combo in combinations(range(n), size):
            indices = list(combo)
            bd = score_play(
                hand, indices, jokers, levels,
                allow_kickers=require_five, deck_remaining=deck_remaining,
            )
            if bd.score > best_bd.score:
                best_bd = bd
                best_indices = indices
    if not best_indices:
        best_indices = [max(range(n), key=lambda i: hand[i].rank_value)]
        best_bd = score_play(hand, best_indices, jokers, levels, deck_remaining=deck_remaining)
    return best_indices, best_bd


# --- 盲注需求曲线与缺口 -------------------------------------------------

# 小丑牌标准盲注基础需求（Small Blind），乘以 ante 系数。
BLIND_BASE: Dict[str, int] = {
    "small": 1,
    "big": 1,
    "boss": 1,
}

# ante → 盲注需求倍率（官方曲线）。
ANTE_REQUIREMENT: Dict[int, int] = {
    1: 1,
    2: 2,
    3: 4,
    4: 6,
    5: 9,
    6: 12,
    7: 16,
    8: 22,
}

# 每 ante Small Blind 基础分（官方：300, 800, 2000, 5000, 11000, 20000, 35000, 50000）。
SMALL_BLIND_BASE: Dict[int, int] = {
    1: 300,
    2: 800,
    3: 2000,
    4: 5000,
    5: 11000,
    6: 20000,
    7: 35000,
    8: 50000,
}


def blind_requirement(ante: int, blind: str = "small") -> int:
    """估算给定 ante 与盲注类型的需求分。

    small = base, big = 1.5×, boss = 2×（近似，boss 有特殊效果但分值粗略）。
    """
    base = SMALL_BLIND_BASE.get(ante, max(300, 300 * (2 ** (ante - 1))))
    factor = {"small": 1.0, "big": 1.5, "boss": 2.0}.get(blind.lower(), 1.5)
    return int(round(base * factor))


@dataclass
class GapEstimate:
    """构筑相对剩余 ante 的得分缺口估算。"""

    expected_single_hand_score: int
    hands_per_round: int
    rounds_remaining_in_ante: int
    ante_required: int
    blind_required: int
    blind_gap: int  # 当前盲注缺口
    can_clear_blind: bool
    expected_per_ante: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "expected_single_hand_score": self.expected_single_hand_score,
            "hands_per_round": self.hands_per_round,
            "rounds_remaining_in_ante": self.rounds_remaining_in_ante,
            "ante_required": self.ante_required,
            "blind_required": self.blind_required,
            "blind_gap": self.blind_gap,
            "can_clear_blind": self.can_clear_blind,
            "expected_per_ante": self.expected_per_ante,
        }


def estimate_gap(
    state: GameState,
    hand: Optional[Sequence[SimCard]] = None,
    jokers: Optional[Sequence[SimJoker]] = None,
    levels: Optional[Dict[str, int]] = None,
) -> GapEstimate:
    """估算当前构筑相对盲注需求的缺口。

    hand/jokers/levels 缺失时从 state 解析。这是商店缺口评分的基础。
    """
    if hand is None:
        hand = parse_hand(state)
    if jokers is None:
        jokers = parse_jokers(state)
    if levels is None:
        levels = hand_levels(state)

    deck_remaining = state.deck_card_count
    _, bd = best_play(hand, jokers, levels, deck_remaining=deck_remaining)
    hands_per_round = max(1, state.hands_remaining) if state.hands_remaining > 0 else 4
    expected_single = bd.score
    expected_per_round = expected_single * hands_per_round

    blind_required = state.blind_requirement or blind_requirement(state.ante)
    current_score = state.score
    blind_gap = max(0, blind_required - current_score)
    can_clear = expected_per_round >= blind_gap or expected_per_round >= blind_required

    # 本 ante 剩余盲注数（粗略：当前盲注未过则算 1，外加后续盲注）
    return GapEstimate(
        expected_single_hand_score=expected_single,
        hands_per_round=hands_per_round,
        rounds_remaining_in_ante=1,
        ante_required=blind_required,
        blind_required=blind_required,
        blind_gap=blind_gap,
        can_clear_blind=can_clear,
        expected_per_ante=expected_per_round,
    )


def marginal_contribution(
    state: GameState,
    candidate_joker_key: str,
) -> int:
    """候选 Joker 装上后，模拟最佳单手得分的提升量（缺口驱动商店评分核心）。

    返回 (装上后得分 - 当前得分)。缺 ×Mult 时，×Mult 牌的提升应显著高于
    第 3 张 chip Joker——直接命中 2026-06-20 所有失败卡在"缺 ×Mult"的根因。
    """
    hand = parse_hand(state)
    jokers = parse_jokers(state)
    levels = hand_levels(state)
    deck_remaining = state.deck_card_count

    _, current_bd = best_play(hand, jokers, levels, deck_remaining=deck_remaining)
    candidate = SimJoker(key=candidate_joker_key)
    _, with_candidate_bd = best_play(
        hand, jokers + [candidate], levels, deck_remaining=deck_remaining
    )
    return with_candidate_bd.score - current_bd.score
