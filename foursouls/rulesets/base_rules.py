from __future__ import annotations

from dataclasses import dataclass
from typing import List

from foursouls.model.commands import Command, PassPriority
from foursouls.model.game_state import GameState


@dataclass(slots=True)
class BaseRuleset:
    """
    Sprint 0 rules: only PASS is legal.
    Later this becomes a full ruleset with timing windows, etc.
    """

    def legal_commands(self, ctx: GameState) -> List[Command]:
        return [PassPriority()]
