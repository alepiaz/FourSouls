from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.refs import CardId, CardRef

# ── Card ID constants ─────────────────────────────────────────────────────────

FLY    = CardId("FLY")
GAPER  = CardId("GAPER")
SPIDER = CardId("SPIDER")
HORF   = CardId("HORF")   # soul monster

# ── Blueprint ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class MonsterDef:
    card_id: CardId
    base_hp: int
    evade: int          # minimum roll to hit
    reward_cents: int
    has_soul: bool

# ── Registry ──────────────────────────────────────────────────────────────────

_REGISTRY: Dict[CardId, MonsterDef] = {
    FLY:    MonsterDef(card_id=FLY,    base_hp=1, evade=1, reward_cents=0,  has_soul=False),
    GAPER:  MonsterDef(card_id=GAPER,  base_hp=2, evade=1, reward_cents=5,  has_soul=False),
    SPIDER: MonsterDef(card_id=SPIDER, base_hp=2, evade=2, reward_cents=5,  has_soul=False),
    HORF:   MonsterDef(card_id=HORF,   base_hp=2, evade=2, reward_cents=10, has_soul=True),
}

# Used when a CardRef has no card_id or an unrecognised one (e.g. test stubs).
_DEFAULT = MonsterDef(
    card_id=CardId("__default__"),
    base_hp=1,
    evade=1,
    reward_cents=0,
    has_soul=False,
)

# ── Factory ───────────────────────────────────────────────────────────────────

def make_monster_in_play(card_ref: CardRef) -> MonsterInPlay:
    """Instantiate runtime monster state from a CardRef using the registry."""
    defn = (
        _REGISTRY.get(card_ref.card_id, _DEFAULT)
        if card_ref.card_id is not None
        else _DEFAULT
    )
    return MonsterInPlay(
        card_ref=card_ref,
        base_hp=defn.base_hp,
        current_hp=defn.base_hp,
        evade=defn.evade,
        reward_cents=defn.reward_cents,
        has_soul=defn.has_soul,
    )
