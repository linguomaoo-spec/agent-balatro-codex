from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from balatro_agent.model import ActionProposal, GameState


SELECTING_HAND = "SELECTING_HAND"
SHOP = "SHOP"
ROUND_EVAL = "ROUND_EVAL"
BLIND_SELECT = "BLIND_SELECT"
BOOSTER_OPENED = "SMODS_BOOSTER_OPENED"
GAME_OVER = "GAME_OVER"


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""


def _bad(reason: str) -> ValidationResult:
    return ValidationResult(False, reason)


def _good() -> ValidationResult:
    return ValidationResult(True, "")


def _exactly_one(params: Dict[str, Any], keys: List[str]) -> bool:
    return sum(1 for key in keys if key in params and params[key] is not None) == 1


def _integer_indices(value: Any) -> Optional[List[int]]:
    if not isinstance(value, list) or not value:
        return None
    indices: List[int] = []
    for item in value:
        if not isinstance(item, int) or item < 0:
            return None
        indices.append(item)
    return indices


def _validate_indices(name: str, value: Any, upper_bound: Optional[int]) -> ValidationResult:
    indices = _integer_indices(value)
    if indices is None:
        return _bad(f"{name} 必须是非空的非负整数索引列表")
    if upper_bound is not None:
        for index in indices:
            if index >= upper_bound:
                return _bad(f"{name} 索引 {index} 超出 {upper_bound} 张牌的范围")
    return _good()


def _require_phase(state: GameState, expected: str) -> ValidationResult:
    if state.phase != expected:
        return _bad(f"需要 {expected} 阶段，当前是 {state.phase}")
    return _good()


def validate_action(action: ActionProposal, state: GameState) -> ValidationResult:
    method = action.method
    params = action.params or {}

    if method in {"gamestate", "health", "menu", "start", "save", "load", "screenshot", "set", "add"}:
        return _good()

    if method in {"play", "discard"}:
        phase_check = _require_phase(state, SELECTING_HAND)
        if not phase_check.ok:
            return phase_check
        hand_len = len(state.hand)
        return _validate_indices("cards", params.get("cards"), hand_len if hand_len else None)

    if method == "buy":
        phase_check = _require_phase(state, SHOP)
        if not phase_check.ok:
            return phase_check
        if not _exactly_one(params, ["card", "voucher", "pack"]):
            return _bad("buy 必须且只能指定 card、voucher 或 pack 中的一个")
        return _validate_single_index(params, state)

    if method == "sell":
        phase_check = _require_phase(state, SHOP)
        if not phase_check.ok:
            return phase_check
        if not _exactly_one(params, ["joker", "consumable"]):
            return _bad("sell 必须且只能指定 joker 或 consumable 中的一个")
        return _good()

    if method in {"reroll", "next_round"}:
        return _require_phase(state, SHOP)

    if method in {"select", "skip"}:
        return _require_phase(state, BLIND_SELECT)

    if method == "cash_out":
        return _require_phase(state, ROUND_EVAL)

    if method == "use":
        if "consumable" not in params:
            return _bad("use 需要 consumable 索引")
        cards = params.get("cards")
        if cards is not None:
            return _validate_indices("cards", cards, len(state.hand) or None)
        return _good()

    if method == "rearrange":
        if not _exactly_one(params, ["hand", "jokers", "consumables"]):
            return _bad("rearrange 必须且只能指定 hand、jokers 或 consumables 中的一个")
        return _good()

    if method == "pack":
        return _require_phase(state, BOOSTER_OPENED)

    return _bad(f"不支持的方法：{method}")


def _validate_single_index(params: Dict[str, Any], state: GameState) -> ValidationResult:
    for key, items in (
        ("card", state.shop_cards()),
        ("voucher", state.shop_vouchers()),
        ("pack", state.shop_packs()),
    ):
        if key not in params:
            continue
        value = params[key]
        if not isinstance(value, int) or value < 0:
            return _bad(f"{key} 必须是非负整数索引")
        if items and value >= len(items):
            return _bad(f"{key} 索引 {value} 超出 {len(items)} 个商店物品的范围")
    return _good()
