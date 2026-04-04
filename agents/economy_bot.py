from __future__ import annotations

from typing import TYPE_CHECKING

from foursouls.model.commands import BuyShop, Command, EndTurn, PassPriority, PlayLoot

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


def choose_command(game: Game) -> Command:
    """
    Shop-aware bot. Priority order within a turn:

    1. BuyShop — buy from the lowest-index legal slot (first affordable slot).
    2. PlayLoot — play the first real loot card in hand (card_id is not None).
       Placeholder cards (no card_id) are skipped; they have no resolvable effect.
    3. EndTurn — end the turn when nothing else is left to do.
    4. PassPriority — fallback (drives stack resolution, START → ACTION transition).

    This bot naturally drives:
      START (Loot1 resolves via passes) → ACTION →
      play coin(s) to build cents → BuyShop → EndTurn
    """
    cmds = game.legal_commands()

    for cmd in cmds:
        if isinstance(cmd, BuyShop):
            return cmd

    for cmd in cmds:
        if isinstance(cmd, PlayLoot) and cmd.card_ref.card_id is not None:
            return cmd

    for cmd in cmds:
        if isinstance(cmd, EndTurn):
            return cmd

    return PassPriority()
