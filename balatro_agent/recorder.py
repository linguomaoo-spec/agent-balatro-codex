from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from balatro_agent.actions import GAME_OVER
from balatro_agent.model import GameState, card_identity, card_rank, card_suit, item_name


def state_digest(raw: Dict[str, Any]) -> str:
    payload = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class StateRecorder:
    client: Any
    output_path: Path
    include_raw: bool = True
    only_changes: bool = True
    now: Callable[[], datetime] = field(default_factory=lambda: _utcnow)

    def run(
        self,
        interval_seconds: float = 1.0,
        max_polls: Optional[int] = None,
        max_snapshots: Optional[int] = None,
        stop_on_game_over: bool = True,
    ) -> Dict[str, Any]:
        self.output_path = Path(self.output_path)
        if max_snapshots is not None and max_snapshots <= 0:
            return self._result("max_snapshots", 0, 0, None)
        if max_polls is not None and max_polls <= 0:
            return self._result("max_polls", 0, 0, None)

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        started_at = time.monotonic()
        previous_hash: Optional[str] = None
        polls = 0
        snapshots = 0
        status = "interrupted"
        last_state: Optional[GameState] = None
        previous_raw: Optional[Dict[str, Any]] = None
        previous_state: Optional[GameState] = None

        try:
            while True:
                raw = self._raw_state()
                state = GameState(raw)
                digest = state_digest(raw)
                polls += 1

                if not self.only_changes or digest != previous_hash:
                    action = infer_action(previous_raw, previous_state, raw, state)
                    self._append_snapshot(
                        raw,
                        state,
                        digest,
                        previous_hash,
                        snapshots,
                        polls,
                        started_at,
                        action,
                    )
                    previous_hash = digest
                    previous_raw = raw
                    previous_state = state
                    snapshots += 1

                last_state = state
                if stop_on_game_over and state.phase == GAME_OVER:
                    status = _terminal_status(state)
                    break
                if max_snapshots is not None and snapshots >= max_snapshots:
                    status = "max_snapshots"
                    break
                if max_polls is not None and polls >= max_polls:
                    status = "max_polls"
                    break
                if interval_seconds > 0:
                    time.sleep(interval_seconds)
        except KeyboardInterrupt:
            status = "interrupted"

        return self._result(status, polls, snapshots, last_state)

    def _raw_state(self) -> Dict[str, Any]:
        raw = self.client.gamestate()
        if isinstance(raw, dict):
            return raw
        return {"value": raw}

    def _append_snapshot(
        self,
        raw: Dict[str, Any],
        state: GameState,
        digest: str,
        previous_hash: Optional[str],
        snapshot_index: int,
        poll_index: int,
        started_at: float,
        action: Optional[Dict[str, Any]] = None,
    ) -> None:
        record: Dict[str, Any] = {
            "type": "human_state_snapshot",
            "timestamp": _format_timestamp(self.now()),
            "elapsed_seconds": round(time.monotonic() - started_at, 3),
            "poll_index": poll_index,
            "snapshot_index": snapshot_index,
            "state_hash": digest,
            "previous_hash": previous_hash,
            "terminal": state.phase == GAME_OVER,
            "state": state.summary(),
        }
        if action:
            record["action"] = action
        if self.include_raw:
            record["raw"] = raw
        with self.output_path.open("a") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")

    def _result(
        self,
        status: str,
        polls: int,
        snapshots: int,
        last_state: Optional[GameState],
    ) -> Dict[str, Any]:
        return {
            "output": str(self.output_path),
            "status": status,
            "polls": polls,
            "snapshots": snapshots,
            "last_state": last_state.summary() if last_state else None,
        }


@dataclass
class ActionRecorder:
    client: Any
    output_path: Path
    now: Callable[[], datetime] = field(default_factory=lambda: _utcnow)

    def run(
        self,
        interval_seconds: float = 1.0,
        max_polls: Optional[int] = None,
        stop_on_game_over: bool = True,
    ) -> Dict[str, Any]:
        self.output_path = Path(self.output_path)
        if max_polls is not None and max_polls <= 0:
            return self._result("max_polls", 0, 0, None, {})

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        started_at = self.now()
        log: Dict[str, Any] = {
            "type": "human_action_run",
            "version": 1,
            "started_at": _format_timestamp(started_at),
            "updated_at": _format_timestamp(started_at),
            "status": "running",
            "rounds": [],
        }

        previous_hash: Optional[str] = None
        previous_raw: Optional[Dict[str, Any]] = None
        previous_state: Optional[GameState] = None
        polls = 0
        action_count = 0
        status = "interrupted"
        last_state: Optional[GameState] = None

        try:
            while True:
                raw = self._raw_state()
                state = GameState(raw)
                digest = state_digest(raw)
                polls += 1

                if digest != previous_hash:
                    timestamp = _format_timestamp(self.now())
                    actions = infer_decision_actions(previous_raw, previous_state, raw, state)
                    if state.phase == GAME_OVER:
                        actions.append(_game_over_action(state))

                    for action in actions:
                        action_count += 1
                        action["index"] = action_count
                        action["timestamp"] = timestamp
                        action.setdefault("ante", state.ante)
                        action.setdefault("round", state.round_number)
                        _append_action(log, action)

                    log["updated_at"] = timestamp
                    log["status"] = "running"
                    log["current"] = state.summary()
                    self._write_log(log)

                    previous_hash = digest
                    previous_raw = raw
                    previous_state = state

                last_state = state
                if stop_on_game_over and state.phase == GAME_OVER:
                    status = _terminal_status(state)
                    log["status"] = status
                    log["terminal"] = state.summary()
                    log["updated_at"] = _format_timestamp(self.now())
                    self._write_log(log)
                    break
                if max_polls is not None and polls >= max_polls:
                    status = "max_polls"
                    log["status"] = status
                    log["updated_at"] = _format_timestamp(self.now())
                    self._write_log(log)
                    break
                if interval_seconds > 0:
                    time.sleep(interval_seconds)
        except KeyboardInterrupt:
            status = "interrupted"
            log["status"] = status
            log["updated_at"] = _format_timestamp(self.now())
            self._write_log(log)

        return self._result(status, polls, action_count, last_state, log)

    def _raw_state(self) -> Dict[str, Any]:
        raw = self.client.gamestate()
        if isinstance(raw, dict):
            return raw
        return {"value": raw}

    def _write_log(self, log: Dict[str, Any]) -> None:
        tmp_path = self.output_path.with_name(self.output_path.name + ".tmp")
        tmp_path.write_text(json.dumps(log, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        tmp_path.replace(self.output_path)

    def _result(
        self,
        status: str,
        polls: int,
        actions: int,
        last_state: Optional[GameState],
        log: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "output": str(self.output_path),
            "status": status,
            "polls": polls,
            "actions": actions,
            "rounds": len(log.get("rounds") or []),
            "last_state": last_state.summary() if last_state else None,
        }


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _terminal_status(state: GameState) -> str:
    if state.won is True:
        return "game_over_win"
    if state.won is False:
        return "game_over_loss"
    return "game_over"


def infer_action(
    previous_raw: Optional[Dict[str, Any]],
    previous_state: Optional[GameState],
    raw: Dict[str, Any],
    state: GameState,
) -> Optional[Dict[str, Any]]:
    if previous_raw is None or previous_state is None:
        return None

    if state.phase == "HAND_PLAYED" and state.hands_remaining < previous_state.hands_remaining:
        highlighted = _highlighted_cards(state.hand)
        if highlighted:
            return _action_record("play", highlighted, "highlighted_hand")

        removed = _removed_cards(previous_state.hand, state.hand)
        return _action_record("play", removed, "hand_delta")

    if state.discards_remaining < previous_state.discards_remaining:
        removed = _removed_cards(previous_state.hand, state.hand)
        added = _removed_cards(state.hand, previous_state.hand)
        action = _action_record("discard", removed, "hand_delta")
        if added:
            action["drawn_cards"] = [_card_record(card) for card in added]
            action["drawn_card_keys"] = [card_identity(card) for card in added]
        return action

    return None


def infer_decision_actions(
    previous_raw: Optional[Dict[str, Any]],
    previous_state: Optional[GameState],
    raw: Dict[str, Any],
    state: GameState,
) -> List[Dict[str, Any]]:
    if previous_raw is None or previous_state is None:
        return []
    if state.phase == GAME_OVER:
        return []

    actions: List[Dict[str, Any]] = []

    if (
        previous_state.phase == "BLIND_SELECT"
        and state.phase == "BLIND_SELECT"
        and state.money > previous_state.money
        and state.round_number == previous_state.round_number
    ):
        actions.append(
            {
                "method": "skip_blind",
                "reward_money": state.money - previous_state.money,
                "money_after": state.money,
                "confidence": "medium",
            }
        )

    if previous_state.phase == "SHOP" and state.phase == "BLIND_SELECT":
        actions.append({"method": "leave_shop", "money_after": state.money, "confidence": "high"})

    if previous_state.phase == "BLIND_SELECT" and state.phase != "BLIND_SELECT" and state.blind_requirement:
        actions.append(
            {
                "method": "select_blind",
                "required_score": state.blind_requirement,
                "money_after": state.money,
                "confidence": "high",
            }
        )

    play_or_discard = infer_action(previous_raw, previous_state, raw, state)
    if play_or_discard:
        actions.append(_compact_card_action(play_or_discard, state))

    shop_actions = _infer_shop_actions(previous_raw, previous_state, raw, state)
    actions.extend(shop_actions)
    actions.extend(_infer_consumable_actions(previous_raw, previous_state, raw, state))

    if _pack_was_skipped(previous_state, state) and not any(
        action.get("method") in {"choose_pack", "use_consumable"} for action in shop_actions
    ):
        actions.append({"method": "skip_pack", "money_after": state.money, "confidence": "medium"})

    return actions


def _append_action(log: Dict[str, Any], action: Dict[str, Any]) -> None:
    round_record = _round_record(log, action.get("ante", 0), action.get("round", 0))
    round_record["actions"].append(action)


def _round_record(log: Dict[str, Any], ante: int, round_number: int) -> Dict[str, Any]:
    for round_record in log["rounds"]:
        if round_record["ante"] == ante and round_record["round"] == round_number:
            return round_record
    round_record = {"ante": ante, "round": round_number, "actions": []}
    log["rounds"].append(round_record)
    return round_record


def _compact_card_action(action: Dict[str, Any], state: GameState) -> Dict[str, Any]:
    compact = {
        "method": action["method"],
        "cards": list(action.get("card_keys") or []),
        "confidence": action.get("confidence", "medium"),
        "score": state.score,
        "required_score": state.blind_requirement,
    }
    drawn = action.get("drawn_card_keys") or []
    if drawn:
        compact["drawn"] = list(drawn)
    return compact


def _infer_shop_actions(
    previous_raw: Dict[str, Any],
    previous_state: GameState,
    raw: Dict[str, Any],
    state: GameState,
) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    previous_jokers = previous_state.jokers
    current_jokers = state.jokers
    previous_consumables = previous_state.consumables
    current_consumables = state.consumables

    previous_pack_cards = _area_cards(previous_raw, "packs")
    current_pack_cards = _area_cards(raw, "packs")
    bought_pack = _removed_cards(previous_pack_cards, current_pack_cards)
    for pack in bought_pack:
        if previous_state.money > state.money or "BOOSTER" in state.phase:
            actions.append(_item_action("buy_pack", pack, previous_state, state))

    previous_vouchers = _area_cards(previous_raw, "vouchers")
    current_vouchers = _area_cards(raw, "vouchers")
    bought_vouchers = _removed_cards(previous_vouchers, current_vouchers)
    for voucher in bought_vouchers:
        if previous_state.money > state.money or "VOUCHER" in state.phase:
            actions.append(_item_action("buy_voucher", voucher, previous_state, state))

    added_jokers = _added_cards(previous_jokers, current_jokers)
    removed_jokers = _removed_cards(previous_jokers, current_jokers)
    for joker in added_jokers:
        method = _item_gain_method(previous_state, state)
        actions.append(_item_action(method, joker, previous_state, state))
    for joker in removed_jokers:
        if state.money >= previous_state.money:
            actions.append(_item_action("sell", joker, previous_state, state))

    added_consumables = _added_cards(previous_consumables, current_consumables)
    for consumable in added_consumables:
        method = _item_gain_method(previous_state, state)
        actions.append(_item_action(method, consumable, previous_state, state))

    if _shop_rerolled(previous_raw, previous_state, raw, state, actions):
        actions.append({"method": "reroll_shop", "money_after": state.money, "confidence": "medium"})

    return actions


def _infer_consumable_actions(
    previous_raw: Dict[str, Any],
    previous_state: GameState,
    raw: Dict[str, Any],
    state: GameState,
) -> List[Dict[str, Any]]:
    removed = _removed_cards(previous_state.consumables, state.consumables)
    if not removed:
        return []

    actions: List[Dict[str, Any]] = []
    cards_changed = _changed_hand_cards(previous_state.hand, state.hand)
    for item in removed:
        action = _item_action("use_consumable", item, previous_state, state)
        if cards_changed:
            action["cards_changed"] = cards_changed
        actions.append(action)
    return actions


def _item_gain_method(previous_state: GameState, state: GameState) -> str:
    if "BOOSTER" in previous_state.phase or "BOOSTER" in state.phase:
        return "choose_pack"
    if previous_state.phase == "SHOP" or state.phase == "SHOP":
        return "buy"
    return "choose_pack"


def _item_action(method: str, item: Dict[str, Any], previous_state: GameState, state: GameState) -> Dict[str, Any]:
    action = {
        "method": method,
        "item": item_name(item),
        "money_after": state.money,
        "confidence": "high",
    }
    key = str(item.get("key") or "")
    if key:
        action["item_key"] = key
    money_delta = state.money - previous_state.money
    if money_delta:
        action["money_delta"] = money_delta
    return action


def _game_over_action(state: GameState) -> Dict[str, Any]:
    return {
        "method": "game_over",
        "status": _terminal_status(state),
        "score": state.score,
        "required_score": state.blind_requirement,
        "confidence": "high",
    }


def _area_cards(raw: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = raw.get(key)
    if isinstance(value, dict):
        cards = value.get("cards")
        if isinstance(cards, list):
            return [card for card in cards if isinstance(card, dict)]
    if isinstance(value, list):
        return [card for card in value if isinstance(card, dict)]
    return []


def _added_cards(previous_cards: List[Dict[str, Any]], current_cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return _removed_cards(current_cards, previous_cards)


def _shop_rerolled(
    previous_raw: Dict[str, Any],
    previous_state: GameState,
    raw: Dict[str, Any],
    state: GameState,
    actions: List[Dict[str, Any]],
) -> bool:
    if actions or previous_state.phase != "SHOP" or state.phase != "SHOP":
        return False
    previous_shop = [card_identity(card) for card in previous_state.shop_cards()]
    current_shop = [card_identity(card) for card in state.shop_cards()]
    if not previous_shop or not current_shop:
        return False
    previous_pack = [card_identity(card) for card in _area_cards(previous_raw, "packs")]
    current_pack = [card_identity(card) for card in _area_cards(raw, "packs")]
    return previous_shop != current_shop or previous_pack != current_pack


def _pack_was_skipped(previous_state: GameState, state: GameState) -> bool:
    return "BOOSTER" in previous_state.phase and state.phase == "SHOP"


def _changed_hand_cards(previous_cards: List[Dict[str, Any]], current_cards: List[Dict[str, Any]]) -> List[str]:
    changed: List[str] = []
    current_by_id = {_card_token(card): card for card in current_cards}
    for previous_card in previous_cards:
        current_card = current_by_id.get(_card_token(previous_card))
        if not current_card:
            continue
        if card_identity(previous_card) != card_identity(current_card):
            changed.append(card_identity(current_card))
    return changed


def _action_record(method: str, cards: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
    confidence = "high" if cards else "low"
    return {
        "method": method,
        "cards": [_card_record(card) for card in cards],
        "card_keys": [card_identity(card) for card in cards],
        "source": source,
        "confidence": confidence,
    }


def _card_record(card: Dict[str, Any]) -> Dict[str, Any]:
    record: Dict[str, Any] = {"key": card_identity(card)}
    if card.get("id") is not None:
        record["id"] = card.get("id")
    rank = card_rank(card)
    suit = card_suit(card)
    if rank:
        record["rank"] = rank
    if suit:
        record["suit"] = suit
    return record


def _highlighted_cards(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [card for card in cards if _is_highlighted(card)]


def _is_highlighted(card: Dict[str, Any]) -> bool:
    state = card.get("state")
    return isinstance(state, dict) and state.get("highlight") is True


def _removed_cards(
    previous_cards: List[Dict[str, Any]], current_cards: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    current_tokens = [_card_token(card) for card in current_cards]
    removed: List[Dict[str, Any]] = []
    for card in previous_cards:
        token = _card_token(card)
        if token in current_tokens:
            current_tokens.remove(token)
        else:
            removed.append(card)
    return removed


def _card_token(card: Dict[str, Any]) -> Tuple[str, str]:
    if card.get("id") is not None:
        return ("id", str(card.get("id")))
    return ("key", card_identity(card))
