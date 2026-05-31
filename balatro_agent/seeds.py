from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_SEEDS = ["AGENT1", "AGENT2", "AGENT3"]


def load_seed_config(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text())
    cohorts = data.get("cohorts")
    if not isinstance(cohorts, dict):
        raise ValueError("seed config must contain a cohorts object")
    return data


def resolve_seed_list(
    explicit_seeds: Optional[List[str]],
    seed_config: Optional[Path],
    cohort: str,
) -> List[str]:
    if explicit_seeds:
        return explicit_seeds
    if seed_config is not None:
        config = load_seed_config(seed_config)
        seeds = config["cohorts"].get(cohort)
        if not isinstance(seeds, list) or not all(isinstance(seed, str) for seed in seeds):
            raise ValueError(f"seed cohort not found or invalid: {cohort}")
        return list(seeds)
    return list(DEFAULT_SEEDS)
