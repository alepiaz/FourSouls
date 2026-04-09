from __future__ import annotations

from typing import TYPE_CHECKING

from foursouls.cards.monsters import make_monster_in_play
from foursouls.engine.events import (
    CoinsGained,
    CombatEntered,
    CombatRollResult,
    DamageDealt,
    DeathPenaltyPaid,
    EffectFizzled,
    GameWon,
    MonsterDied,
    PhaseChanged,
    PlayerDied,
    SoulGranted,
)
from foursouls.model.phase import Phase
from foursouls.model.combat_state import CombatState

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game

SOULS_TO_WIN = 4


def enter_combat(game: Game, slot_index: int) -> None:
    """
    Declare an attack against the monster in slot_index.

    Preconditions (caller must have validated via legal_commands):
    - game.zones is not None
    - slot is occupied
    - attack_used is False
    - game.combat is None

    Post-conditions:
    - attack_used = True
    - game.combat is a fresh CombatState for this attacker/slot
    - CombatEntered event is logged
    - priority resets to the active player
    """
    assert game.zones is not None
    monster = game.zones.monster_slots.get(slot_index)
    assert monster is not None, f"Monster slot {slot_index} is empty"

    attacker_id = game.state.active_player_id
    game.state.turn_flags.attack_used = True

    game.combat = CombatState(
        attacker_id=attacker_id,
        defender_slot=slot_index,
        monster_ref=monster.card_ref,
    )

    monster_name = str(monster.card_ref.card_id or "unknown")
    game.log.append(CombatEntered(
        attacker_id=attacker_id,
        defender_slot=slot_index,
        monster_id=monster.card_ref.card_id,
        monster_name=monster_name,
        monster_hp=monster.current_hp,
        monster_evade=monster.evade,
    ))
    game.priority.reset_to(attacker_id)


def resolve_roll(game: Game) -> None:
    """
    Execute one combat exchange:
    - Roll d6.
    - Hit (roll >= monster.evade): monster takes 1 damage.
    - Miss (roll < monster.evade): attacker takes 1 damage.
    - Log CombatRollResult and DamageDealt.
    - Check for death.
    """
    assert game.combat is not None and game.combat.is_active
    assert game.zones is not None

    combat = game.combat
    monster = game.zones.monster_slots.get(combat.defender_slot)
    assert monster is not None, f"Monster slot {combat.defender_slot} is empty"

    roll = game.rng.roll_d6()
    is_hit = roll >= monster.evade

    if is_hit:
        monster.take_damage(1)
        game.log.append(DamageDealt(
            source_player_id=combat.attacker_id,
            source_monster_slot=None,
            target_player_id=None,
            target_monster_slot=combat.defender_slot,
            amount=1,
            reason="combat_hit",
        ))
    else:
        attacker = game.state.get_player(combat.attacker_id)
        attacker.hp = max(0, attacker.hp - 1)
        game.log.append(DamageDealt(
            source_player_id=None,
            source_monster_slot=combat.defender_slot,
            target_player_id=combat.attacker_id,
            target_monster_slot=None,
            amount=1,
            reason="combat_miss",
        ))

    game.log.append(CombatRollResult(
        attacker_id=combat.attacker_id,
        defender_slot=combat.defender_slot,
        roll=roll,
        evade=monster.evade,
        is_hit=is_hit,
    ))

    if not monster.is_alive():
        resolve_monster_death(game)
    elif not is_hit and not game.state.get_player(combat.attacker_id).is_alive() \
            and not game.state.turn_flags.died_this_turn:
        resolve_player_death(game)
    else:
        game.priority.reset_to(combat.attacker_id)


def resolve_monster_death(game: Game) -> None:
    """
    Clean up after a monster's hp reaches 0.

    - Discard the dead monster's card ref.
    - Clear the slot.
    - Refill the slot from the monster deck (make_monster_in_play on the drawn ref).
    - If the deck is empty, leave the slot empty.
    - Grant cent reward to attacker and log CoinsGained (always fired, even if 0).
    - Grant soul to attacker and log SoulGranted if monster has_soul.
    - End combat (game.combat = None).
    - Log MonsterDied.
    - Reset priority to the attacker.
    - Check for game win and emit GameWon if threshold reached.
    """
    assert game.combat is not None
    assert game.zones is not None

    combat = game.combat
    slot_index = combat.defender_slot
    dead_monster = game.zones.monster_slots.get(slot_index)
    assert dead_monster is not None

    monster_name = str(dead_monster.card_ref.card_id or "unknown")

    # Discard card, clear slot
    game.zones.monster_discard.add(dead_monster.card_ref)
    game.zones.monster_slots.clear(slot_index)

    # Refill from deck if possible
    if not game.zones.monster_deck.empty():
        new_ref = game.zones.monster_deck.draw(1)[0]
        game.zones.monster_slots.set(slot_index, make_monster_in_play(new_ref))

    attacker_id = combat.attacker_id
    attacker = game.state.get_player(attacker_id)

    game.log.append(MonsterDied(
        attacker_id=attacker_id,
        slot_index=slot_index,
        card_ref=dead_monster.card_ref,
        monster_name=monster_name,
        reward_cents=dead_monster.reward_cents,
        had_soul=dead_monster.has_soul,
    ))

    # Grant cent reward (always, even if 0 — keeps the path uniform).
    attacker.cents += dead_monster.reward_cents
    game.log.append(CoinsGained(
        player_id=attacker_id,
        cents=dead_monster.reward_cents,
        reason="monster_kill",
    ))

    # Grant soul if the monster carries one.
    if dead_monster.has_soul:
        attacker.souls.append(dead_monster.card_ref)
        game.log.append(SoulGranted(
            player_id=attacker_id,
            card_ref=dead_monster.card_ref,
            card_name=monster_name,
        ))

    game.combat = None
    game.priority.reset_to(attacker_id)

    # Check win condition
    if len(attacker.souls) >= SOULS_TO_WIN:
        game.log.append(GameWon(
            player_id=attacker_id,
            soul_count=len(attacker.souls),
        ))
        game.game_over = True


def resolve_player_death(game: Game) -> None:
    """
    Clean up after the attacking player's hp reaches 0.

    - Log PlayerDied.
    - Apply the four-step death penalty:
        1. Destroy 1 non-eternal item (first in player.items, if any).
        2. Discard 1 loot card from hand (first in hand, if any).
        3. Lose 1¢ (floor 0).
        4. Deactivate (untap) all ↷ items.
    - Log DeathPenaltyPaid.
    - End combat (game.combat = None); the monster survives in place.
    - Reset priority to the (now dead) attacker so the turn can still end.
    - attack_used stays True: the attack was spent.
    - Turn continues; the player must issue EndTurn explicitly.
    """
    assert game.combat is not None
    assert game.zones is not None

    combat = game.combat
    attacker_id = combat.attacker_id
    slot_index = combat.defender_slot

    monster = game.zones.monster_slots.get(slot_index)
    monster_name = str(monster.card_ref.card_id or "unknown") if monster is not None else "unknown"

    game.log.append(PlayerDied(
        player_id=attacker_id,
        slot_index=slot_index,
        monster_name=monster_name,
    ))

    player = game.state.get_player(attacker_id)

    # 1. Destroy 1 non-eternal item (all CardRefs in player.items are non-eternal)
    item_destroyed = None
    if player.items:
        item_destroyed = player.items.pop(0)
        game.zones.treasure_discard.add(item_destroyed)

    # 2. Discard 1 loot card from hand
    loot_discarded = None
    if player.hand:
        loot_discarded = player.hand.pop(0)
        game.zones.loot_discard.add(loot_discarded)

    # 3. Lose 1¢
    cents_lost = min(1, player.cents)
    player.cents = max(0, player.cents - 1)

    # 4. Deactivate (untap) all ↷ items
    items_deactivated = 0
    if player.character is not None and player.character.is_tapped:
        player.character.untap()
        items_deactivated += 1

    game.log.append(DeathPenaltyPaid(
        player_id=attacker_id,
        item_destroyed=item_destroyed,
        loot_discarded=loot_discarded,
        cents_lost=cents_lost,
        items_deactivated=items_deactivated,
    ))

    game.state.turn_flags.died_this_turn = True
    game.combat = None

    # Active-player death: drain the stack then advance to END phase.
    # (Stack is always empty here in the current model, but cleared defensively.)
    if attacker_id == game.state.active_player_id:
        while not game.stack.empty():
            item = game.stack.pop()
            game.log.append(EffectFizzled(
                stack_id=item.stack_id,
                reason="active_player_death",
                label=item.label,
            ))
        game.log.append(PhaseChanged(old_phase=Phase.ACTION, new_phase=Phase.END))
        game.state.phase = Phase.END

    game.priority.reset_to(attacker_id)
