from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


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


def compare_eval_summaries(
    baseline: Dict[str, Any],
    candidate: Dict[str, Any],
    cohort: str = "dev",
) -> Dict[str, Any]:
    baseline_runs = _runs_by_seed(baseline.get("runs") or [])
    candidate_runs = _runs_by_seed(candidate.get("runs") or [])
    lost_wins = sorted(
        seed
        for seed, run in baseline_runs.items()
        if run.get("status") == "game_over_win"
        and candidate_runs.get(seed, {}).get("status") != "game_over_win"
    )
    deltas = {
        "run_count": _as_int(candidate.get("run_count")) - _as_int(baseline.get("run_count")),
        "win_rate": _as_float(candidate.get("win_rate")) - _as_float(baseline.get("win_rate")),
        "error_count": _as_int(candidate.get("error_count")) - _as_int(baseline.get("error_count")),
        "rejected_count": _as_int(candidate.get("rejected_count")) - _as_int(baseline.get("rejected_count")),
        "max_ante": _as_int(candidate.get("max_ante")) - _as_int(baseline.get("max_ante")),
    }
    failed_checks: List[str] = []
    if deltas["max_ante"] < 0:
        failed_checks.append("max_ante_regressed")
    if deltas["win_rate"] < 0:
        failed_checks.append("win_rate_regressed")
    if deltas["error_count"] > 0:
        failed_checks.append("error_count_increased")
    if lost_wins:
        failed_checks.append("lost_previous_win")
    if cohort == "heldout" and deltas["rejected_count"] > 0:
        failed_checks.append("heldout_rejected_count_increased")
    return {
        "cohort": cohort,
        "promote": not failed_checks,
        "failed_checks": failed_checks,
        "deltas": deltas,
        "lost_wins": lost_wins,
        "baseline": {
            "run_count": _as_int(baseline.get("run_count")),
            "win_rate": _as_float(baseline.get("win_rate")),
            "error_count": _as_int(baseline.get("error_count")),
            "rejected_count": _as_int(baseline.get("rejected_count")),
            "max_ante": _as_int(baseline.get("max_ante")),
        },
        "candidate": {
            "run_count": _as_int(candidate.get("run_count")),
            "win_rate": _as_float(candidate.get("win_rate")),
            "error_count": _as_int(candidate.get("error_count")),
            "rejected_count": _as_int(candidate.get("rejected_count")),
            "max_ante": _as_int(candidate.get("max_ante")),
        },
    }


def extract_replay_cases(path: Path, limit: int = 100) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for file_path in _jsonl_files(path):
        records = list(_read_jsonl(file_path))
        for index, record in enumerate(records):
            case_type = _case_type(record, index, len(records))
            if case_type is None:
                continue
            state = record.get("state") or {}
            score = _as_int(state.get("score"))
            required_score = _as_int(state.get("required_score"))
            cases.append(
                {
                    "case_type": case_type,
                    "source": str(file_path),
                    "step_index": index,
                    "phase": str(state.get("phase") or ""),
                    "ante": _as_int(state.get("ante")),
                    "money": _as_int(state.get("money")),
                    "jokers": _count_value(state.get("jokers") or state.get("joker_count")),
                    "score": score,
                    "required_score": required_score,
                    "score_gap": max(0, required_score - score),
                    "won": state.get("won"),
                    "action": _method_name(record.get("action")),
                    "executed": _method_name(record.get("executed")),
                    "hands": _as_int(state.get("hands")),
                    "discards": _as_int(state.get("discards")),
                    "action_params": _params_dict(record.get("action")),
                    "executed_params": _params_dict(record.get("executed")),
                    "proposal_count": len(record.get("proposals") or []),
                    "agents": _proposal_agents(record.get("proposals") or []),
                    "error_name": _error_name(record.get("error")),
                    "rejected_count": len(record.get("rejected") or []),
                }
            )
            if len(cases) >= limit:
                return cases
    return cases


def write_replay_cases(log_dir: Path, output: Path, limit: int = 100) -> Dict[str, Any]:
    cases = extract_replay_cases(log_dir, limit=limit)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as handle:
        for case in cases:
            handle.write(json.dumps(case, sort_keys=True) + "\n")
    return {"output": str(output), "case_count": len(cases)}


def load_replay_cases(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return list(_read_jsonl(path))


def query_replay_cases(
    cases: Iterable[Dict[str, Any]],
    phase: Optional[str] = None,
    case_type: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    filtered = []
    phase_filter = str(phase or "").upper()
    type_filter = str(case_type or "")
    for case in cases:
        if phase_filter and str(case.get("phase") or "").upper() != phase_filter:
            continue
        if type_filter and str(case.get("case_type") or "") != type_filter:
            continue
        filtered.append(case)
    filtered.sort(key=_replay_relevance_score, reverse=True)
    return filtered[: max(0, limit)]


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
        "steps": sum(1 for record in records if not record.get("terminal")),
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


def _runs_by_seed(runs: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for run in runs:
        seed = _seed_from_path(str(run.get("path") or ""))
        if seed:
            result[seed] = run
    return result


def _seed_from_path(path: str) -> str:
    name = Path(path).stem
    if not name:
        return ""
    return name


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


def _case_type(record: Dict[str, Any], index: int, total: int) -> Optional[str]:
    if record.get("error"):
        return "error"
    state = record.get("state") or {}
    if index == total - 1 and str(state.get("phase") or "").upper() == "GAME_OVER":
        if state.get("won") is True:
            return "terminal_win"
        if state.get("won") is False:
            return "terminal_loss"
        return "terminal_unknown"
    if _is_decision_case(record):
        return "decision"
    return None


def _is_decision_case(record: Dict[str, Any]) -> bool:
    state = record.get("state") or {}
    required_score = _as_int(state.get("required_score"))
    score = _as_int(state.get("score"))
    score_gap = max(0, required_score - score)
    if score_gap > 0 and _as_int(state.get("hands")) <= 1:
        return True
    if record.get("rejected"):
        return True
    return False


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _count_value(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    return _as_int(value)


def _method_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("method") or "")
    return ""


def _params_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get("params"), dict):
        return dict(value["params"])
    return {}


def _proposal_agents(proposals: Iterable[Any]) -> List[str]:
    agents = []
    for proposal in proposals:
        if isinstance(proposal, dict):
            agent = str(proposal.get("agent") or "")
            if agent and agent not in agents:
                agents.append(agent)
    return agents


def _replay_relevance_score(case: Dict[str, Any]) -> float:
    type_bonus = {
        "error": 1000.0,
        "terminal_loss": 600.0,
        "decision": 300.0,
        "terminal_unknown": 100.0,
        "terminal_win": 50.0,
    }.get(str(case.get("case_type") or ""), 0.0)
    return (
        type_bonus
        + _as_int(case.get("rejected_count")) * 50.0
        + _as_int(case.get("score_gap")) * 0.1
        + _as_int(case.get("ante")) * 5.0
    )


def _error_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("code") or "")
    return ""
