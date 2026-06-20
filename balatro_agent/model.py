from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


UNKNOWN_PHASE = "UNKNOWN"


def normalize_phase(value: Any) -> str:
    if value is None:
        return UNKNOWN_PHASE
    text = str(value).strip().upper()
    if not text:
        return UNKNOWN_PHASE
    return text.replace(" ", "_").replace("-", "_")


def _path_get(raw: Dict[str, Any], path: Sequence[str]) -> Any:
    current: Any = raw
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _first_present(raw: Dict[str, Any], paths: Iterable[Sequence[str]]) -> Any:
    for path in paths:
        value = _path_get(raw, path)
        if value is not None:
            return value
    return None


def _as_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item if isinstance(item, dict) else {"value": item} for item in value]
    if isinstance(value, dict):
        return _as_list(value.get("cards"))
    return []


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
    text = str(value).strip().lower()
    if text in {"true", "yes", "won", "win", "1"}:
        return True
    if text in {"false", "no", "lost", "loss", "0"}:
        return False
    return None


@dataclass
class GameState:
    """BalatroBot JSON 游戏状态的轻量封装。

    BalatroBot 变化很快，本地 mod 也可能添加字段。这个封装保持宽松解析，
    同时为决策层提供稳定的辅助方法。
    """

    raw: Dict[str, Any]

    @property
    def phase(self) -> str:
        return normalize_phase(
            _first_present(
                self.raw,
                [
                    ("state",),
                    ("game_state",),
                    ("phase",),
                    ("screen",),
                    ("run", "state"),
                ],
            )
        )

    @property
    def money(self) -> int:
        return _as_int(
            _first_present(
                self.raw,
                [
                    ("money",),
                    ("dollars",),
                    ("cash",),
                    ("run", "money"),
                ],
            )
        )

    @property
    def ante(self) -> int:
        return _as_int(
            _first_present(
                self.raw,
                [("ante",), ("ante_num",), ("run", "ante"), ("blind", "ante")],
            )
        )

    @property
    def round_number(self) -> int:
        return _as_int(
            _first_present(
                self.raw,
                [("round_num",), ("round_number",), ("run", "round"), ("round",)],
            )
        )

    @property
    def hands_remaining(self) -> int:
        return _as_int(
            _first_present(
                self.raw,
                [
                    ("current_round", "hands_left"),
                    ("round", "hands_left"),
                    ("hands_left",),
                    ("hands",),
                ],
            ),
            default=0,
        )

    @property
    def discards_remaining(self) -> int:
        return _as_int(
            _first_present(
                self.raw,
                [
                    ("current_round", "discards_left"),
                    ("round", "discards_left"),
                    ("discards_left",),
                    ("discards",),
                ],
            ),
            default=0,
        )

    @property
    def score(self) -> int:
        return _as_int(
            _first_present(
                self.raw,
                [("score",), ("chips",), ("current_round", "score"), ("round", "chips")],
            )
        )

    @property
    def blind_requirement(self) -> int:
        direct = _first_present(
            self.raw,
            [
                ("blind", "chips"),
                ("blind", "score"),
                ("blind", "required_score"),
                ("blinds", "current", "score"),
                ("required_score",),
                ("current_round", "required_score"),
            ],
        )
        if direct is not None:
            return _as_int(direct)

        blinds = self.raw.get("blinds")
        if not isinstance(blinds, dict):
            return 0

        for blind in blinds.values():
            if not isinstance(blind, dict):
                continue
            if normalize_phase(blind.get("status")) != "CURRENT":
                continue
            score = blind.get("score")
            if score is not None:
                return _as_int(score)
        return 0

    @property
    def blind_name(self) -> str:
        value = _first_present(
            self.raw,
            [
                ("blind", "name"),
                ("blind", "label"),
                ("blind", "key"),
                ("blind_name",),
                ("blinds", "current", "name"),
                ("blinds", "current", "label"),
                ("blinds", "current", "key"),
            ],
        )
        if value is not None:
            return str(value)

        blinds = self.raw.get("blinds")
        if not isinstance(blinds, dict):
            return ""
        for blind in blinds.values():
            if not isinstance(blind, dict):
                continue
            if normalize_phase(blind.get("status")) != "CURRENT":
                continue
            return str(blind.get("name") or blind.get("label") or blind.get("key") or "")
        return ""

    @property
    def won(self) -> Optional[bool]:
        return _as_bool(_first_present(self.raw, [("won",), ("run", "won"), ("game", "won")]))

    @property
    def hand(self) -> List[Dict[str, Any]]:
        return _as_list(
            _first_present(
                self.raw,
                [
                    ("hand",),
                    ("hand_cards",),
                    ("cards", "hand"),
                    ("areas", "hand", "cards"),
                    ("G", "hand", "cards"),
                ],
            )
        )

    @property
    def jokers(self) -> List[Dict[str, Any]]:
        return _as_list(
            _first_present(
                self.raw,
                [
                    ("jokers",),
                    ("joker_cards",),
                    ("cards", "jokers"),
                    ("areas", "jokers", "cards"),
                ],
            )
        )

    @property
    def consumables(self) -> List[Dict[str, Any]]:
        return _as_list(
            _first_present(
                self.raw,
                [
                    ("consumables",),
                    ("consumeables",),
                    ("cards", "consumables"),
                    ("areas", "consumables", "cards"),
                ],
            )
        )

    @property
    def joker_limit(self) -> int:
        return _as_int(
            _first_present(
                self.raw,
                [
                    ("jokers", "limit"),
                    ("areas", "jokers", "limit"),
                ],
            ),
            default=len(self.jokers),
        )

    @property
    def consumable_limit(self) -> int:
        return _as_int(
            _first_present(
                self.raw,
                [
                    ("consumables", "limit"),
                    ("areas", "consumables", "limit"),
                ],
            ),
            default=len(self.consumables),
        )

    def shop_cards(self) -> List[Dict[str, Any]]:
        return _as_list(
            _first_present(
                self.raw,
                [
                    ("shop", "cards"),
                    ("shop_cards",),
                    ("shop", "jokers"),
                    ("areas", "shop", "cards"),
                ],
            )
        )

    def shop_vouchers(self) -> List[Dict[str, Any]]:
        return _as_list(
            _first_present(
                self.raw,
                [
                    ("vouchers", "cards"),
                    ("shop", "vouchers"),
                    ("shop_vouchers",),
                    ("areas", "vouchers", "cards"),
                ],
            )
        )

    def shop_packs(self) -> List[Dict[str, Any]]:
        return _as_list(
            _first_present(
                self.raw,
                [
                    ("packs", "cards"),
                    ("shop", "packs"),
                    ("shop_packs",),
                    ("areas", "packs", "cards"),
                ],
            )
        )

    def booster_choices(self) -> List[Dict[str, Any]]:
        return _as_list(
            _first_present(
                self.raw,
                [
                    ("booster", "cards"),
                    ("pack", "cards"),
                    ("pack_choices",),
                    ("areas", "pack", "cards"),
                ],
            )
        )

    @property
    def deck_cards(self) -> List[Dict[str, Any]]:
        return _as_list(
            _first_present(
                self.raw,
                [
                    ("cards", "cards"),
                    ("deck", "cards"),
                    ("deck_cards",),
                    ("cards", "deck"),
                    ("areas", "deck", "cards"),
                    ("G", "deck", "cards"),
                ],
            )
        )

    @property
    def discard_pile_cards(self) -> List[Dict[str, Any]]:
        return _as_list(
            _first_present(
                self.raw,
                [
                    ("discard_pile",),
                    ("discard", "cards"),
                    ("discard_pile", "cards"),
                    ("cards", "discard"),
                    ("areas", "discard", "cards"),
                    ("G", "discard", "cards"),
                ],
            )
        )

    @property
    def deck_card_count(self) -> int:
        return len(self.deck_cards)

    @property
    def discard_pile_card_count(self) -> int:
        return len(self.discard_pile_cards)

    def summary(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "ante": self.ante,
            "round": self.round_number,
            "money": self.money,
            "hands": self.hands_remaining,
            "discards": self.discards_remaining,
            "score": self.score,
            "required_score": self.blind_requirement,
            "blind_name": self.blind_name,
            "won": self.won,
            "jokers": len(self.jokers),
            "consumables": len(self.consumables),
            "hand_cards": [card_identity(card) for card in self.hand],
            "joker_keys": [str(joker.get("key") or item_name(joker)) for joker in self.jokers],
            "shop_cards": [item_name(item) for item in self.shop_cards()],
            "deck_cards_remaining": self.deck_card_count,
            "discard_pile_cards": [card_identity(card) for card in self.discard_pile_cards],
        }


@dataclass
class ActionProposal:
    method: str
    params: Dict[str, Any]
    score: float
    agent: str
    confidence: float = 1.0
    reasons: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "params": dict(self.params),
            "score": self.score,
            "agent": self.agent,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
        }


@dataclass
class Decision:
    state: GameState
    selected: ActionProposal
    proposals: List[ActionProposal]
    rejected: List[Dict[str, str]]

    def as_log_record(self) -> Dict[str, Any]:
        return {
            "state": self.state.summary(),
            "action": self.selected.as_dict(),
            "proposals": [proposal.as_dict() for proposal in self.proposals],
            "rejected": list(self.rejected),
        }


@dataclass
class Genome:
    weights: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    GENE_SPECS = {
        "play": (0.1, 3.0, 0.15, False),
        "discard": (0.1, 3.0, 0.15, False),
        "buy_joker": (0.1, 4.0, 0.2, False),
        "buy_consumable": (0.0, 4.0, 0.2, False),
        "buy_pack": (0.0, 3.0, 0.15, False),
        "buy_voucher": (0.0, 3.0, 0.15, False),
        "reroll": (0.0, 2.0, 0.1, False),
        "next_round": (0.0, 2.0, 0.1, False),
        "cash_reserve": (0.0, 100.0, 4.0, False),
        "risk": (0.0, 2.0, 0.1, False),
        "synergy": (0.0, 3.0, 0.15, False),
        "cash_reserve_ante_scale": (0.0, 10.0, 0.5, False),
        "joker_replacement_margin": (0.0, 30.0, 2.0, False),
        "xmult_priority_ante": (1.0, 8.0, 1.0, True),
        "consumable_empty_slot_bonus": (0.0, 3.0, 0.2, False),
        "value_hand": (0.0, 5.0, 0.25, False),
        "value_discard": (0.0, 5.0, 0.25, False),
        "value_money": (0.0, 0.5, 0.02, False),
        "value_joker": (0.0, 5.0, 0.25, False),
        "value_consumable": (0.0, 5.0, 0.25, False),
    }

    @classmethod
    def default(cls) -> "Genome":
        return cls(
            weights={
                "play": 1.0,
                "discard": 0.85,
                "buy_joker": 1.8,
                "buy_consumable": 0.90,
                "buy_pack": 0.35,
                "buy_voucher": 0.70,
                "reroll": 0.22,
                "next_round": 0.18,
                "cash_reserve": 5.0,
                "risk": 0.55,
                "synergy": 0.75,
                "cash_reserve_ante_scale": 1.0,
                "joker_replacement_margin": 10.0,
                "xmult_priority_ante": 4.0,
                "consumable_empty_slot_bonus": 1.5,
                "value_hand": 1.0,
                "value_discard": 0.5,
                "value_money": 0.02,
                "value_joker": 0.5,
                "value_consumable": 0.25,
            },
            metadata={"version": 3},
        )

    def weight(self, name: str, default: float = 1.0) -> float:
        value = self.weights.get(name, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def bounds(cls, name: str) -> Tuple[float, float]:
        lower, upper, _, _ = cls.GENE_SPECS.get(name, (-10.0, 10.0, 0.15, False))
        return lower, upper

    def mutated(
        self,
        rng: Any,
        sigma: Optional[float] = None,
        mutation_rate: float = 0.3,
    ) -> "Genome":
        keys = sorted(self.weights)
        mutation_count = max(1, min(len(keys), round(len(keys) * mutation_rate)))
        selected = set(rng.sample(keys, mutation_count))
        next_weights: Dict[str, float] = dict(self.weights)
        for key in selected:
            lower, upper, scale, integer = self.GENE_SPECS.get(key, (-10.0, 10.0, 0.15, False))
            mutated = float(self.weights[key]) + rng.gauss(0.0, sigma if sigma is not None else scale)
            mutated = min(upper, max(lower, mutated))
            if integer:
                mutated = float(round(mutated))
            next_weights[key] = round(mutated, 6)
        metadata = dict(self.metadata)
        metadata["parent_version"] = metadata.get("version", 1)
        return Genome(next_weights, metadata)

    def crossover(self, other: "Genome", rng: Any) -> "Genome":
        keys = sorted(set(self.weights) | set(other.weights))
        weights: Dict[str, float] = {}
        for key in keys:
            if key not in self.weights:
                weights[key] = other.weights[key]
            elif key not in other.weights:
                weights[key] = self.weights[key]
            else:
                weights[key] = self.weights[key] if rng.random() < 0.5 else other.weights[key]
        return Genome(weights, {"version": 3, "parents": 2})

    def to_json(self) -> str:
        return json.dumps(
            {"weights": self.weights, "metadata": self.metadata},
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, payload: str) -> "Genome":
        data = json.loads(payload)
        weights = dict(cls.default().weights)
        weights.update({str(key): float(value) for key, value in data["weights"].items()})
        return cls(
            weights=weights,
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def load(cls, path: Path) -> "Genome":
        return cls.from_json(path.read_text())

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json() + "\n")


def card_rank(card: Dict[str, Any]) -> str:
    value = _first_present(
        card,
        [
            ("rank",),
            ("value", "rank"),
            ("value",),
            ("label",),
            ("base", "rank"),
        ],
    )
    if value is None:
        name = str(card.get("name", card.get("id", ""))).upper()
        for rank in ("A", "K", "Q", "J", "T", "10", "9", "8", "7", "6", "5", "4", "3", "2"):
            if rank in name:
                return rank
        return ""
    return str(value).upper()


def card_identity(card: Dict[str, Any]) -> str:
    key = str(card.get("key") or "").upper()
    if key:
        return key
    suit = card_suit(card).upper()
    rank = card_rank(card)
    if suit and rank:
        return f"{suit}_{rank}"
    return rank or suit or item_name(card)


def card_rank_value(card: Dict[str, Any]) -> int:
    rank = card_rank(card)
    values = {
        "A": 14,
        "K": 13,
        "Q": 12,
        "J": 11,
        "T": 10,
        "10": 10,
        "9": 9,
        "8": 8,
        "7": 7,
        "6": 6,
        "5": 5,
        "4": 4,
        "3": 3,
        "2": 2,
    }
    return values.get(rank, 0)


def card_suit(card: Dict[str, Any]) -> str:
    value = _first_present(
        card,
        [
            ("suit",),
            ("value", "suit"),
            ("base", "suit"),
        ],
    )
    if value is None:
        name = str(card.get("name", card.get("label", card.get("id", "")))).upper()
        for suit in ("H", "D", "C", "S"):
            token = f"_{suit}"
            if token in name or name.endswith(suit):
                return suit
        return ""
    return str(value).upper()


def card_enhancement(card: Dict[str, Any]) -> str:
    value = _first_present(
        card,
        [
            ("modifier", "enhancement"),
            ("enhancement",),
        ],
    )
    if value is None:
        return ""
    return str(value).upper()


def item_cost(item: Dict[str, Any]) -> int:
    return _as_int(
        _first_present(item, [("cost", "buy"), ("cost",), ("price",), ("sell_cost",)]),
        default=0,
    )


def item_name(item: Dict[str, Any]) -> str:
    return str(item.get("name") or item.get("label") or item.get("key") or item.get("id") or "")


def item_type(item: Dict[str, Any]) -> str:
    raw = str(item.get("type") or item.get("kind") or item.get("set") or "")
    if raw:
        return raw.upper()
    key = str(item.get("key") or item.get("id") or "").lower()
    name = item_name(item).lower()
    if key.startswith("j_") or "joker" in name:
        return "JOKER"
    if key.startswith("v_") or "voucher" in name:
        return "VOUCHER"
    if key.startswith("c_") or "planet" in name or "tarot" in name or "spectral" in name:
        return "CONSUMABLE"
    if "pack" in name or "booster" in name:
        return "PACK"
    return "UNKNOWN"
