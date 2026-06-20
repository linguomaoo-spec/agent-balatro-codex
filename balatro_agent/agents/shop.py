from __future__ import annotations
from typing import Dict, List, Optional, Set
from balatro_agent.actions import SHOP
from balatro_agent.agents.base import Agent
from balatro_agent.agents.consumable import ConsumableAgent
from balatro_agent.agents.tarot_targets import TARGETED_TAROT_COUNTS
from balatro_agent.model import (
    ActionProposal,
    GameState,
    Genome,
    card_enhancement,
    card_identity,
    card_rank_value,
    card_suit,
    item_cost,
    item_name,
    item_type,
)


class ShopAgent(Agent):
    name = "shop"
    _JOKER_REPLACEMENT_MARGIN = 15.0
    _NARROW_CONDITIONAL_JOKERS = {
        "j_clever",
        "j_sly",
        "j_droll",
        "j_zany",
        "j_wily",
        "j_mystic_summit",
        "j_hack",
    }

    # 渐进式牌型专精：Joker → 目标牌型信号（精简版，与HandAgent._JOKER_HAND_TYPE_SIGNAL一致）
    _JOKER_HAND_TYPE_SIGNAL = {
        "j_half": [("pair", 3.0), ("high_card", 2.5), ("three_kind", 2.0)],
        "j_sly": [("pair", 3.0), ("two_pair", 2.0)],
        "j_photograph": [("pair", 2.5), ("high_card", 2.5)],
        "j_hanging_chad": [("high_card", 3.0), ("pair", 2.0)],
        "j_scholar": [("pair", 2.5), ("high_card", 2.5)],
        "j_walkie_talkie": [("two_pair", 2.5), ("pair", 1.5)],
        "j_runner": [("straight", 3.5)],
        "j_superposition": [("straight", 2.5)],
        "j_lusty_joker": [("flush", 3.0)],
        "j_greedy_joker": [("flush", 3.0)],
        "j_wrathful_joker": [("flush", 3.0)],
        "j_gluttenous_joker": [("flush", 3.0)],
        "j_ancient": [("flush", 2.5)],
        "j_smeared": [("flush", 2.0)],
        "j_card_sharp": [("__repeat__", 4.0)],
        "j_supernova": [("__consistency__", 3.5)],
        "j_mad": [("two_pair", 2.0)],
        "j_ride_the_bus": [("two_pair", 2.0), ("straight", 1.5)],
        "j_even_steven": [("pair", 1.5)],
        "j_odd_todd": [("pair", 1.5)],
        "j_green_joker": [("pair", 1.5)],
        "j_trousers": [("two_pair", 3.0)],
        "j_square": [("pair", 1.5), ("high_card", 1.5)],
        "j_scary_face": [("pair", 1.5), ("high_card", 1.5)],
    }

    # 手牌类型 → 对应行星牌 key
    _HAND_TYPE_TO_PLANET = {
        "pair": "c_mercury",
        "two_pair": "c_uranus",
        "three_kind": "c_saturn",  # Saturn is actually Three of a Kind? Let me check
        "straight": "c_saturn",
        "flush": "c_jupiter",
        "full_house": "c_neptune",  # Actually I'm not sure about these
        "four_kind": "c_mars",     # Let me use correct associations
        "straight_flush": "c_neptune",
        "high_card": "c_pluto",
    }
    # 修正行星牌映射（Balatro实际对应关系）
    _HAND_TYPE_TO_PLANET = {
        "pair": "mercury",
        "two_pair": "uranus",
        "three_kind": "saturn",
        "straight": "saturn",
        "flush": "jupiter",
        "full_house": "mars",
        "four_kind": "mars",
        "straight_flush": "neptune",
        "high_card": "pluto",
    }

    def _resolve_committed_hand_type(self, state: GameState) -> Optional[str]:
        """根据当前Joker组合解析目标牌型（与HandAgent._resolve_commitment一致）。"""
        ante = state.ante
        if ante < 3:
            return None
        joker_keys = {str(j.get("key") or "").lower() for j in state.jokers}
        if not joker_keys:
            return None

        from collections import defaultdict
        signal_scores: Dict[str, float] = defaultdict(float)
        consistency_bonus = 0.0
        repeat_bonus = 0.0

        for key in joker_keys:
            signals = self._JOKER_HAND_TYPE_SIGNAL.get(key, [])
            for hand_type, strength in signals:
                if hand_type == "__consistency__":
                    consistency_bonus += strength
                elif hand_type == "__repeat__":
                    repeat_bonus += strength
                else:
                    signal_scores[hand_type] = signal_scores.get(hand_type, 0) + strength

        if consistency_bonus > 0 and signal_scores:
            best_type = max(signal_scores, key=signal_scores.get)
            signal_scores[best_type] += consistency_bonus * 0.8
        if repeat_bonus > 0:
            for small_type in ("pair", "high_card", "two_pair"):
                if small_type in signal_scores:
                    signal_scores[small_type] += repeat_bonus

        if not signal_scores:
            return None

        best_type = max(signal_scores, key=signal_scores.get)
        best_score = signal_scores[best_type]
        total_score = sum(signal_scores.values()) + 1.0
        confidence = best_score / total_score

        if ante >= 6:
            if best_score >= 2.5 or (best_score >= 1.5 and confidence >= 0.25):
                return best_type
        elif ante >= 3:
            if (best_score >= 5.0 and confidence >= 0.30) or (best_score >= 3.5 and confidence >= 0.35):
                return best_type
        return None

    def _hand_type_synergy_bonus(self, item: Dict[str, object], state: GameState) -> float:
        """Joker购买时，如果与目标牌型协同，给予额外加分。"""
        committed = self._resolve_committed_hand_type(state)
        if not committed:
            return 0.0

        item_name_lower = item_name(item).lower()
        item_key = str(item.get("key") or "").lower()
        bonus = 0.0

        # 购买Joker时：检查该Joker是否支持目标牌型
        signals = self._JOKER_HAND_TYPE_SIGNAL.get(item_key, [])
        for hand_type, strength in signals:
            if hand_type == committed:
                bonus += strength * 3.0  # 已有Joker信号的3倍系数
            elif hand_type == "__consistency__":
                bonus += strength * 2.0
            elif hand_type == "__repeat__":
                bonus += strength * 2.0

        # 已知强协同对
        if committed == "pair":
            if item_key in {"j_half", "j_photograph", "j_scholar", "j_hanging_chad",
                           "j_business_card", "j_even_steven", "j_odd_todd"}:
                bonus += 8.0
        elif committed == "flush":
            if item_key in {"j_lusty_joker", "j_greedy_joker", "j_wrathful_joker",
                           "j_gluttenous_joker", "j_ancient", "j_smeared"}:
                bonus += 8.0
        elif committed == "straight":
            if item_key in {"j_runner", "j_superposition", "j_ride_the_bus"}:
                bonus += 8.0
        elif committed == "two_pair":
            if item_key in {"j_trousers", "j_mad", "j_walkie_talkie"}:
                bonus += 8.0

        # 通用X-mult在锁定后更珍贵
        if "x" in item_name_lower and bonus > 0:
            bonus += 6.0

        return bonus

    def _committed_planet_bonus(self, item: Dict[str, object], state: GameState) -> float:
        """目标牌型对应的行星牌给予额外加分。"""
        committed = self._resolve_committed_hand_type(state)
        if not committed:
            return 0.0
        target_planet = self._HAND_TYPE_TO_PLANET.get(committed, "")
        if not target_planet:
            return 0.0
        item_key = str(item.get("key") or item.get("id") or "").lower()
        item_name_lower = item_name(item).lower()
        if target_planet in item_key or target_planet in item_name_lower:
            return 15.0 + state.ante * 2.0  # 越后期越重要
        return 0.0

    def propose(self, state: GameState, genome: Genome) -> List[ActionProposal]:
        if state.phase != SHOP:
            return []
        proposals: List[ActionProposal] = []
        money = state.money
        joker_slots_full = state.joker_limit > 0 and len(state.jokers) >= state.joker_limit
        consumable_slots_full = (
            state.consumable_limit > 0 and len(state.consumables) >= state.consumable_limit
        )

        if joker_slots_full:
            sell_proposal = self._sell_joker_proposal(state, money, genome)
            if sell_proposal is not None:
                proposals.append(sell_proposal)

        # 自动卖出已失效的Joker（如牌库空时的Erosion）
        dead_sell = self._sell_dead_joker_proposal(state)
        if dead_sell is not None:
            proposals.append(dead_sell)

        for index, item in enumerate(state.shop_cards()):
            cost = item_cost(item)
            if cost and cost > money:
                continue
            kind = item_type(item)
            if kind == "JOKER":
                if joker_slots_full:
                    continue
                base = self._joker_strength(item, state, genome) * genome.weight("buy_joker")
                # Boss感知调整
                base += self._boss_aware_joker_adjust(item, state)
                # 后期低分Joker不值得购买
                if state.ante >= 4 and self._joker_strength(item, state, genome) < 20.0:
                    base *= 0.5
                # ante 5+: chip Joker降权，mult/X-mult升权
                if state.ante >= 5:
                    key = str(item.get("key") or "").lower()
                    name_lower = item_name(item).lower()
                    effect = ""
                    value = item.get("value")
                    if isinstance(value, dict):
                        effect = str(value.get("effect") or "").lower()
                    is_chip_joker = ("chip" in name_lower or "筹码" in effect) and \
                        "mult" not in name_lower and "倍率" not in effect and \
                        "x" not in name_lower
                    if is_chip_joker:
                        base *= 0.65
                    if "x" in name_lower or "x" in effect:
                        base *= 1.25
            elif kind in {"CONSUMABLE", "TAROT", "PLANET", "SPECTRAL"}:
                if consumable_slots_full:
                    continue
                base = self._consumable_buy_score(item, state, genome)
                if base is None:
                    continue
                # 消耗品槽全空时提升塔罗牌购买意愿——确保进入盲注时有即时战力
                if len(state.consumables) == 0 and kind != "PLANET":
                    base *= genome.weight("consumable_empty_slot_bonus", 1.5)
            else:
                base = 5.0
            base += self._synergy_bonus(item, state, genome)
            # 渐进式牌型专精：目标牌型协同加分
            base += self._hand_type_synergy_bonus(item, state)
            cash_reserve = int(
                genome.weight("cash_reserve", 8.0)
                + state.ante * genome.weight("cash_reserve_ante_scale", 1.5)
            )
            base -= max(0, cost - max(0, money - cash_reserve)) * 0.7
            proposals.append(
                ActionProposal(
                    "buy",
                    {"card": index},
                    base,
                    self.name,
                    confidence=0.55,
                    reasons=[f"商店卡牌：{item_name(item) or kind or index}"],
                )
            )

        for index, voucher in enumerate(state.shop_vouchers()):
            cost = item_cost(voucher)
            if cost and cost > money:
                continue
            voucher_score = 22.0 * genome.weight("buy_voucher")  # 提高基础分：22*0.7≈15.4
            # 优惠券是永久升级，越早买越值
            voucher_score += max(0, 8 - state.ante) * 2.0  # ante1 +14, ante4 +8
            proposals.append(
                ActionProposal(
                    "buy",
                    {"voucher": index},
                    voucher_score,
                    self.name,
                    confidence=0.5,
                    reasons=[f"优惠券：{item_name(voucher) or index}"],
                )
            )

        for index, pack in enumerate(state.shop_packs()):
            cost = item_cost(pack)
            if cost and cost > money:
                continue
            if joker_slots_full and "buffoon" in item_name(pack).lower():
                continue
            pack_score = 25.0 * genome.weight("buy_pack")  # 提高基础分：25*0.4=10
            # 星球牌包：锁定目标牌型后大幅加分
            pack_name = item_name(pack).lower()
            if "celestial" in pack_name or "planet" in pack_name or "天体" in pack_name:
                committed = self._resolve_committed_hand_type(state)
                if committed:
                    pack_score += 20.0 + state.ante * 2.0  # commit后+20~32
            # 塔罗牌包：Campfire or 临近Boss时加分
            if "arcanum" in pack_name or "tarot" in pack_name:
                if self._has_campfire(state):
                    pack_score += 10.0
                if self._approaching_single_hand_boss(state):
                    pack_score += 8.0
            # 优惠包（buffoon）：有空槽时加分
            if "buffoon" in pack_name and not joker_slots_full:
                pack_score += 5.0
            proposals.append(
                ActionProposal(
                    "buy",
                    {"pack": index},
                    pack_score,
                    self.name,
                    confidence=0.5,
                    reasons=[f"补充包：{item_name(pack) or index}"],
                )
            )
        return proposals

    def _sell_joker_proposal(
        self,
        state: GameState,
        money: int,
        genome: Genome,
    ) -> Optional[ActionProposal]:
        owned = list(state.jokers)
        if not owned:
            return None

        chad_sell = self._hanging_chad_small_build_sell_proposal(state, money)
        if chad_sell is not None:
            return chad_sell

        abstract_sell = self._abstract_over_popcorn_chad_sell_proposal(state, money)
        if abstract_sell is not None:
            return abstract_sell

        best_shop_option: Optional[Tuple[float, int, Dict[str, object]]] = None
        for index, item in enumerate(state.shop_cards()):
            if item_type(item) != "JOKER":
                continue
            cost = item_cost(item)
            if cost and cost > money:
                continue
            score = self._joker_strength(item, state, genome)
            candidate = (score, index, item)
            if best_shop_option is None or candidate > best_shop_option:
                best_shop_option = candidate

        if best_shop_option is None:
            return None

        weakest_owned = min(
            (
                (self._joker_strength(joker, state, genome), index, joker)
                for index, joker in enumerate(owned)
            ),
            default=None,
        )
        if weakest_owned is None:
            return None

        best_score, _, best_item = best_shop_option
        weakest_score, weakest_index, weakest_item = weakest_owned
        # 保护Blue Joker：Half+Chad构筑中的筹码基石不应被非chip非xmult替换
        weakest_key = str(weakest_item.get("key") or "").lower()
        if weakest_key == "j_blue_joker" or "blue joker" in item_name(weakest_item).lower():
            owned_keys = {str(j.get("key") or "").lower() for j in state.jokers}
            if {"j_half", "j_hanging_chad"} & owned_keys:
                best_key = str(best_item.get("key") or "").lower()
                best_name = item_name(best_item).lower()
                is_chip = "chip" in best_name or "筹码" in str(best_item.get("value", {})).lower()
                is_xmult = "x" in best_name or "x" in best_key
                if not is_chip and not is_xmult:
                    return None  # 不替换Blue Joker除非换的是chip或xmult
        # ante 4+ 无X-mult时降低X-mult Joker替换门槛
        margin = genome.weight("joker_replacement_margin", self._JOKER_REPLACEMENT_MARGIN)
        best_key = str(best_item.get("key") or "").lower()
        best_name = item_name(best_item).lower()
        # Photograph-Chad协同保护：卖Chad换Photograph时，Photograph失去Chad加成
        if best_key == "j_photograph" or "photograph" in best_name:
            weakest_key = str(weakest_item.get("key") or "").lower()
            if weakest_key == "j_hanging_chad" or "hanging chad" in item_name(weakest_item).lower():
                best_score -= 14.0  # 扣除Chad加成(+10)和Half+Chad联合加成(+4)
        # Chad主动保护：Half构筑中的重触发核心，不卖Chad换非重触发/非Xmult
        weakest_key_ck = str(weakest_item.get("key") or "").lower()
        if weakest_key_ck == "j_hanging_chad" or "hanging chad" in item_name(weakest_item).lower():
            owned_keys = {str(j.get("key") or "").lower() for j in state.jokers}
            if "j_half" in owned_keys:
                best_value = best_item.get("value", {})
                best_effect = str(best_value.get("effect", "") or "").lower() if isinstance(best_value, dict) else ""
                is_retrigger = "retrigger" in best_effect or "trigger" in best_effect
                is_strong_xmult = ("x" in best_name or "x" in best_key) and best_score > 45
                if not is_retrigger and not is_strong_xmult:
                    return None  # Chad+Half核心不容替换
        xmult_priority_ante = int(genome.weight("xmult_priority_ante", 4.0))
        if state.ante >= xmult_priority_ante and ("x" in best_name or "x" in best_key):
            has_xmult = any(
                "x" in str(owned.get("key", "") or "").lower()
                or "x" in str(owned.get("name", "") or "").lower()
                for owned in state.jokers
            )
            if not has_xmult:
                margin = 4.0  # 大幅降低门槛，鼓励入手首张X-mult
        if best_score < weakest_score + margin:
            return None

        return ActionProposal(
            "sell",
            {"joker": weakest_index},
            16.0 + best_score - weakest_score,
            self.name,
            confidence=0.6,
            reasons=[
                f"卖出较弱 Joker：{item_name(weakest_item) or weakest_index}",
                f"为更强 Joker 腾槽：{item_name(best_item)}",
            ],
        )

    def _hanging_chad_small_build_sell_proposal(
        self,
        state: GameState,
        money: int,
    ) -> Optional[ActionProposal]:
        owned_keys = {str(joker.get("key") or "").lower() for joker in state.jokers}
        if not {
            "j_sly",
            "j_scary_face",
            "j_half",
            "j_supernova",
            "j_popcorn",
        }.issubset(owned_keys):
            return None

        chad_available = False
        for item in state.shop_cards():
            key = str(item.get("key") or item.get("id") or "").lower()
            if key != "j_hanging_chad" or item_type(item) != "JOKER":
                continue
            cost = item_cost(item)
            if cost and cost > money:
                continue
            chad_available = True
            break
        if not chad_available:
            return None

        for index, joker in enumerate(state.jokers):
            if str(joker.get("key") or "").lower() == "j_supernova":
                return ActionProposal(
                    "sell",
                    {"joker": index},
                    44.0,
                    self.name,
                    confidence=0.6,
                    reasons=[
                        "卖出 Supernova 试验 Hanging Chad 小牌型触发",
                        "保留 Sly/Scary Face/Half/Popcorn 核心",
                    ],
                )
        return None

    def _abstract_over_popcorn_chad_sell_proposal(
        self,
        state: GameState,
        money: int,
    ) -> Optional[ActionProposal]:
        owned_keys = {str(joker.get("key") or "").lower() for joker in state.jokers}
        if not self._is_chad_small_hand_build_keys(owned_keys):
            return None

        abstract_available = False
        for item in state.shop_cards():
            key = str(item.get("key") or item.get("id") or "").lower()
            if key != "j_abstract" or item_type(item) != "JOKER":
                continue
            cost = item_cost(item)
            if cost and cost > money:
                continue
            abstract_available = True
            break
        if not abstract_available:
            return None

        for index, joker in enumerate(state.jokers):
            if str(joker.get("key") or "").lower() == "j_popcorn":
                return ActionProposal(
                    "sell",
                    {"joker": index},
                    40.0,
                    self.name,
                    confidence=0.6,
                    reasons=[
                        "卖出衰减 Popcorn 替换为 Abstract Joker",
                        "保留 Sly/Scary Face/Half/Hanging Chad 核心",
                    ],
                )
        return None

    def _sell_dead_joker_proposal(self, state: GameState) -> Optional[ActionProposal]:
        """当Joker因游戏状态变化而失效时（如牌库空→Erosion=0），提议卖出。"""
        for index, joker in enumerate(state.jokers):
            strength = self._joker_strength(joker, state)
            if strength < 0:
                return ActionProposal(
                    "sell",
                    {"joker": index},
                    50.0,  # 高分确保优先执行
                    self.name,
                    confidence=0.95,
                    reasons=[f"卖出已失效 Joker：{item_name(joker) or index}（当前环境无价值）"],
                )
        return None

    def _boss_aware_joker_adjust(self, item: Dict[str, object], state: GameState) -> float:
        """根据即将到来的Boss盲注调整Joker购买评分。"""
        name = state.blind_name.lower()
        joker_key = str(item.get("key") or "").lower()
        adjust = 0.0
        # 花色削弱Boss：降低对应花色Joker评分
        debuff_map = {"the head": "H", "the goad": "S", "the club": "C", "the window": "D"}
        suit_jokers = {"H": "j_lusty_joker", "S": "j_wrathful_joker",
                       "D": "j_greedy_joker", "C": "j_gluttenous_joker"}
        for boss, suit in debuff_map.items():
            if boss in name:
                if joker_key == suit_jokers.get(suit, ""):
                    adjust -= 20.0
        # The Mouth: 倾向专注型Joker
        if "the mouth" in name:
            focus_jokers = {"j_half", "j_photograph", "j_runner", "j_scholar",
                            "j_walkie_talkie", "j_hanging_chad"}
            if joker_key in focus_jokers:
                adjust += 8.0
        return adjust

    def _consumable_buy_score(
        self,
        item: Dict[str, object],
        state: GameState,
        genome: Genome,
    ) -> Optional[float]:
        kind = item_type(item)
        key = str(item.get("key") or item.get("id") or "").lower()
        base = 28.0 * genome.weight("buy_consumable")  # 大幅提升消耗品购买意愿

        if kind == "PLANET":
            if self._is_completed_small_hand_build(state) and not self._is_small_hand_planet(item):
                return None
            # 行星牌是永久升级，基础分更高
            ante_bonus = max(0.0, state.ante - 1) * 3.0
            # 如果手牌等级还很低（<3级），行星牌价值更高
            level_bonus = self._planet_level_bonus(state, item)
            score = base + ante_bonus + level_bonus
            # 渐进式牌型专精：目标牌型行星牌大幅加分
            score += self._committed_planet_bonus(item, state)
            # 临近The Needle等单手Boss时，升行星更紧迫
            if self._approaching_single_hand_boss(state):
                score += 12.0
            return score
        # 支持所有已知塔罗牌购买
        if key in TARGETED_TAROT_COUNTS or key in ConsumableAgent._NO_TARGET_TAROTS:
            score = base
            # Campfire燃料：拥有Campfire时塔罗牌价值提升
            if self._has_campfire(state):
                score += 8.0
            # 临近单手Boss：塔罗牌用于增强关键牌
            if self._approaching_single_hand_boss(state):
                score += 6.0
            # Hermit在缺钱时价值极高
            if key == "c_hermit" and state.money < 10:
                score += 8.0
            return score
        # Campfire模式下，任何廉价消耗品都有燃料价值
        if self._has_campfire(state) and item_cost(item) and item_cost(item) <= 4:
            return base + 6.0
        return None

    def _has_campfire(self, state: GameState) -> bool:
        return any(
            str(joker.get("key") or "").lower() == "j_campfire"
            for joker in state.jokers
        )

    def _approaching_single_hand_boss(self, state: GameState) -> bool:
        """检测是否接近单手Boss（The Needle, The Eye等）。"""
        name = state.blind_name.lower()
        if "the needle" in name:
            return True
        # 提前一个盲注准备：如果是boss盲且可能是The Needle
        if state.ante >= 4 and "boss" in name and state.hands_remaining <= 1:
            return True
        return False

    def _is_completed_small_hand_build(self, state: GameState) -> bool:
        owned_keys = {str(joker.get("key") or "").lower() for joker in state.jokers}
        supernova_build = {
            "j_sly",
            "j_scary_face",
            "j_half",
            "j_supernova",
            "j_popcorn",
        }.issubset(owned_keys)
        return supernova_build or self._is_chad_small_hand_build_keys(owned_keys)

    def _is_chad_small_hand_build_keys(self, owned_keys: set[str]) -> bool:
        core = {
            "j_sly",
            "j_scary_face",
            "j_half",
            "j_hanging_chad",
        }
        return core.issubset(owned_keys) and (
            "j_popcorn" in owned_keys or "j_abstract" in owned_keys
        )

    def _is_small_hand_planet(self, item: Dict[str, object]) -> bool:
        name = item_name(item).lower()
        key = str(item.get("key") or item.get("id") or "").lower()
        return any(
            token in name or token in key
            for token in {"mercury", "venus", "pluto"}
        )

    def _planet_level_bonus(self, state: GameState, item: Dict[str, object]) -> float:
        """低等级手牌的行星牌价值更高。"""
        name = item_name(item).lower()
        raw = state.raw.get("hands") if isinstance(state.raw, dict) else None
        if not isinstance(raw, dict):
            return 0.0
        for hand_name, hand_state in raw.items():
            if not isinstance(hand_state, dict):
                continue
            if hand_name.lower() not in name:
                continue
            level = float(hand_state.get("level", 1) or 1)
            if level < 3:
                return 8.0
            if level < 5:
                return 4.0
            return 1.0
        return 0.0

    def _synergy_bonus(self, item: Dict[str, object], state: GameState, genome: Genome) -> float:
        name = item_name(item).lower()
        bonus = 0.0
        if "mult" in name:
            bonus += 2.5
        if "chip" in name:
            bonus += 1.5
        if state.ante >= 4 and "x" in name:
            bonus += 3.0
        return bonus * genome.weight("synergy")

    def _joker_strength(
        self,
        item: Dict[str, object],
        state: Optional[GameState] = None,
        genome: Optional[Genome] = None,
    ) -> float:
        key = str(item.get("key") or item.get("id") or "").lower()
        name = item_name(item).lower()
        value = item.get("value")
        effect = ""
        if isinstance(value, dict):
            effect = str(value.get("effect") or "").lower()

        key_scores = {
            "j_abstract": 36.0,
            "j_ancient": 18.0,
            "j_baron": 18.0,
            "j_blueprint": 38.0,
            "j_brainstorm": 36.0,
            "j_castle": 24.0,
            "j_delayed_grat": 6.0,
            "j_dna": 26.0,
            "j_gluttenous_joker": 14.0,
            "j_joker": 18.0,
            "j_lusty_joker": 14.0,
            "j_greedy_joker": 14.0,
            "j_wrathful_joker": 14.0,
            "j_half": 30.0,
            "j_mime": 24.0,
            "j_pareidolia": 18.0,
            "j_photograph": 24.0,
            "j_scholar": 20.0,
            "j_smeared": 22.0,
            "j_sock_and_buskin": 26.0,
            "j_square": 24.0,
            "j_walkie_talkie": 22.0,
            "j_blue_joker": 24.0,
            "j_campfire": 20.0,
            "j_credit_card": 1.0,
            "j_red_card": 4.0,
            "j_rocket": 1.0,
            "j_hallucination": 6.0,
            "j_to_the_moon": 1.0,
            "j_golden_joker": 3.0,
            "j_cloud_9": 3.0,
            "j_business": 1.0,
            "j_business_card": 1.0,
            "j_faceless": 3.0,
            "j_hanging_chad": 28.0,
            "j_ice_cream": 34.0,
            "j_madness": 24.0,
            "j_banner": 26.0,
            "j_gros_michel": 34.0,
            "j_smiley": 20.0,
            "j_trousers": 28.0,
        }
        base = key_scores.get(key, 14.0)

        if "abstract joker" in name:
            base = max(base, 36.0)
        if "ancient joker" in name:
            base = max(base, 18.0)
        if "baron" in name:
            base = max(base, 18.0)
        if "blueprint" in name:
            base = max(base, 38.0)
        if "brainstorm" in name:
            base = max(base, 36.0)
        if "castle" in name:
            base = max(base, 24.0)
        if "dna" in name:
            base = max(base, 26.0)
        if "scholar" in name:
            base = max(base, 20.0)
        if "spare trousers" in name:
            base = max(base, 28.0)
        if "photograph" in name:
            base = max(base, 24.0)
        if "mime" in name:
            base = max(base, 24.0)
        if "pareidolia" in name:
            base = max(base, 18.0)
        if "smeared joker" in name:
            base = max(base, 22.0)
        if "sock and buskin" in name:
            base = max(base, 26.0)
        if "campfire" in name:
            base = max(base, 20.0)
        if "half joker" in name:
            base = max(base, 30.0)
        if "credit card" in name:
            base = min(base, 1.0)
        if "ice cream" in name:
            if state is not None:
                # Ice Cream 每手牌 -4 chips。ante 4+ 开始明显衰减
                decay = max(0, state.ante - 3) * 10.0
                base = max(base, max(4.0, 34.0 - decay))
            else:
                base = max(base, 34.0)
        if "madness" in name:
            base = max(base, 24.0)
        if "banner" in name:
            base = max(base, 26.0)
        if "gros michel" in name:
            base = max(base, 34.0)
        if "smiley face" in name:
            base = max(base, 20.0)
        if "business card" in name:
            base = min(base, 1.0)

        if key not in key_scores:
            if "x" in name or "x" in effect or "倍率" in effect:
                base += 20.0  # X-mult 稀缺，提升但不过分
            elif "mult" in name or "mult" in effect:
                base += 6.0
            if "chip" in name or "chip" in effect or "筹码" in effect:
                base += 4.0
            if "trigger" in effect or "额外触发" in effect:
                base += 6.0
            if "discard" in name or "弃牌" in effect:
                base -= 3.0
            if "$" in effect or "money" in name or "dollar" in name:
                base -= 2.0
            # 纯经济Joker占槽位但无战斗力，严重降分
            if key in {"j_to_the_moon", "j_rocket", "j_golden_joker", "j_cloud_9", "j_business_card", "j_faceless"}:
                base = min(base, 8.0)
            if "to the moon" in name or "rocket" in name:
                base = min(base, 6.0)

        # Stencil：空槽越多越强，满槽时价值极低
        if key == "j_stencil" or "stencil" in name:
            if state is not None:
                empty_slots = state.joker_limit - len(state.jokers)
                base = 8.0 + empty_slots * 8.0  # 0空槽=8, 1空槽=16, 2空槽=24...
            else:
                base = 16.0  # 未知状态保守估计（通常1-2空槽）
        # Mystic Summit 仅在最后手+15 mult，条件严苛
        if key == "j_mystic_summit" or "mystic summit" in name:
            base = min(base, 12.0)
        # Jolly: 仅+8 mult for pairs，太弱
        if key == "j_jolly" or "jolly joker" in name:
            base = min(base, 10.0)

        if state is not None:
            owned_keys = {str(joker.get("key") or "").lower() for joker in state.jokers}
            base += self._archetype_joker_bonus(key, name, effect, state, owned_keys)
            if key == "j_blue_joker" or "blue joker" in name:
                # Blue Joker 是核心筹码来源，配合Half/Chad时不可替代
                deck_remaining = state.deck_card_count if state.deck_card_count > 0 else 52
                base = max(base, 20.0 + deck_remaining * 0.25)  # 52牌=33, 40牌=30
                if {"j_half", "j_hanging_chad"} & owned_keys:
                    base += 8.0  # Half+Chad构筑中Blue=必需筹码基础
            if key == "j_photograph":
                if "j_hanging_chad" in owned_keys:
                    base += 10.0
                if "j_half" in owned_keys:
                    base += 4.0
            if key == "j_scholar":
                if "j_half" in owned_keys:
                    base += 8.0
                if "j_hanging_chad" in owned_keys:
                    base += 4.0
                # 同时拥有Chad和Half时学者价值大幅提升（终极对子构建）
                if "j_hanging_chad" in owned_keys and "j_half" in owned_keys:
                    base += 6.0
                if self._is_chad_small_hand_build_keys(owned_keys):
                    base = min(base, 25.0)
            if key == "j_banner" or "banner" in name:
                base += min(8.0, max(0, state.discards_remaining) * 2.0)
            if self._is_third_narrow_conditional_joker(key, state):
                base = min(base, 2.0)
            if key == "j_sly" and ({"j_scary_face", "j_half"} & owned_keys):
                base = max(base, 20.0)
            if self._is_chad_small_hand_build_keys(owned_keys):
                if key in {"j_sly", "j_scary_face", "j_half", "j_hanging_chad"}:
                    base = max(base, 42.0)
            # Fortune Teller在没有塔罗牌配合时很弱
            if key == "j_fortune_teller" or "fortune" in name:
                tarot_count = sum(1 for c in state.consumables if item_type(c) in ("TAROT", "CONSUMABLE"))
                if tarot_count == 0 and state.money < 5:
                    base = min(base, 12.0)
            # 牌库耗尽时，依赖牌库的Joker价值归零
            if state.deck_card_count <= 0:
                if key == "j_erosion" or "erosion" in name:
                    base = -10.0  # 强力负面信号，应该卖掉
                if "deck" in effect.lower() or "below" in effect.lower():
                    base = min(base, 2.0)
            # 经济Joker动态估值：剩余局数越多价值越高，但ante 1-2现金紧张时不宜高价买纯经济牌
            if key in {"j_delayed_grat", "j_golden_joker", "j_business_card",
                       "j_to_the_moon", "j_rocket", "j_cloud_9", "j_faceless"}:
                remaining_rounds = max(1, (8 - state.ante) * 3 + (3 - state.round_number % 3))
                economy_bonus = min(remaining_rounds * 0.8, 12.0)
                # 早期现金紧张：ante 1-2时纯经济Joker价值受限
                early_penalty = 0.7 if state.ante <= 2 else 1.0
                if key == "j_delayed_grat":
                    base = max(base, 8.0 + economy_bonus * early_penalty)
                elif key in {"j_golden_joker", "j_business_card"}:
                    base = max(base, 4.0 + economy_bonus * 0.7 * early_penalty)
                else:
                    # Rocket等纯经济Joker不提供战力，保持低估值
                    base = max(base, 1.0 + economy_bonus * 0.25 * early_penalty)
            # 缩放型Joker：按回合数加基础分（已投入多轮不应被轻易替换）
            if key == "j_supernova" or "supernova" in name:
                base = max(base, 22.0 + state.round_number * 1.5)
            if key == "j_ride_the_bus" or "ride the bus" in name:
                base = max(base, 20.0 + state.round_number * 2.0)
            if key == "j_green_joker" or "green joker" in name:
                base = max(base, 18.0 + state.round_number * 1.0)
            # ante 4+：无X-mult的构筑应大幅提升X-mult优先级
            xmult_priority_ante = int(
                genome.weight("xmult_priority_ante", 4.0) if genome is not None else 4
            )
            if state.ante >= xmult_priority_ante and ("x" in name or "x" in effect):
                has_xmult = any(
                    "x" in str(owned.get("key", "") or "").lower()
                    or "x" in str(owned.get("name", "") or "").lower()
                    for owned in state.jokers
                )
                if not has_xmult:
                    base += 20.0  # 无X-mult时大幅提升首张X-mult价值
        return base

    def _archetype_joker_bonus(
        self,
        key: str,
        name: str,
        effect: str,
        state: GameState,
        owned_keys: set[str],
    ) -> float:
        bonus = 0.0

        if key == "j_trousers" or "spare trousers" in name:
            if state.ante <= 3:
                bonus += 8.0
            if owned_keys & {"j_square", "j_mad", "j_clever", "j_sly", "j_jolly"}:
                bonus += 6.0

        if key in {"j_hanging_chad", "j_sock_and_buskin"}:
            if "j_photograph" in owned_keys:
                bonus += 14.0
            if "j_pareidolia" in owned_keys:
                bonus += 6.0

        if key == "j_photograph":
            if owned_keys & {"j_hanging_chad", "j_sock_and_buskin"}:
                bonus += 10.0
            if "j_pareidolia" in owned_keys:
                bonus += 6.0

        if key == "j_midas_mask" and owned_keys & {"j_pareidolia", "j_photograph", "j_sock_and_buskin"}:
            bonus += 8.0

        if key == "j_baron":
            bonus += self._steel_king_route_bonus(state, owned_keys)

        if key in {"j_mime", "j_blueprint", "j_brainstorm", "j_dna"}:
            if "j_baron" in owned_keys or self._steel_king_count(state) > 0:
                bonus += 10.0

        suit_jokers = {
            "H": "j_lusty_joker",
            "D": "j_greedy_joker",
            "S": "j_wrathful_joker",
            "C": "j_gluttenous_joker",
        }
        for suit, joker_key in suit_jokers.items():
            if key == joker_key:
                bonus += self._suit_focus_bonus(state, suit)
        if key in {"j_ancient", "j_smeared", "j_castle"}:
            bonus += self._best_suit_focus_bonus(state) * 0.6

        return bonus

    def _steel_king_route_bonus(self, state: GameState, owned_keys: set[str]) -> float:
        king_count = self._rank_count(state, 13)
        steel_king_count = self._steel_king_count(state)
        if king_count == 0 and steel_king_count == 0:
            return 0.0

        bonus = steel_king_count * 14.0 + max(0, king_count - 1) * 2.0
        if owned_keys & {"j_blueprint", "j_brainstorm", "j_mime", "j_dna"}:
            bonus += 8.0
        return bonus

    def _rank_count(self, state: GameState, rank_value: int) -> int:
        return sum(1 for card in self._profile_cards(state) if card_rank_value(card) == rank_value)

    def _steel_king_count(self, state: GameState) -> int:
        return sum(
            1
            for card in self._profile_cards(state)
            if card_rank_value(card) == 13 and card_enhancement(card) == "STEEL"
        )

    def _suit_focus_bonus(self, state: GameState, suit: str) -> float:
        cards = self._profile_cards(state)
        if not cards:
            return 0.0
        suit_count = sum(1 for card in cards if card_suit(card) == suit)
        ratio = suit_count / len(cards)
        if suit_count >= 5 and ratio >= 0.45:
            return 14.0
        if suit_count >= 4 and ratio >= 0.35:
            return 7.0
        return 0.0

    def _best_suit_focus_bonus(self, state: GameState) -> float:
        return max((self._suit_focus_bonus(state, suit) for suit in ("H", "D", "S", "C")), default=0.0)

    def _profile_cards(self, state: GameState) -> List[Dict[str, object]]:
        cards = list(state.deck_cards)
        if cards:
            return cards
        return list(state.hand)

    def _is_third_narrow_conditional_joker(self, key: str, state: GameState) -> bool:
        if state.ante < 2 or key == "j_sly" or key not in self._NARROW_CONDITIONAL_JOKERS:
            return False
        owned_count = sum(
            1
            for joker in state.jokers
            if str(joker.get("key") or "").lower() in self._NARROW_CONDITIONAL_JOKERS
        )
        return owned_count >= 2
