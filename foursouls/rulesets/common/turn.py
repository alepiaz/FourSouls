from __future__ import annotations

from typing import TYPE_CHECKING

from foursouls.engine.events import ActivePlayerChanged, PhaseChanged, TurnEnded
from foursouls.model.phase import Phase
from foursouls.rulesets.common.effects import DrawLoot1Effect

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


def enter_start_phase(game: Game) -> None:
    """
    Transition into START phase for the current active player:
      - set phase = START
      - untap the active player's character (recharge)
      - push Loot1 (draw 1 loot) onto the stack

    Requires game.zones to be initialised.
    """
    assert game.zones is not None, "enter_start_phase requires game.zones to be set up"
    game.state.phase = Phase.START
    active_id = game.state.active_player_id

    # Recharge: untap character at the start of the active player's turn
    character = game.state.get_player(active_id).character
    if character is not None:
        character.untap()

    effect = DrawLoot1Effect(player_id=active_id, loot_deck=game.zones.loot_deck)
    game.push_to_stack(
        controller_id=active_id,
        source="turn:start_phase",
        effect=effect,
        label="Loot1",
    )


def on_all_passed_empty_stack(game: Game) -> None:
    """
    Called from Game.step() after AllPlayersPassed fires with an empty stack.

    START  → advance to ACTION (Loot1 has resolved)
    ACTION → nothing; player must issue EndTurn explicitly
    END    → should not normally occur; no-op
    """
    if game.state.phase == Phase.START:
        game.log.append(PhaseChanged(old_phase=Phase.START, new_phase=Phase.ACTION))
        game.state.phase = Phase.ACTION


def on_end_turn(game: Game) -> None:
    """
    Execute end-of-turn sequence:
      1. Heal active player to full HP.
      2. Trim active player's hand to ≤ 10 cards.
      3. Emit TurnEnded.
      4. Advance active_player_id to next in turn order.
      5. Reset turn_number, turn_flags, and phase via reset_for_new_turn().
      6. Emit ActivePlayerChanged + PhaseChanged(ACTION→START).
      7. Reset priority to new active player.
      8. Enter START phase (queues Loot1 for new active player).
    """
    state = game.state
    old_active_id = state.active_player_id
    old_turn_number = state.turn_number
    active = state.get_player(old_active_id)

    # Heal to full
    active.hp = active.max_hp

    # Discard down to 10
    if len(active.hand) > 10:
        del active.hand[10:]

    game.log.append(TurnEnded(player_id=old_active_id, turn_number=old_turn_number))

    # Advance turn
    next_id = state.next_player_id(old_active_id)
    state.reset_for_new_turn(next_id)  # sets phase=START, increments turn_number, resets flags

    game.log.append(ActivePlayerChanged(old_player_id=old_active_id, new_player_id=next_id))
    game.log.append(PhaseChanged(old_phase=Phase.ACTION, new_phase=Phase.START))

    # Re-sync priority to new active player (reset_for_new_turn does not touch priority)
    game.priority.reset_to(next_id)

    # Enter START phase: push Loot1 for the new active player
    enter_start_phase(game)
