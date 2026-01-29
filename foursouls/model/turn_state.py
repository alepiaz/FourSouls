from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TurnPhase(str, Enum):
    START = "START"
    ACTION = "ACTION"
    END = "END"


@dataclass(slots=True)
class TurnState:
    """
    Data-only container for turn-related state.
    Rules will mutate these fields; model does not enforce game rules.
    """

    number: int = 1
    phase: TurnPhase = TurnPhase.START

    # Start-of-turn automation
    loot1_scheduled: bool = False

    # Placeholders for later legality rules
    attack_used: bool = False
    purchase_used: bool = False
    loot_play_used: bool = False
