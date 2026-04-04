from __future__ import annotations

import enum
from dataclasses import dataclass


class Phase(enum.Enum):
    START = "START"
    ACTION = "ACTION"
    END = "END"


@dataclass(slots=True)
class TurnFlags:
    loot_play_used: bool = False
    attack_used: bool = False
    purchase_used: bool = False

    def reset(self) -> None:
        self.loot_play_used = False
        self.attack_used = False
        self.purchase_used = False
