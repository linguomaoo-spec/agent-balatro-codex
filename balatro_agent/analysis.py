from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def summarize_jsonl_logs(path: Path) -> Dict[str, Any]:
    files = _jsonl_files(path)
    runs = [_summarize_file(file_path) for file_path in files]
    record_count = sum(run["steps"] for run in runs)
    win_count = sum(1 for run in runs if run["status"] == "game_over_win")
    loss_count = sum(1 for run in runs if run["status"] == "game_over_loss")
    return {
        "path": str(path),
        "run_count": len(runs),
        "record_count": record_count,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": win_count / len(runs) if runs else 0.0,
        "error_count": sum(run["error_count"] for run in runs),
        "rejected_count": sum(run["rejected_count"] for run in runs),
        "max_ante": max((run["max_ante"] for run in runs), default=0),
        "runs": runs,
    }


def _jsonl_files(path: Path) -> List[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        return []
    return sorted(file_path for file_path in path.rglob("*.jsonl") if file_path.is_file())


def _summarize_file(path: Path) -> Dict[str, Any]:
    records = list(_read_jsonl(path))
    states = [record.get("state") or {} for record in records]
    final_state = states[-1] if states else {}
    status = _status_from_state(final_state)
    error_records = [record for record in records if record.get("error")]
    rejected_count = sum(len(record.get("rejected") or []) for record in records)
    final_score = _as_int(final_state.get("score"))
    final_required = _as_int(final_state.get("required_score"))
    last_action = records[-1].get("action") if records else {}
    last_executed = records[-1].get("executed") if records else {}
    last_phase = str(final_state.get("phase") or "")
    return {
        "path": str(path),
        "steps": len(records),
        "status": status,
        "failure_phase": None if status == "game_over_win" else last_phase,
        "max_ante": max((_as_int(state.get("ante")) for state in states), default=0),
        "final_ante": _as_int(final_state.get("ante")),
        "final_money": _as_int(final_state.get("money")),
        "final_score": final_score,
        "final_required_score": final_required,
        "score_gap": max(0, final_required - final_score),
        "final_jokers": _count_value(final_state.get("jokers") or final_state.get("joker_count")),
        "last_phase": last_phase,
        "last_action": _method_name(last_action),
        "last_executed": _method_name(last_executed),
        "error_count": len(error_records),
        "error_methods": [_method_name(record.get("executed") or record.get("action")) for record in error_records],
        "rejected_count": rejected_count,
    }


def _read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open() as handle:
        for line in handle:
            text = line.strip()
            if text:
                yield json.loads(text)


def _status_from_state(state: Dict[str, Any]) -> str:
    phase = str(state.get("phase") or "").upper()
    won = state.get("won")
    if phase == "GAME_OVER":
        if won is True:
            return "game_over_win"
        if won is False:
            return "game_over_loss"
        return "game_over"
    return "incomplete"


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _count_value(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    return _as_int(value)


def _method_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("method") or "")
    return ""
