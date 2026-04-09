from __future__ import annotations

from dataclasses import dataclass

from .refs import CardRef


@dataclass(slots=True)
class ItemInPlay:
    """A card on a player's board that can be tapped/untapped.

    eternal=True marks items that cannot be destroyed by the death penalty
    (e.g. the character card a player starts with).
    """

    card_ref: CardRef
    is_tapped: bool = False
    eternal: bool = False

    def tap(self) -> None:
        self.is_tapped = True

    def untap(self) -> None:
        self.is_tapped = False
