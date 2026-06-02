from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from balatro_agent.actions import GAME_OVER
from balatro_agent.model import GameState


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

        try:
            while True:
                raw = self._raw_state()
                state = GameState(raw)
                digest = state_digest(raw)
                polls += 1

                if not self.only_changes or digest != previous_hash:
                    self._append_snapshot(
                        raw,
                        state,
                        digest,
                        previous_hash,
                        snapshots,
                        polls,
                        started_at,
                    )
                    previous_hash = digest
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
