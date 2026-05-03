from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict


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
    died_this_turn: bool = False
    # Off-turn extra loot plays granted to non-active players (e.g. opponent taps
    # their character on your turn).  Keyed by PlayerId (str); cleared each turn.
    extra_loot_plays: Dict[str, int] = field(default_factory=dict)

    def reset(self) -> None:
        self.loot_plays_used = 0
        self.loot_plays_allowed = 1
        self.attack_used = False
        self.purchase_used = False
        self.died_this_turn = False
        self.extra_loot_plays = {}
