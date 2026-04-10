from __future__ import annotations

from typing import TYPE_CHECKING

from foursouls.engine.events import ActivePlayerChanged, ItemActivated, PhaseChanged, TurnEnded, TurnStarted
from foursouls.model.phase import Phase
from foursouls.rulesets.common.effects import DrawLoot1Effect, GrantExtraLootPlayEffect

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


def enter_start_phase(game: Game) -> None:
    """
    Transition into START phase for the current active player:
      - set phase = START
      - untap the active player's character (recharge)
      - emit TurnStarted
      - push Loot1 (draw 1 loot) onto the stack

    Requires game.zones to be initialised.
    """
    assert game.zones is not None, "enter_start_phase requires game.zones to be set up"
    game.state.phase = Phase.START
    active_id = game.state.active_player_id

    game.log.append(TurnStarted(
        turn_number=game.state.turn_number,
        player_id=active_id,
    ))

    # Recharge: untap character at the start of the active player's turn
    character = game.state.get_player(active_id).character
    if character is not None:
        character.untap()

    effect = DrawLoot1Effect(
        player_id=active_id,
        loot_deck=game.zones.loot_deck,
        log=game.log,
    )
    game.push_to_stack(
        controller_id=active_id,
        source="turn:start_phase",
        effect=effect,
        label="Loot1",
    )


def on_activate_character_ability(game: Game) -> None:
    """
    Pay the tap cost, log the activation, push GrantExtraLootPlay onto the
    stack, and give priority to the active player.
    """
    active_id = game.state.active_player_id
    game.state.get_player(active_id).character.tap()
    game.log.append(ItemActivated(player_id=active_id, source="character:tap_ability"))
    effect = GrantExtraLootPlayEffect(player_id=active_id)
    game.push_to_stack(
        controller_id=active_id,
        source="character:tap_ability",
        effect=effect,
        label="GrantExtraLootPlay",
    )
    game.priority.reset_to(active_id)


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

    # All players (including dead) heal to full and clear damage shields at end of every turn
    for player in state.players.values():
        player.hp = player.max_hp
        player.prevent_damage = 0

    # All monsters in slots also heal to full and clear damage shields at end of every turn
    if game.zones is not None:
        for idx in game.zones.monster_slots.filled_indices():
            monster = game.zones.monster_slots.get(idx)
            if monster is not None:
                monster.current_hp = monster.base_hp
                monster.prevent_damage = 0

    # Discard down to 10
    if len(active.hand) > 10:
        del active.hand[10:]

    game.log.append(TurnEnded(player_id=old_active_id, turn_number=old_turn_number))

    # Advance turn
    next_id = state.next_player_id(old_active_id)
    old_phase = state.phase  # capture before reset_for_new_turn overwrites it
    state.reset_for_new_turn(next_id)  # sets phase=START, increments turn_number, resets flags

    game.log.append(ActivePlayerChanged(old_player_id=old_active_id, new_player_id=next_id))
    game.log.append(PhaseChanged(old_phase=old_phase, new_phase=Phase.START))

    # Re-sync priority to new active player (reset_for_new_turn does not touch priority)
    game.priority.reset_to(next_id)

    # Clear any lingering combat context
    game.combat = None

    # Enter START phase: push Loot1 for the new active player
    enter_start_phase(game)
