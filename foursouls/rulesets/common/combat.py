from __future__ import annotations

from typing import TYPE_CHECKING

from foursouls.cards.monsters import get_monster_def, make_monster_in_play
from foursouls.engine.events import (
    CoinsGained,
    CombatEntered,
    CombatRollResult,
    DamageDealt,
    DeathPenaltyPaid,
    EffectFizzled,
    EventEntered,
    GameWon,
    MonsterDied,
    MonsterTriggerFired,
    PhaseChanged,
    PlayerDied,
    SoulGranted,
)
from foursouls.model.phase import Phase
from foursouls.model.combat_state import CombatState
from foursouls.model.refs import CardRef
from foursouls.rulesets.common.effects import CombatMissDamageEffect

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game

SOULS_TO_WIN = 4


def place_monster_card(game: Game, slot_index: int, card_ref: CardRef) -> None:
    """
    Place a card into a monster slot.

    For normal monsters: create MonsterInPlay and set the slot.
    For event cards: additionally emit EventEntered and push the triggered
    ability onto the stack, wrapped in EventCardEffect so the slot is cleared
    and the card discarded when the effect resolves.
    """
    from foursouls.rulesets.common.effects import EventCardEffect

    monster = make_monster_in_play(card_ref)
    game.zones.monster_slots.set(slot_index, monster)

    if monster.is_event:
        defn = get_monster_def(card_ref.card_id)
        inner = defn.event_effect(game) if defn.event_effect is not None else _NoOpEffect()
        wrapped = EventCardEffect(
            card_ref=card_ref,
            slot_index=slot_index,
            inner=inner,
            monster_slots=game.zones.monster_slots,
            monster_discard=game.zones.monster_discard,
        )
        card_name = str(card_ref.card_id or "event")
        game.log.append(EventEntered(
            slot_index=slot_index,
            card_ref=card_ref,
            card_name=card_name,
        ))
        game.push_to_stack(
            controller_id=game.state.active_player_id,
            source=f"event:{card_ref.card_id}",
            effect=wrapped,
            label=card_name,
        )


class _NoOpEffect:
    """Fallback effect for event cards with no defined effect."""
    def validate(self, ctx) -> bool:  # noqa: ARG002
        return True
    def apply(self, ctx) -> None:
        pass


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
    - Hit (roll >= monster.evade + evade_bonus): invoke on_would_take_combat_damage
      (if defined), then apply final damage to monster.
    - Miss (roll < evade): invoke on_miss (if defined) to determine final miss
      damage, then apply to attacker.
    - Skip the damage step if the final amount is 0.
    - Log CombatRollResult and DamageDealt.
    - Check for death; invoke on_would_die before resolving monster death.
    """
    assert game.combat is not None and game.combat.is_active
    assert game.zones is not None

    combat = game.combat
    monster = game.zones.monster_slots.get(combat.defender_slot)
    assert monster is not None, f"Monster slot {combat.defender_slot} is empty"

    attacker = game.state.get_player(combat.attacker_id)
    roll = game.rng.roll_d6()
    combat.last_combat_roll = roll                              # R13.1 substrate

    effective_evade = monster.evade + monster.evade_bonus      # R13.1 substrate
    is_hit = roll >= effective_evade

    if is_hit:
        damage = attacker.attack + attacker.attack_bonus
        # on_would_take_combat_damage: let the monster modify incoming damage
        if monster.on_would_take_combat_damage is not None:
            game.log.append(MonsterTriggerFired(
                card_id=monster.card_ref.card_id,
                trigger="on_would_take_combat_damage",
                roll=roll,
            ))
            damage = monster.on_would_take_combat_damage(game, roll, damage)  # type: ignore[call-arg]
        if damage > 0:
            monster.take_damage(damage)
            game.log.append(DamageDealt(
                source_player_id=combat.attacker_id,
                source_monster_slot=None,
                target_player_id=None,
                target_monster_slot=combat.defender_slot,
                amount=damage,
                reason="combat_hit",
                damage_type="combat",
            ))
        attack_stat = damage
    else:
        damage = monster.attack + monster.attack_bonus         # R13.1 substrate
        # on_miss: let the monster modify miss damage
        if monster.on_miss is not None:
            game.log.append(MonsterTriggerFired(
                card_id=monster.card_ref.card_id,
                trigger="on_miss",
                roll=roll,
            ))
            damage = monster.on_miss(game, roll)               # type: ignore[call-arg]
        # Push miss damage to the stack so players can respond (R14.1).
        # Actual HP reduction happens when the effect resolves in game_loop.
        if damage > 0:
            game.push_to_stack(
                controller_id=combat.attacker_id,
                source="combat:miss",
                effect=CombatMissDamageEffect(
                    attacker_id=combat.attacker_id,
                    amount=damage,
                    combat=game.combat,
                ),
                label="CombatMissDamage",
            )
        attack_stat = damage

    game.log.append(CombatRollResult(
        attacker_id=combat.attacker_id,
        defender_slot=combat.defender_slot,
        roll=roll,
        evade=effective_evade,
        is_hit=is_hit,
        attack_stat=attack_stat,
    ))

    # ── Death checks (hit path only; miss damage is on the stack) ────────────
    if check_combat_defender_death(game):
        pass  # monster died; resolve_monster_death already reset priority
    else:
        game.priority.reset_to(combat.attacker_id)


def check_combat_defender_death(game: Game) -> bool:
    """
    If there is active combat and the defender's HP has reached zero, resolve
    its death (including the on_would_die trigger).

    Returns True  → monster death was resolved; game.combat is now None.
    Returns False → monster is still alive, or death was prevented by a trigger.

    Safe to call from any damage path (roll, loot, item, AoE).  Idempotent
    when combat is not active or the monster is still healthy.
    """
    if game.combat is None or not game.combat.is_active or game.zones is None:
        return False

    monster = game.zones.monster_slots.get(game.combat.defender_slot)
    if monster is None or monster.is_alive():
        return False

    prevented = False
    if monster.on_would_die is not None and not monster.prevent_death_used:
        game.log.append(MonsterTriggerFired(
            card_id=monster.card_ref.card_id,
            trigger="on_would_die",
            roll=0,
        ))
        prevented = monster.on_would_die(game)  # type: ignore[call-arg]
        if prevented:
            monster.prevent_death_used = True

    if not prevented:
        resolve_monster_death(game)
        return True

    return False


def _do_resolve_monster_death(game: Game, slot_index: int, attacker_id: object, kill_roll: int) -> None:
    """
    Shared core for monster-death resolution.

    Handles rewards, slot refill, on_death trigger, and win-condition check.
    Called by both resolve_monster_death (combat path) and
    resolve_monster_death_out_of_combat (loot/ability path).
    Does NOT clear game.combat or reset priority — callers handle that.
    """
    assert game.zones is not None

    dead_monster = game.zones.monster_slots.get(slot_index)
    assert dead_monster is not None

    monster_name = str(dead_monster.card_ref.card_id or "unknown")

    # Discard card, clear slot
    game.zones.monster_discard.add(dead_monster.card_ref)
    game.zones.monster_slots.clear(slot_index)

    # Refill from deck if possible
    if not game.zones.monster_deck.empty():
        new_ref = game.zones.monster_deck.draw(1)[0]
        place_monster_card(game, slot_index, new_ref)

    attacker = game.state.get_player(attacker_id)  # type: ignore[arg-type]

    game.log.append(MonsterDied(
        attacker_id=attacker_id,  # type: ignore[arg-type]
        slot_index=slot_index,
        card_ref=dead_monster.card_ref,
        monster_name=monster_name,
        reward_coin=dead_monster.reward_coin,
        had_soul=dead_monster.has_soul,
        reward_loot=dead_monster.reward_loot,
        reward_treasure=dead_monster.reward_treasure,
    ))

    # Grant cent reward (always, even if 0 — keeps the path uniform).
    attacker.cents += dead_monster.reward_coin
    game.log.append(CoinsGained(
        player_id=attacker_id,  # type: ignore[arg-type]
        cents=dead_monster.reward_coin,
        reason="monster_kill",
    ))

    # Grant loot reward (e.g. Spider: draw 1 loot on kill).
    if dead_monster.reward_loot > 0 and not game.zones.loot_deck.empty():
        from foursouls.engine.events import CardDrawn
        drawn = game.zones.loot_deck.draw(dead_monster.reward_loot)
        attacker.hand.extend(drawn)
        for card_ref in drawn:
            game.log.append(CardDrawn(
                player_id=attacker_id,  # type: ignore[arg-type]
                card_ref=card_ref,
                source="monster_kill_loot",
            ))

    # Grant treasure reward (e.g. Headless Horseman: draw 1 treasure on kill).
    if dead_monster.reward_treasure > 0 and not game.zones.treasure_deck.empty():
        from foursouls.engine.events import CardDrawn
        drawn = game.zones.treasure_deck.draw(dead_monster.reward_treasure)
        for card_ref in drawn:
            attacker.gain_treasure(card_ref)
            game.log.append(CardDrawn(
                player_id=attacker_id,  # type: ignore[arg-type]
                card_ref=card_ref,
                source="monster_kill_treasure",
            ))

    # Grant soul if the monster carries one.
    if dead_monster.has_soul:
        attacker.souls.append(dead_monster.card_ref)
        game.log.append(SoulGranted(
            player_id=attacker_id,  # type: ignore[arg-type]
            card_ref=dead_monster.card_ref,
            card_name=monster_name,
        ))

    # on_death: fires after rewards; callback receives the triggering roll
    if dead_monster.on_death is not None:
        game.log.append(MonsterTriggerFired(
            card_id=dead_monster.card_ref.card_id,
            trigger="on_death",
            roll=kill_roll,
        ))
        dead_monster.on_death(game, kill_roll)                 # type: ignore[call-arg]

    # Check win condition
    if len(attacker.souls) >= SOULS_TO_WIN:
        game.log.append(GameWon(
            player_id=attacker_id,  # type: ignore[arg-type]
            soul_count=len(attacker.souls),
        ))
        game.game_over = True


def resolve_monster_death(game: Game) -> None:
    """
    Clean up after a monster's hp reaches 0 during active combat.

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
    _do_resolve_monster_death(game, combat.defender_slot, combat.attacker_id, combat.last_combat_roll)
    # Signal any pending CombatMissDamageEffect on the stack to fizzle (R14.1).
    game.combat.is_active = False
    game.combat = None
    game.priority.reset_to(combat.attacker_id)


def resolve_monster_death_out_of_combat(game: Game, slot_index: int) -> None:
    """
    Resolve a monster death that occurred outside of active combat
    (e.g. via loot card damage, item AoE, event effects).

    Per the Four Souls rules, the active player always receives rewards when
    a monster dies, regardless of who dealt the killing blow.
    Priority is NOT reset here — the game_loop handles that after all deaths
    in the batch are processed.
    """
    assert game.zones is not None
    _do_resolve_monster_death(game, slot_index, game.state.active_player_id, 0)


def check_all_monster_deaths_out_of_combat(game: Game) -> None:
    """
    Scan all monster slots for any monster at 0 HP and process their deaths.

    Called after any effect resolves that could damage monsters outside of
    active combat (e.g. Bomb!, item AoE).  Skips the active combat defender
    slot when combat is in progress — that path is handled by
    check_combat_defender_death.
    """
    if game.zones is None:
        return

    # Snapshot the indices first; slots may be refilled during iteration.
    dead_slots = [
        idx for idx in game.zones.monster_slots.filled_indices()
        if (
            # Skip the active combat defender — handled by check_combat_defender_death
            (game.combat is None or idx != game.combat.defender_slot)
            and (m := game.zones.monster_slots.get(idx)) is not None
            and not m.is_alive()
        )
    ]

    for idx in dead_slots:
        # Re-check: the slot may have been refilled by an earlier death in this loop.
        monster = game.zones.monster_slots.get(idx)
        if monster is not None and not monster.is_alive():
            resolve_monster_death_out_of_combat(game, idx)


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

    # 1. Destroy 1 non-eternal item (first non-eternal entry in player.items).
    item_destroyed = None
    destroyable = [i for i in player.items if not i.eternal]
    if destroyable:
        item_to_destroy = destroyable[0]
        player.items.remove(item_to_destroy)
        item_destroyed = item_to_destroy.card_ref
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


def check_combat_attacker_death(game: Game) -> bool:
    """
    After a CombatMissDamageEffect resolves, check whether the attacker
    has been reduced to 0 HP and trigger player death if so.

    Called from game_loop after every stack item resolution (R14.1).
    Safe to call when combat is None or already inactive.
    """
    if game.combat is None or not game.combat.is_active:
        return False
    attacker = game.state.get_player(game.combat.attacker_id)
    if not attacker.is_alive() and not game.state.turn_flags.died_this_turn:
        resolve_player_death(game)
        return True
    return False
