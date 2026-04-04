from __future__ import annotations

from dataclasses import dataclass
from typing import NewType, Optional

PlayerId = NewType("PlayerId", str)
CardId = NewType("CardId", str)
InstanceId = NewType("InstanceId", str)


@dataclass(frozen=True, slots=True)
class CardRef:
    """Reference to a specific card instance in the game."""
    instance_id: InstanceId
    card_id: Optional[CardId] = None  # None for placeholder/unknown cards

    def __str__(self) -> str:
        suffix = f"/{self.card_id}" if self.card_id else ""
        return f"CardRef({self.instance_id}{suffix})"