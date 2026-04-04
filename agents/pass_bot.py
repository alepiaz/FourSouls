from __future__ import annotations

from typing import TYPE_CHECKING

from foursouls.model.commands import Command, EndTurn, PassPriority

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


def choose_command(game: Game) -> Command:
    """
    Minimal bot: take EndTurn if legal, otherwise pass.
    Drives the game through START (Loot1) → ACTION → EndTurn loop.
    """
    for cmd in game.legal_commands():
        if isinstance(cmd, EndTurn):
            return cmd
    return PassPriority()
