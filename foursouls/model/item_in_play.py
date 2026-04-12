from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .refs import CardRef


@dataclass(slots=True)
class ItemInPlay:
    """A card on a player's board that can be tapped/untapped.

    eternal=True marks items that cannot be destroyed by the death penalty
    (e.g. the character card a player starts with).

    recharge_on controls when the item untaps each turn:
      "start_of_turn"  — default; untapped at the start of the owner's turn
      "end_of_turn"    — untapped at the end of the owner's turn (e.g. The D6)

    counters holds named counter stacks (e.g. {"charge": 9} for Dead Cat).
    """

    card_ref: CardRef
    is_tapped: bool = False
    eternal: bool = False
    recharge_on: str = "start_of_turn"
    counters: Dict[str, int] = field(default_factory=dict)

    def tap(self) -> None:
        self.is_tapped = True

    def untap(self) -> None:
        self.is_tapped = False
