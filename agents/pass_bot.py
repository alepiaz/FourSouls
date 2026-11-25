from __future__ import annotations

from typing import TYPE_CHECKING

from foursouls.model.commands import AttackMonsterDeck, PlaceRevealedMonster, Command, EndTurn, PassPriority

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


def choose_command(game: Game) -> Command:
    """
    Minimal bot: take EndTurn if legal, otherwise pass.
    Drives the game through START (Loot1) → ACTION → EndTurn loop.
    """
    commands = game.legal_commands()
    for cmd in commands:
        if isinstance(cmd, PlaceRevealedMonster):
            return cmd
        if isinstance(cmd, AttackMonsterDeck) and game.state.turn_flags.forced_deck_attacks:
            return cmd
    if game.combat is not None and game.combat.from_deck:
        from foursouls.model.commands import RollCombat
        for cmd in commands:
            if isinstance(cmd, RollCombat):
                return cmd
    for cmd in commands:
        if isinstance(cmd, EndTurn):
            return cmd
    return PassPriority()
