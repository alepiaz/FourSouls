from __future__ import annotations

from typing import TYPE_CHECKING

from foursouls.model.commands import AttackMonster, Command, EndTurn, PassPriority, RollCombat

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


def choose_command(game: Game) -> Command:
    """
    Combat-focused bot. Priority order within a turn:

    1. RollCombat  — keep rolling while combat is active.
    2. AttackMonster — declare an attack against the first available slot.
    3. EndTurn     — end the turn once combat is resolved and there is nothing else to do.
    4. PassPriority — fallback: drives stack resolution and START → ACTION transition.

    The bot does not play loot or buy from the shop; it exists solely to drive
    one complete combat exchange per turn.  Other bots (economy_bot, pass_bot)
    handle those actions in their own acceptance slices.
    """
    cmds = game.legal_commands()

    for cmd in cmds:
        if isinstance(cmd, RollCombat):
            return cmd

    for cmd in cmds:
        if isinstance(cmd, AttackMonster):
            return cmd

    for cmd in cmds:
        if isinstance(cmd, EndTurn):
            return cmd

    return PassPriority()
