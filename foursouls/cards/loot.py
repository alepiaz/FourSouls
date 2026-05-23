from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, ConfigDict

from foursouls.model.effects import Effect
from foursouls.model.refs import CardId
from foursouls.model.target import AnyTarget

# ── Card ID constants ─────────────────────────────────────────────────────────

LOOT_COIN        = CardId("LOOT_COIN")
TWO_CENTS        = CardId("TWO_CENTS")
THREE_CENTS      = CardId("THREE_CENTS")
FOUR_CENTS       = CardId("FOUR_CENTS")
NICKEL           = CardId("NICKEL")
BOMB_BANG        = CardId("BOMB!")
GOLD_BOMB_BANG_BANG = CardId("GOLD_BOMB!!")
SOUL_HEART       = CardId("SOUL_HEART")
BLANK_RUNE       = CardId("BLANK_RUNE")
BUTTER_BEAN      = CardId("BUTTER_BEAN")

# ── Blueprint ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class LootDef:
    card_id: CardId
    requires_target: bool = False
    allows_monster_target: bool = False
    allows_stack_target: bool = False
    make_effect: object = field(default=None, compare=False, hash=False)


# ── YAML schema (Pydantic) ────────────────────────────────────────────────────

class _LootEffect(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str


class _LootEntry(BaseModel):
    requires_target: bool = False
    allows_monster_target: bool = False
    allows_stack_target: bool = False
    effect: Optional[_LootEffect] = None


# ── Registry loader ───────────────────────────────────────────────────────────

def _load_registry() -> Dict[CardId, LootDef]:
    from foursouls.cards.loot_handlers import build_loot_effect

    data_path = Path(__file__).parent.parent / "data" / "loot.yaml"
    raw: dict = yaml.safe_load(data_path.read_text(encoding="utf-8"))

    registry: Dict[CardId, LootDef] = {}
    for card_id_str, entry_dict in raw.items():
        card_id = CardId(card_id_str)
        entry = _LootEntry.model_validate(entry_dict or {})
        registry[card_id] = LootDef(
            card_id=card_id,
            requires_target=entry.requires_target,
            allows_monster_target=entry.allows_monster_target,
            allows_stack_target=entry.allows_stack_target,
            make_effect=build_loot_effect(entry.effect.model_dump()) if entry.effect else None,
        )

    return registry


_LOOT_REGISTRY: Dict[CardId, LootDef] = _load_registry()


# ── Targeting metadata ────────────────────────────────────────────────────────

def requires_target(card_id: CardId) -> bool:
    defn = _LOOT_REGISTRY.get(card_id)
    return defn.requires_target if defn is not None else False


def allows_monster_target(card_id: CardId) -> bool:
    defn = _LOOT_REGISTRY.get(card_id)
    return defn.allows_monster_target if defn is not None else False


def allows_stack_target(card_id: CardId) -> bool:
    defn = _LOOT_REGISTRY.get(card_id)
    return defn.allows_stack_target if defn is not None else False


# ── Effect factory ────────────────────────────────────────────────────────────

def make_loot_effect(
    card_id: CardId,
    controller_id: Any,
    *,
    target: Optional[AnyTarget] = None,
    monster_slots: Any = None,
    rng: Any = None,
    loot_deck: Any = None,
    log: Any = None,
    stack: Any = None,
) -> Effect:
    """Return the resolved effect for a loot card played by controller_id."""
    defn = _LOOT_REGISTRY.get(card_id)
    if defn is None or defn.make_effect is None:
        raise ValueError(f"Unknown loot card_id: {card_id!r}")
    return defn.make_effect(
        controller_id,
        target=target,
        monster_slots=monster_slots,
        rng=rng,
        loot_deck=loot_deck,
        log=log,
        stack=stack,
    )
