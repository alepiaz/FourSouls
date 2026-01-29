from __future__ import annotations

from dataclasses import dataclass
from typing import List

from foursouls.model.commands import Command, EndTurn, PassPriority
from foursouls.model.game_state import GameState
from foursouls.model.refs import PlayerId
from foursouls.rulesets.common.legality import can_end_turn


@dataclass(slots=True)
class BaseRuleset:
    """
    Sprint 1 rules (still minimal):
    - PASS always legal
    - END_TURN legal only when can_end_turn(...) is True
    """

    def legal_commands(
        self,
        ctx: GameState,
        *,
        stack_empty: bool,
        priority_player_id: PlayerId,
    ) -> List[Command]:
        cmds: List[Command] = [PassPriority()]
        if can_end_turn(
            ctx, stack_empty=stack_empty, priority_player_id=priority_player_id
        ):
            cmds.append(EndTurn())
        return cmds
