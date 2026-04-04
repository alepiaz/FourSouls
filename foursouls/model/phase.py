from __future__ import annotations

import enum
from dataclasses import dataclass


class Phase(enum.Enum):
    START = "START"
    ACTION = "ACTION"
    END = "END"


@dataclass(slots=True)
class TurnFlags:
    loot_plays_used: int = 0
    loot_plays_allowed: int = 1
    attack_used: bool = False
    purchase_used: bool = False

    def reset(self) -> None:
        self.loot_plays_used = 0
        self.loot_plays_allowed = 1
        self.attack_used = False
        self.purchase_used = False
