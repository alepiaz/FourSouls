"""
Sprint 9 acceptance test — Event cards in monster deck.

Scenarios
---------
1. Event card in slot cannot be attacked (no AttackMonster legal action for it).

2. Event card triggers on slot-fill: EventEntered is emitted and the triggered
   ability is pushed onto the stack.

3. When all players pass, the event effect resolves: the inner effect fires and
   the event card is moved to monster discard (slot is cleared).

4. FEAST resolves → active player gains 5¢.
   PLAGUE resolves → active player loses 2 HP.
   WANDERING resolves → active player draws 1 loot card.

5. After resolution, the slot is empty (event discarded) and can be refilled
   by a subsequent monster death.
"""
from __future__ import annotations

from foursouls.cards.monsters import FEAST, PLAGUE, WANDERING, make_monster_in_play
from foursouls.cli.app import build_demo_game
from foursouls.engine.events import EventEntered, StackItemPushed
from foursouls.model.commands import AttackMonster, PassPriority
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.refs import CardRef, InstanceId, PlayerId

from agents.pass_bot import choose_command as pass_command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _advance_to_action(g) -> None:
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))


def _plant_event(g, card_id, slot=0) -> CardRef:
    """Directly place an event card in a slot via make_monster_in_play."""
    ref = CardRef(InstanceId(f"evt-{card_id}"), card_id)
    monster = make_monster_in_play(ref)
    assert monster.is_event
    g.zones.monster_slots.set(slot, monster)
    return ref


def _collect_all_events(g, *, steps=200):
    """Run the game (pass-bot) for up to `steps` steps, collecting all events."""
    all_events = []
    for _ in range(steps):
        if g.game_over:
            break
        actions = g.legal_commands()
        if not actions:
            break
        result = g.step(actions[0])
        all_events.extend(result.events)
    return all_events


# ---------------------------------------------------------------------------
# R9.1: event slots are not legal attack targets
# ---------------------------------------------------------------------------

def test_event_slot_not_attackable():
    """AttackMonster is not offered for a slot containing an event card."""
    g = build_demo_game(["P1", "P2"], seed=0)
    _advance_to_action(g)

    # Replace slot 0 with an event card
    _plant_event(g, FEAST, slot=0)

    legal = g.legal_commands()
    attack_slots = {cmd.slot_index for cmd in legal if isinstance(cmd, AttackMonster)}
    assert 0 not in attack_slots, "Event slot must not be a legal attack target"


# ---------------------------------------------------------------------------
# R9.2: EventEntered + stack push when event enters via place_monster_card
# ---------------------------------------------------------------------------

def test_event_entered_emitted_on_refill():
    """
    When a monster dies and the replacement draw is an event card,
    EventEntered is emitted and the triggered ability is pushed onto the stack.
    """
    from foursouls.rulesets.common.combat import place_monster_card

    g = build_demo_game(["P1", "P2"], seed=0)
    _advance_to_action(g)

    # Put a FEAST card on top of the monster deck
    feast_ref = CardRef(InstanceId("feast-top"), FEAST)
    g.zones.monster_deck.cards.append(feast_ref)  # drawn next (draw pops from end)

    # Plant a 1-HP, evade-1 monster in slot 0 (guaranteed kill)
    g.zones.monster_slots.set(
        0,
        MonsterInPlay(
            card_ref=CardRef(InstanceId("easy-kill")),
            base_hp=1,
            current_hp=1,
            evade=1,
            reward_coin=0,
            has_soul=False,
        ),
    )

    # Kill it: attack + repeated rolls until dead
    from foursouls.model.commands import AttackMonster, RollCombat
    g.step(AttackMonster(slot_index=0))

    all_events = []
    for _ in range(20):
        result = g.step(RollCombat())
        all_events.extend(result.events)
        from foursouls.engine.events import MonsterDied
        if any(isinstance(e, MonsterDied) for e in result.events):
            break

    entered = [e for e in all_events if isinstance(e, EventEntered)]
    assert entered, "EventEntered not emitted after refill with event card"
    assert entered[0].slot_index == 0
    assert entered[0].card_ref.card_id == FEAST

    pushed = [e for e in all_events if isinstance(e, StackItemPushed)]
    assert any("FEAST" in e.label for e in pushed), "Event trigger not pushed to stack"


# ---------------------------------------------------------------------------
# R9.3: Effect resolution per event type
# ---------------------------------------------------------------------------

def test_feast_gives_5_cents():
    """FEAST resolves → active player gains 5¢."""
    g = build_demo_game(["P1", "P2"], seed=0)
    _advance_to_action(g)

    from foursouls.rulesets.common.combat import place_monster_card
    feast_ref = CardRef(InstanceId("feast-test"), FEAST)
    place_monster_card(g, 0, feast_ref)

    p1 = g.state.get_player(PlayerId("P1"))
    cents_before = p1.cents

    # Pass to resolve: all players pass → stack item resolves
    g.step(PassPriority())
    g.step(PassPriority())

    assert p1.cents == cents_before + 5


def test_plague_deals_2_damage():
    """PLAGUE resolves → active player loses 2 HP."""
    g = build_demo_game(["P1", "P2"], seed=0)
    _advance_to_action(g)

    from foursouls.rulesets.common.combat import place_monster_card
    plague_ref = CardRef(InstanceId("plague-test"), PLAGUE)
    place_monster_card(g, 0, plague_ref)

    p1 = g.state.get_player(PlayerId("P1"))
    hp_before = p1.hp

    g.step(PassPriority())
    g.step(PassPriority())

    assert p1.hp == max(0, hp_before - 2)


def test_wandering_draws_1_loot():
    """WANDERING resolves → active player draws 1 loot card."""
    g = build_demo_game(["P1", "P2"], seed=0)
    _advance_to_action(g)

    from foursouls.rulesets.common.combat import place_monster_card
    wandering_ref = CardRef(InstanceId("wandering-test"), WANDERING)
    place_monster_card(g, 0, wandering_ref)

    p1 = g.state.get_player(PlayerId("P1"))
    hand_before = len(p1.hand)

    g.step(PassPriority())
    g.step(PassPriority())

    assert len(p1.hand) == hand_before + 1


# ---------------------------------------------------------------------------
# R9.2: Event slot cleared after resolution
# ---------------------------------------------------------------------------

def test_event_slot_cleared_after_resolution():
    """After an event resolves, its monster slot is empty."""
    g = build_demo_game(["P1", "P2"], seed=0)
    _advance_to_action(g)

    from foursouls.rulesets.common.combat import place_monster_card
    feast_ref = CardRef(InstanceId("feast-clear"), FEAST)
    place_monster_card(g, 0, feast_ref)

    assert g.zones.monster_slots.get(0) is not None, "Slot should be occupied before resolution"

    g.step(PassPriority())
    g.step(PassPriority())

    assert g.zones.monster_slots.get(0) is None, "Slot should be empty after event resolves"
    assert feast_ref in g.zones.monster_discard.cards


# ---------------------------------------------------------------------------
# R9.4: Events in the real deck don't break the game
# ---------------------------------------------------------------------------

def test_game_with_event_cards_completes():
    """
    A full game with event cards in the monster deck runs without error.
    combat_bot drives to win; game terminates normally.
    """
    import agents.combat_bot as combat_bot
    from foursouls.rulesets.common.combat import SOULS_TO_WIN

    g = build_demo_game(["P1", "P2"], seed=7)

    # Pre-load souls so we don't need too many turns
    p1 = g.state.get_player(PlayerId("P1"))
    for i in range(SOULS_TO_WIN - 1):
        p1.souls.append(CardRef(InstanceId(f"pre-{i}")))

    # Drain the stack first — event cards from setup may hold EventCardEffect items
    # that will clear a slot when they resolve. Plant the monster only after the
    # stack is empty to avoid having the plant overwritten by event resolution.
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    # Plant a guaranteed-kill soul monster into whichever slot is empty (or slot 0).
    target_slot = next(
        (i for i in range(2) if g.zones.monster_slots.get(i) is None),
        0,
    )
    g.zones.monster_slots.set(
        target_slot,
        MonsterInPlay(
            card_ref=CardRef(InstanceId("boss")),
            base_hp=1,
            current_hp=1,
            evade=1,
            has_soul=True,
        ),
    )

    for _ in range(2000):
        if g.game_over:
            break
        result = g.step(combat_bot.choose_command(g))
    else:
        raise AssertionError("Game did not terminate within step limit")

    assert g.game_over
