from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from foursouls.model.refs import CardId

# Base-game character card IDs.
ISAAC     = CardId("ISAAC")      # 2 HP
MAGDALENE = CardId("MAGDALENE")  # 2 HP
CAIN      = CardId("CAIN")       # 2 HP
EVE       = CardId("EVE")        # 2 HP


@dataclass(frozen=True, slots=True)
class CharacterDef:
    card_id: CardId
    base_hp: int
    attack: int
    # Eternal item this character starts with (None = no starting item).
    # The card_id here must resolve to a TreasureDef in TREASURE_REGISTRY.
    starting_eternal: Optional[CardId] = None


_REGISTRY: Dict[CardId, CharacterDef] = {
    ISAAC:     CharacterDef(card_id=ISAAC,     base_hp=2, attack=1, starting_eternal=CardId("THE_D6")),
    MAGDALENE: CharacterDef(card_id=MAGDALENE, base_hp=2, attack=1, starting_eternal=CardId("YUM_HEART")),
    CAIN:      CharacterDef(card_id=CAIN,      base_hp=2, attack=1, starting_eternal=CardId("SLEIGHT_OF_HAND")),
    EVE:       CharacterDef(card_id=EVE,       base_hp=2, attack=1, starting_eternal=CardId("THE_CURSE")),
}

_DEFAULT = CharacterDef(card_id=CardId("__default__"), base_hp=2, attack=1)


def get_character_def(card_id: CardId) -> CharacterDef:
    return _REGISTRY.get(card_id, _DEFAULT)
