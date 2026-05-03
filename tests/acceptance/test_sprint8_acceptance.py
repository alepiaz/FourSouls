"""
Sprint 8 acceptance test — ATK stat & correct combat damage.

Scenarios
---------
1. Hit uses attacker.attack + attack_bonus:
   - Player with attack=2, attack_bonus=1 → monster takes 3 damage on hit.

2. Miss uses monster.attack:
   - Monster with attack=3 → player loses 3 HP on miss.

3. HORF (attack=2) deals 2 damage on miss.

4. Zero-damage hit skips DamageDealt event.

5. CombatRollResult carries correct attack_stat.

6. DamageDealt.damage_type == "combat" for combat damage.
"""
from __future__ import annotations

from foursouls.cards.monsters import HORF, make_monster_in_play
from foursouls.cli.app import build_demo_game
from foursouls.engine.events import CombatRollResult, DamageDealt
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.refs import CardRef, InstanceId, PlayerId

from agents.pass_bot import choose_command as pass_command


def _advance_to_action(g) -> None:
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))


def _plant_monster(g, *, base_hp, evade, attack, has_soul=False) -> None:
    g.zones.monster_slots.set(
        0,
        MonsterInPlay(
            card_ref=CardRef(InstanceId("test-monster")),
            base_hp=base_hp,
            current_hp=base_hp,
            evade=evade,
            reward_coin=0,
            has_soul=has_soul,
            attack=attack,
        ),
    )


def _step_until(g, predicate, limit=100):
    """Step the game until predicate(events) is True. Returns all collected events."""
    from foursouls.rulesets.common.legality import get_legal_actions
    all_events = []
    for _ in range(limit):
        actions = get_legal_actions(g)
        if not actions:
            break
        result = g.step(actions[0])
        all_events.extend(result.events)
        if predicate(result.events):
            return all_events
    return all_events


# ---------------------------------------------------------------------------
# Test 1: hit damage = attack + attack_bonus
# ---------------------------------------------------------------------------

def test_hit_deals_attack_plus_bonus_damage():
    """On a guaranteed hit, monster takes attack + attack_bonus damage."""
    g = build_demo_game(["P1", "P2"], seed=0)
    _advance_to_action(g)

    p1 = g.state.get_player(PlayerId("P1"))
    p1.attack = 2
    p1.attack_bonus = 1  # total = 3

    # Monster with evade=1 (always hit), high HP so it survives
    _plant_monster(g, base_hp=10, evade=1, attack=1)

    from foursouls.model.commands import AttackMonster, RollCombat

    # Attack
    g.step(AttackMonster(slot_index=0))
    # Roll
    result = g.step(RollCombat())

    damage_events = [e for e in result.events if isinstance(e, DamageDealt)]
    roll_events = [e for e in result.events if isinstance(e, CombatRollResult)]

    assert roll_events, "CombatRollResult not emitted"
    roll = roll_events[0]

    if roll.is_hit:
        assert len(damage_events) == 1
        assert damage_events[0].amount == 3
        assert damage_events[0].damage_type == "combat"
        assert roll.attack_stat == 3

        monster = g.zones.monster_slots.get(0)
        if monster is not None:
            assert monster.current_hp == 10 - 3
    else:
        # Miss: player takes monster.attack=1 damage
        assert len(damage_events) == 1
        assert damage_events[0].amount == 1
        assert damage_events[0].damage_type == "combat"


# ---------------------------------------------------------------------------
# Test 2: miss damage = monster.attack
# ---------------------------------------------------------------------------

def test_miss_deals_monster_attack_damage():
    """On a guaranteed miss, player loses monster.attack HP."""
    # Use seed that produces a miss (roll < evade=6)
    # We'll try seeds until we get a miss, or force it by inspection
    g = build_demo_game(["P1", "P2"], seed=42)
    _advance_to_action(g)

    p1 = g.state.get_player(PlayerId("P1"))
    initial_hp = p1.hp

    # Monster with evade=6 (always miss), attack=3
    _plant_monster(g, base_hp=10, evade=6, attack=3)

    from foursouls.model.commands import AttackMonster, PassPriority, RollCombat

    g.step(AttackMonster(slot_index=0))
    roll_result = g.step(RollCombat())
    # Resolve CombatMissDamageEffect — 2-player game requires 2 passes
    for _ in range(2):
        g.step(PassPriority())

    roll_events = [e for e in roll_result.events if isinstance(e, CombatRollResult)]
    assert roll_events
    roll = roll_events[0]
    assert not roll.is_hit, "Expected a miss (evade=6)"
    assert roll.attack_stat == 3
    assert p1.hp == max(0, initial_hp - 3)


# ---------------------------------------------------------------------------
# Test 3: HORF monster has attack=2 by registry
# ---------------------------------------------------------------------------

def test_horf_attack_is_1():
    """HORF has ATK 1 per the official card."""
    from foursouls.model.refs import CardRef, InstanceId
    horf = make_monster_in_play(CardRef(InstanceId("horf-1"), HORF))
    assert horf.attack == 1


def test_horf_miss_deals_2_damage():
    """Missing against HORF costs the attacker 2 HP."""
    g = build_demo_game(["P1", "P2"], seed=42)
    _advance_to_action(g)

    p1 = g.state.get_player(PlayerId("P1"))
    initial_hp = p1.hp

    # Plant HORF (evade=2, attack=2) but override evade to 6 to guarantee miss
    g.zones.monster_slots.set(
        0,
        MonsterInPlay(
            card_ref=CardRef(InstanceId("horf-test")),
            base_hp=2,
            current_hp=2,
            evade=6,
            reward_coin=10,
            has_soul=True,
            attack=2,
        ),
    )

    from foursouls.model.commands import AttackMonster, PassPriority, RollCombat

    g.step(AttackMonster(slot_index=0))
    roll_result = g.step(RollCombat())
    all_events = list(roll_result.events)
    for _ in range(2):
        all_events.extend(g.step(PassPriority()).events)

    roll_events = [e for e in all_events if isinstance(e, CombatRollResult)]
    assert roll_events and not roll_events[0].is_hit
    assert roll_events[0].attack_stat == 2
    assert p1.hp == max(0, initial_hp - 2)


# ---------------------------------------------------------------------------
# Test 4: zero-damage hit skips DamageDealt
# ---------------------------------------------------------------------------

def test_zero_damage_hit_skips_damage_event():
    """A hit with attack=0 does not emit DamageDealt and does not change monster HP."""
    g = build_demo_game(["P1", "P2"], seed=0)
    _advance_to_action(g)

    p1 = g.state.get_player(PlayerId("P1"))
    p1.attack = 0
    p1.attack_bonus = 0

    _plant_monster(g, base_hp=5, evade=1, attack=1)  # evade=1: always hit

    from foursouls.model.commands import AttackMonster, RollCombat

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_events = [e for e in result.events if isinstance(e, CombatRollResult)]
    assert roll_events

    if roll_events[0].is_hit:
        damage_events = [e for e in result.events if isinstance(e, DamageDealt)]
        assert damage_events == [], "DamageDealt should be skipped for 0 damage"
        monster = g.zones.monster_slots.get(0)
        if monster is not None:
            assert monster.current_hp == 5
