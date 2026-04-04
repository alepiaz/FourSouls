from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

PlayerId = NewType("PlayerId", str)
CardId = NewType("CardId", str)
InstanceId = NewType("InstanceId", str)


@dataclass(frozen=True, slots=True)
class CardRef:
    """Reference to a specific card instance in the game."""
    instance_id: InstanceId

    def __str__(self) -> str:
        return f"CardRef({self.instance_id})"