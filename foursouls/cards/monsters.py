from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict, Field

from foursouls.model.abilities import AbilityDefinition
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.refs import CardId, CardRef

if TYPE_CHECKING:
    from foursouls.model.effects import Effect

# ── Card ID constants ─────────────────────────────────────────────────────────

DINGA         = CardId("DINGA")
ATTACK_FLY    = CardId("ATTACK_FLY")
BOOM_FLY      = CardId("BOOM_FLY")
CLOTTY        = CardId("CLOTTY")
MULLIBOIL     = CardId("MULLIBOIL")
FLY           = CardId("FLY")
GAPER         = CardId("GAPER")
SPIDER        = CardId("SPIDER")
HORF          = CardId("HORF")
BIG_SPIDER    = CardId("BIG_SPIDER")
BONY          = CardId("BONY")
MEGA_FATTY    = CardId("MEGA_FATTY")
CARRION_QUEEN = CardId("CARRION_QUEEN")
THE_BLOAT     = CardId("THE_BLOAT")
CURSED_PSY_HORF = CardId("CURSED_PSY_HORF")

# Boss card IDs
MONSTRO           = CardId("MONSTRO")            # Base Game V2
HEADLESS_HORSEMAN = CardId("HEADLESS_HORSEMAN")  # Four Souls+ V2

# Event card IDs
CURSED_CHEST         = CardId("CURSED_CHEST")         # bad: roll d6 — 1-3: 1 dmg; 4-5: 2 dmg; 6: stub
WE_NEED_TO_GO_DEEPER = CardId("WE_NEED_TO_GO_DEEPER") # good: reset attack_used

# ── Blueprint ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class MonsterDef:
    card_id: CardId
    base_hp: int
    evade: int
    attack: int
    has_soul: bool
    reward_coin: int = 0
    reward_loot: int = 0      # loot cards drawn by attacker on kill (e.g. Spider)
    reward_treasure: int = 0  # treasure cards drawn by attacker on kill (e.g. Headless Horseman)
    is_boss: bool = False
    is_event: bool = False
    abilities: tuple[AbilityDefinition, ...] = ()
    # Callable[[Game], Effect] — not part of equality or hash
    event_effect: object = field(default=None, compare=False, hash=False)


# ── YAML schema (Pydantic) ────────────────────────────────────────────────────

class _AbilityConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str


class _MonsterEntry(BaseModel):
    base_hp: int = 0
    evade: int = 0
    attack: int = 0
    has_soul: bool = False
    reward_coin: int = Field(default=0, ge=0)
    reward_loot: int = Field(default=0, ge=0)
    reward_treasure: int = Field(default=0, ge=0)
    is_boss: bool = False
    is_event: bool = False
    abilities: tuple[AbilityDefinition, ...] = ()
    event_effect: Optional[_AbilityConfig] = None


# ── Registry loader ───────────────────────────────────────────────────────────

def _load_registry() -> Dict[CardId, MonsterDef]:
    from foursouls.cards.ability_handlers import build_event_effect

    data_path = Path(__file__).parent.parent / "data" / "monsters.yaml"
    raw: dict = yaml.safe_load(data_path.read_text(encoding="utf-8"))

    registry: Dict[CardId, MonsterDef] = {}
    for card_id_str, entry_dict in raw.items():
        card_id = CardId(card_id_str)
        entry = _MonsterEntry.model_validate(entry_dict or {})

        registry[card_id] = MonsterDef(
            card_id=card_id,
            base_hp=entry.base_hp,
            evade=entry.evade,
            attack=entry.attack,
            has_soul=entry.has_soul,
            reward_coin=entry.reward_coin,
            reward_loot=entry.reward_loot,
            reward_treasure=entry.reward_treasure,
            is_boss=entry.is_boss,
            is_event=entry.is_event,
            abilities=entry.abilities,
            event_effect=(
                build_event_effect(entry.event_effect.model_dump())
                if entry.event_effect
                else None
            ),
        )

    return registry


_REGISTRY: Dict[CardId, MonsterDef] = _load_registry()

# Used when a CardRef has no card_id or an unrecognised one (e.g. test stubs).
_DEFAULT = MonsterDef(
    card_id=CardId("__default__"),
    base_hp=1,
    evade=1,
    attack=1,
    reward_coin=0,
    has_soul=False,
)

# ── Lookup ────────────────────────────────────────────────────────────────────

def get_monster_def(card_id: Optional[CardId]) -> MonsterDef:
    """Return the MonsterDef for a card_id, or _DEFAULT if unknown/None."""
    if card_id is None:
        return _DEFAULT
    return _REGISTRY.get(card_id, _DEFAULT)


# ── Factory ───────────────────────────────────────────────────────────────────

def make_monster_in_play(card_ref: CardRef) -> MonsterInPlay:
    """Instantiate runtime monster state from a CardRef using the registry."""
    defn = get_monster_def(card_ref.card_id)
    return MonsterInPlay(
        card_ref=card_ref,
        base_hp=defn.base_hp,
        current_hp=defn.base_hp,
        evade=defn.evade,
        reward_coin=defn.reward_coin,
        has_soul=defn.has_soul,
        attack=defn.attack,
        reward_loot=defn.reward_loot,
        reward_treasure=defn.reward_treasure,
        is_boss=defn.is_boss,
        is_event=defn.is_event,
        abilities=defn.abilities,
    )
