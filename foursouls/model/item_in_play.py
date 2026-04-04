from __future__ import annotations

from dataclasses import dataclass

from .refs import CardRef


@dataclass(slots=True)
class ItemInPlay:
    """A card on a player's board that can be tapped/untapped."""

    card_ref: CardRef
    is_tapped: bool = False

    def tap(self) -> None:
        self.is_tapped = True

    def untap(self) -> None:
        self.is_tapped = False
