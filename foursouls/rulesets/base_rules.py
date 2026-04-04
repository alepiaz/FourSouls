from __future__ import annotations

from dataclasses import dataclass
from typing import List

from foursouls.engine.stack import Stack
from foursouls.model.commands import Command
from foursouls.model.game_state import GameState
from foursouls.rulesets.common.legality import legal_commands as _legal_commands


@dataclass(slots=True)
class BaseRuleset:
    def legal_commands(self, ctx: GameState, stack: Stack) -> List[Command]:
        return _legal_commands(ctx, stack)