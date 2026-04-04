from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List

from foursouls.model.commands import Command
from foursouls.rulesets.common.legality import legal_commands as _legal_commands

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


@dataclass(slots=True)
class BaseRuleset:
    def legal_commands(self, game: Game) -> List[Command]:
        return _legal_commands(game)