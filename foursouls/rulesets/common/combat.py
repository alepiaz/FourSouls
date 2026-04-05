from __future__ import annotations

from typing import TYPE_CHECKING

from foursouls.cards.monsters import make_monster_in_play
from foursouls.engine.events import CombatEntered, CombatRollResult, MonsterDied, PlayerDied, RewardGranted, SoulGranted
from foursouls.model.combat_state import CombatState

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


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

    game.log.append(CombatEntered(attacker_id=attacker_id, defender_slot=slot_index))
    game.priority.reset_to(attacker_id)


def resolve_roll(game: Game) -> None:
    """
    Execute one combat exchange:
    - Roll d6.
    - Hit (roll >= monster.evade): monster takes 1 damage.
    - Miss (roll < monster.evade): attacker takes 1 damage.
    - Log CombatRollResult.
    - Combat remains active; death detection is Release 4.4.
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
    else:
        attacker = game.state.get_player(combat.attacker_id)
        attacker.hp = max(0, attacker.hp - 1)

    game.log.append(CombatRollResult(
        attacker_id=combat.attacker_id,
        defender_slot=combat.defender_slot,
        roll=roll,
        evade=monster.evade,
        is_hit=is_hit,
    ))

    if not monster.is_alive():
        resolve_monster_death(game)
    elif not is_hit and not game.state.get_player(combat.attacker_id).is_alive():
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
    - Grant cent reward to attacker and log RewardGranted (always fired, even if 0).
    - Grant soul to attacker and log SoulGranted if monster has_soul.
    - End combat (game.combat = None).
    - Log MonsterDied.
    - Reset priority to the attacker.
    """
    assert game.combat is not None
    assert game.zones is not None

    combat = game.combat
    slot_index = combat.defender_slot
    dead_monster = game.zones.monster_slots.get(slot_index)
    assert dead_monster is not None

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
    ))

    # Grant cent reward (always, even if 0 — keeps the path uniform).
    attacker.cents += dead_monster.reward_cents
    game.log.append(RewardGranted(player_id=attacker_id, cents=dead_monster.reward_cents))

    # Grant soul if the monster carries one.
    if dead_monster.has_soul:
        attacker.souls.append(dead_monster.card_ref)
        game.log.append(SoulGranted(player_id=attacker_id, card_ref=dead_monster.card_ref))

    game.combat = None
    game.priority.reset_to(attacker_id)


def resolve_player_death(game: Game) -> None:
    """
    Clean up after the attacking player's hp reaches 0.

    - End combat (game.combat = None); the monster survives in place.
    - Log PlayerDied.
    - Reset priority to the (now dead) attacker so the turn can still end.
    - attack_used stays True: the attack was spent.
    - Turn continues; the player must issue EndTurn explicitly.
    - Full death-penalty ecosystem (item loss, re-spawn, etc.) is out of scope.
    """
    assert game.combat is not None

    combat = game.combat
    attacker_id = combat.attacker_id
    slot_index = combat.defender_slot

    game.log.append(PlayerDied(player_id=attacker_id, slot_index=slot_index))
    game.combat = None
    game.priority.reset_to(attacker_id)
