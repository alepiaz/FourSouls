from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

from foursouls.model.refs import CardId

# ── Card ID constants ─────────────────────────────────────────────────────────

DRY_BABY        = CardId("DRY_BABY")
EYE_OF_GREED    = CardId("EYE_OF_GREED")
THE_DEAD_CAT    = CardId("THE_DEAD_CAT")
MAMA_MEGA       = CardId("MAMA_MEGA")
TECH_X          = CardId("TECH_X")
MAGIC_MUSHROOM  = CardId("MAGIC_MUSHROOM")
MEAT_BANG       = CardId("MEAT!")
LUCKY_FOOT      = CardId("LUCKY_FOOT")
LIL_BATTERY     = CardId("LIL_BATTERY")

# Starting Eternals
THE_D6          = CardId("THE_D6")
YUM_HEART       = CardId("YUM_HEART")
SLEIGHT_OF_HAND = CardId("SLEIGHT_OF_HAND")
THE_CURSE       = CardId("THE_CURSE")


# ── Blueprint ─────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class TreasureDef:
    """Definition of a treasure card.

    Instances are singletons (one per card type); runtime state lives in
    ItemInPlay. All callable hooks are optional and default to None (no-op).

    recharge_on controls when tapped copies untap each turn:
      "start_of_turn"  — default
      "end_of_turn"    — e.g. The D6, Yum Heart, Sleight Of Hand, The Curse

    is_one_use=True: the item is destroyed when its tap effect resolves.

    eternal=True: item cannot be destroyed or discarded (starting Eternals).

    is_guppy=True: counts toward the 2-Guppy threshold for Soul of Guppy.

    tap_target_type controls how legality emits ActivateItem commands:
      None              — no target; emit a single ActivateItem
      "player"          — emit one ActivateItem per player
      "player_or_monster" — emit one per player + one per occupied non-event slot

    make_tap_effect(target, game) → Effect: produces the Effect pushed onto
      the stack when the item is activated. None means the tap is a no-op stub.
    """

    card_id: CardId
    name: str
    recharge_on: str = "start_of_turn"
    is_one_use: bool = False
    eternal: bool = False
    is_guppy: bool = False
    tap_effect_description: Optional[str] = None
    tap_target_type: Optional[str] = field(default=None, compare=False)
    make_tap_effect: Optional[Callable] = field(default=None, compare=False)
    on_enters_play: Optional[Callable] = field(default=None, compare=False)
    on_start_of_turn: Optional[Callable] = field(default=None, compare=False)
    on_roll: Optional[Callable] = field(default=None, compare=False)
    on_character_tap: Optional[Callable] = field(default=None, compare=False)
    starting_counters: Dict[str, int] = field(default_factory=dict)


# ── YAML schema (Pydantic) ────────────────────────────────────────────────────

class _TreasureEffect(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str


class _TreasureHook(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str


class _TreasureEntry(BaseModel):
    name: str
    recharge_on: str = "start_of_turn"
    is_one_use: bool = False
    eternal: bool = False
    is_guppy: bool = False
    tap_target_type: Optional[str] = None
    tap_effect_description: Optional[str] = None
    tap_effect: Optional[_TreasureEffect] = None
    on_enters_play: Optional[_TreasureHook] = None
    on_start_of_turn: Optional[_TreasureHook] = None
    on_roll: Optional[_TreasureHook] = None
    on_character_tap: Optional[_TreasureHook] = None
    starting_counters: Dict[str, int] = Field(default_factory=dict)


# ── Registry loader ───────────────────────────────────────────────────────────

def _load_registry() -> Dict[CardId, TreasureDef]:
    from foursouls.cards.treasure_handlers import build_tap_effect, build_lifecycle_hook

    data_path = Path(__file__).parent.parent / "data" / "treasures.yaml"
    raw: dict = yaml.safe_load(data_path.read_text(encoding="utf-8"))

    registry: Dict[CardId, TreasureDef] = {}
    for card_id_str, entry_dict in raw.items():
        card_id = CardId(card_id_str)
        entry = _TreasureEntry.model_validate(entry_dict or {})

        registry[card_id] = TreasureDef(
            card_id=card_id,
            name=entry.name,
            recharge_on=entry.recharge_on,
            is_one_use=entry.is_one_use,
            eternal=entry.eternal,
            is_guppy=entry.is_guppy,
            tap_target_type=entry.tap_target_type,
            tap_effect_description=entry.tap_effect_description,
            make_tap_effect=build_tap_effect(entry.tap_effect.model_dump()) if entry.tap_effect else None,
            on_enters_play=build_lifecycle_hook("on_enters_play", entry.on_enters_play.model_dump()) if entry.on_enters_play else None,
            on_start_of_turn=build_lifecycle_hook("on_start_of_turn", entry.on_start_of_turn.model_dump()) if entry.on_start_of_turn else None,
            on_roll=build_lifecycle_hook("on_roll", entry.on_roll.model_dump()) if entry.on_roll else None,
            on_character_tap=build_lifecycle_hook("on_character_tap", entry.on_character_tap.model_dump()) if entry.on_character_tap else None,
            starting_counters=entry.starting_counters,
        )

    return registry


TREASURE_REGISTRY: Dict[CardId, TreasureDef] = _load_registry()
