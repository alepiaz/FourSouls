from __future__ import annotations

from dataclasses import dataclass, field

from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.refs import CardRef


@dataclass(slots=True)
class GameZones:
    """All shared game zones. Owned by Game, not GameState."""

    loot_deck: DeckZone[CardRef]
    loot_discard: DiscardZone[CardRef]

    treasure_deck: DeckZone[CardRef]
    treasure_discard: DiscardZone[CardRef]

    monster_deck: DeckZone[CardRef]
    monster_discard: DiscardZone[CardRef]

    shop_slots: SlotsZone[CardRef]
    monster_slots: SlotsZone[CardRef]
