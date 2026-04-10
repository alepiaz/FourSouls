from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from foursouls.model.refs import CardId

# Base-game character card IDs.
ISAAC     = CardId("ISAAC")      # 4 HP
MAGDALENE = CardId("MAGDALENE")  # 6 HP
CAIN      = CardId("CAIN")       # 4 HP
EVE       = CardId("EVE")        # 2 HP


@dataclass(frozen=True, slots=True)
class CharacterDef:
    card_id: CardId
    base_hp: int
    attack: int


_REGISTRY: Dict[CardId, CharacterDef] = {
    ISAAC:     CharacterDef(card_id=ISAAC,     base_hp=4, attack=1),
    MAGDALENE: CharacterDef(card_id=MAGDALENE, base_hp=6, attack=1),
    CAIN:      CharacterDef(card_id=CAIN,      base_hp=4, attack=1),
    EVE:       CharacterDef(card_id=EVE,       base_hp=2, attack=1),
}

_DEFAULT = CharacterDef(card_id=CardId("__default__"), base_hp=4, attack=1)


def get_character_def(card_id: CardId) -> CharacterDef:
    return _REGISTRY.get(card_id, _DEFAULT)
