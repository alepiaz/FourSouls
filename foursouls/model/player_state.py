from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .item_in_play import ItemInPlay
from .refs import CardRef, PlayerId


@dataclass(slots=True)
class PlayerState:
    player_id: PlayerId
    max_hp: int
    hp: int
    cents: int = 0
    attack: int = 1         # base attack from character definition
    attack_bonus: int = 0   # bonus from items/effects

    hand: List[CardRef] = field(default_factory=list)
    character: Optional[ItemInPlay] = None          # character card in play
    items: List[CardRef] = field(default_factory=list)  # treasures/trinkets/etc in play
    souls: List[CardRef] = field(default_factory=list)  # collected souls (bosses/bonus)

    def __post_init__(self) -> None:
        if self.max_hp <= 0:
            raise ValueError("max_hp must be > 0")
        if not (0 <= self.hp <= self.max_hp):
            raise ValueError("hp must be between 0 and max_hp")

    def is_alive(self) -> bool:
        return self.hp > 0

    def gain_treasure(self, ref: CardRef) -> None:
        """Move a treasure card into this player's treasure area."""
        self.items.append(ref)

    @property
    def treasures(self) -> List[CardRef]:
        """Read-only view of the player's treasure area (alias for items)."""
        return self.items