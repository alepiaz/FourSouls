from __future__ import annotations

from typing import List

from foursouls.engine.stack import Stack
from foursouls.model.commands import Command, EndTurn, PassPriority
from foursouls.model.game_state import GameState
from foursouls.model.phase import Phase


def legal_commands(state: GameState, stack: Stack) -> List[Command]:
    """
    Sprint 1 legality rules:
    - PassPriority: always legal.
    - EndTurn: legal only when phase is ACTION and the stack is empty.
    """
    cmds: List[Command] = [PassPriority()]

    if state.phase == Phase.ACTION and stack.empty():
        cmds.append(EndTurn())

    return cmds
