from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict, Field

from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.refs import CardId, CardRef

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game
    from foursouls.model.effects import Effect

# Type aliases for monster trigger callbacks (used only for documentation;
# TYPE_CHECKING guards keep these from being imported at runtime).
#
#   on_death(game, roll) -> None          — fires after combat confirms kill
#   on_miss(game, roll) -> int            — returns (possibly modified) miss damage
#   on_would_take_combat_damage(game, roll, amount) -> int
#                                         — returns (possibly modified) hit damage
#   on_would_die(game) -> bool            — returns True if death is prevented

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
CARRION_QUEEN = CardId("CARRION_QUEEN")

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
    # Callable[[Game], Effect] — not part of equality or hash
    event_effect: object = field(default=None, compare=False, hash=False)
    # ── Sprint 13 trigger hooks (R13.1 substrate) ─────────────────────────────
    # None means "no trigger for this monster".  Callables are excluded from
    # equality and hashing so MonsterDef instances remain safely comparable.
    #
    # on_death(game, roll) -> None
    on_death: object = field(default=None, compare=False, hash=False)
    # on_miss(game, roll) -> int   (return value = final miss damage)
    on_miss: object = field(default=None, compare=False, hash=False)
    # on_would_take_combat_damage(game, roll, amount) -> int   (return = final damage)
    on_would_take_combat_damage: object = field(default=None, compare=False, hash=False)
    # on_would_die(game) -> bool   (return True = death prevented)
    on_would_die: object = field(default=None, compare=False, hash=False)


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
    on_death: Optional[_AbilityConfig] = None
    on_miss: Optional[_AbilityConfig] = None
    on_would_take_combat_damage: Optional[_AbilityConfig] = None
    on_would_die: Optional[_AbilityConfig] = None
    event_effect: Optional[_AbilityConfig] = None


# ── Registry loader ───────────────────────────────────────────────────────────

def _load_registry() -> Dict[CardId, MonsterDef]:
    from foursouls.cards.ability_handlers import build_trigger, build_event_effect

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
            event_effect=build_event_effect(entry.event_effect.model_dump()) if entry.event_effect else None,
            on_death=build_trigger(entry.on_death.model_dump()) if entry.on_death else None,
            on_miss=build_trigger(entry.on_miss.model_dump()) if entry.on_miss else None,
            on_would_take_combat_damage=build_trigger(entry.on_would_take_combat_damage.model_dump()) if entry.on_would_take_combat_damage else None,
            on_would_die=build_trigger(entry.on_would_die.model_dump()) if entry.on_would_die else None,
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
        # Sprint 13 R13.2: copy trigger hooks from the definition
        on_death=defn.on_death,
        on_miss=defn.on_miss,
        on_would_take_combat_damage=defn.on_would_take_combat_damage,
        on_would_die=defn.on_would_die,
    )
