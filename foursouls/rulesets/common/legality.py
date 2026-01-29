from __future__ import annotations

from foursouls.model.game_state import GameState
from foursouls.model.refs import PlayerId
from foursouls.model.turn_state import TurnPhase


def can_end_turn(
    state: GameState, *, stack_empty: bool, priority_player_id: PlayerId
) -> bool:
    """
    Sprint 1 legality:
    - End Turn only during ACTION phase
    - only when stack is empty
    - only when the active player currently has priority
    """
    return (
        state.turn.phase == TurnPhase.ACTION
        and stack_empty
        and priority_player_id == state.active_player_id
    )
