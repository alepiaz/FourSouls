from __future__ import annotations

from dataclasses import dataclass

from foursouls.model.effects import DrawLootEffect
from foursouls.model.game_state import GameState
from foursouls.model.turn_state import TurnPhase


LOOT1_LABEL = "LOOT_1"


def should_schedule_loot1(state: GameState) -> bool:
    return state.turn.phase == TurnPhase.START and not state.turn.loot1_scheduled


def make_loot1_effect(state: GameState) -> DrawLootEffect:
    return DrawLootEffect(player_id=state.active_player_id, n=1)


def mark_loot1_scheduled(state: GameState) -> None:
    state.turn.loot1_scheduled = True


def on_loot1_resolved(state: GameState) -> None:
    """
    When Loot 1 finishes resolving (even if it fizzles), we move into ACTION.
    """
    if state.turn.phase == TurnPhase.START:
        state.turn.phase = TurnPhase.ACTION
    state.turn.loot1_scheduled = False  # reset the scheduling flag for clarity


def begin_new_turn(state: GameState) -> None:
    state.turn.phase = TurnPhase.START
    state.turn.loot1_scheduled = False
    state.turn.attack_used = False
    state.turn.purchase_used = False
    state.turn.loot_play_used = False


def advance_turn(state: GameState) -> None:
    """
    End current turn and advance to next active player.
    """
    prev = state.active_player_id
    nxt = state.next_player_id(prev)
    state.active_player_id = nxt
    state.turn.number += 1
    begin_new_turn(state)
