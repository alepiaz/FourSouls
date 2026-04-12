"""
R13.2 — Combat integration tests.

Verifies that the four monster trigger hooks are called at the right moment
in the combat flow, that their return values are respected, and that
last_combat_roll / evade_bonus / attack_bonus are wired into the hit/miss
logic.  No real card definitions carry these hooks yet; each test wires a
fresh callback directly onto a MonsterDef or MonsterInPlay.

Determinism strategy:
  evade=1  → any d6 roll (1–6) is a hit
  evade=7  → no d6 roll (1–6) can hit; every roll is a miss
"""
from __future__ import annotations

from foursouls.cards.monsters import MonsterDef
from foursouls.cli.app import build_demo_game
from foursouls.engine.events import (
    CombatRollResult,
    DamageDealt,
    MonsterDied,
    MonsterTriggerFired,
)
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _advance_to_action(g) -> None:
    from agents.pass_bot import choose_command as pass_command
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))


def _plant(g, monster: MonsterInPlay, slot: int = 0) -> None:
    g.zones.monster_slots.set(slot, monster)


def _guaranteed_hit_monster(**kwargs) -> MonsterInPlay:
    """evade=1 → always hit (any d6 roll ≥ 1)."""
    kw = dict(base_hp=10, evade=1, attack=0, has_soul=False)
    kw.update(kwargs)
    return _make_stub(**kw)


def _guaranteed_miss_monster(**kwargs) -> MonsterInPlay:
    """evade=7 → always miss (d6 max is 6 < 7)."""
    kw = dict(base_hp=10, evade=7, attack=1, has_soul=False)
    kw.update(kwargs)
    return _make_stub(**kw)


def _make_stub(*, base_hp=5, evade=1, attack=0, has_soul=False,
               on_death=None, on_miss=None,
               on_would_take_combat_damage=None, on_would_die=None) -> MonsterInPlay:
    """Build a MonsterInPlay with trigger hooks set directly on the instance."""
    return MonsterInPlay(
        card_ref=CardRef(InstanceId("stub-m"), CardId("STUB")),
        base_hp=base_hp,
        current_hp=base_hp,
        evade=evade,
        attack=attack,
        has_soul=has_soul,
        on_death=on_death,
        on_miss=on_miss,
        on_would_take_combat_damage=on_would_take_combat_damage,
        on_would_die=on_would_die,
    )


def _roll_result(events) -> CombatRollResult:
    return next(e for e in events if isinstance(e, CombatRollResult))


# ---------------------------------------------------------------------------
# last_combat_roll is stored on CombatState
# ---------------------------------------------------------------------------

def test_last_combat_roll_stored_after_hit():
    """last_combat_roll equals the roll in CombatRollResult after a hit."""
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    _plant(g, _guaranteed_hit_monster(base_hp=20))  # won't die from one hit

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    # combat may still be active; if so we can read last_combat_roll directly
    if g.combat is not None:
        assert g.combat.last_combat_roll == roll_evt.roll
    else:
        # combat cleared on monster death — verify indirectly via event
        assert roll_evt.roll in range(1, 7)


def test_last_combat_roll_stored_after_miss():
    """last_combat_roll equals the roll in CombatRollResult after a miss."""
    from foursouls.model.commands import AttackMonster, RollCombat

    roll_seen = []

    def capture(game, roll):  # on_miss callback
        roll_seen.append(roll)
        return 0  # no damage

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    _plant(g, _guaranteed_miss_monster(on_miss=capture))

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert roll_seen == [roll_evt.roll]


# ---------------------------------------------------------------------------
# evade_bonus shifts the hit threshold
# ---------------------------------------------------------------------------

def test_evade_bonus_makes_monster_impossible_to_hit():
    """With evade=1 but evade_bonus=6, effective evade=7 → always miss."""
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=10, attack=0)  # evade=1
    m.evade_bonus = 6   # effective evade = 7 → always miss now
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert not roll_evt.is_hit
    assert roll_evt.evade == 7


def test_evade_bonus_reported_in_roll_result():
    """CombatRollResult.evade reflects the effective (bonus-adjusted) threshold."""
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _make_stub(base_hp=10, evade=3, attack=0)
    m.evade_bonus = 2   # effective = 5
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert roll_evt.evade == 5


def test_evade_bonus_zero_default_unchanged():
    """evade_bonus=0 (default) leaves outcome identical to original logic."""
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=10, attack=0)
    assert m.evade_bonus == 0
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert roll_evt.is_hit  # evade=1 still guarantees a hit


# ---------------------------------------------------------------------------
# attack_bonus on monster shifts miss damage
# ---------------------------------------------------------------------------

def test_monster_attack_bonus_increases_miss_damage():
    """Monster with attack=1 and attack_bonus=2 deals 3 damage on miss."""
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_miss_monster(attack=1)
    m.attack_bonus = 2   # effective miss damage = 3
    _plant(g, m)

    attacker = g.state.get_player(g.state.active_player_id)
    # Give the player enough HP so 3 damage doesn't clamp at 0
    attacker.hp = 10
    attacker.max_hp = 10
    hp_before = attacker.hp

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

    assert attacker.hp == hp_before - 3


def test_negative_attack_bonus_reduces_miss_damage():
    """Monster with attack=2 and attack_bonus=-1 deals 1 damage on miss."""
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_miss_monster(attack=2)
    m.attack_bonus = -1
    _plant(g, m)

    attacker = g.state.get_player(g.state.active_player_id)
    hp_before = attacker.hp

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

    assert attacker.hp == hp_before - 1


def test_attack_bonus_zero_default_unchanged():
    """attack_bonus=0 (default) → miss damage equals monster.attack."""
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_miss_monster(attack=2)
    assert m.attack_bonus == 0
    _plant(g, m)

    attacker = g.state.get_player(g.state.active_player_id)
    hp_before = attacker.hp

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

    assert attacker.hp == hp_before - 2


# ---------------------------------------------------------------------------
# on_would_take_combat_damage
# ---------------------------------------------------------------------------

def test_on_would_take_combat_damage_can_reduce_damage_to_zero():
    """Callback returning 0 means monster takes no damage on hit."""
    from foursouls.model.commands import AttackMonster, RollCombat

    def block_all(game, roll, amount):  # noqa: ARG001
        return 0

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=5, on_would_take_combat_damage=block_all)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

    # Monster should be alive and unharmed
    surviving = g.zones.monster_slots.get(0)
    assert surviving is not None
    assert surviving.current_hp == 5


def test_on_would_take_combat_damage_emits_trigger_event():
    from foursouls.model.commands import AttackMonster, RollCombat

    def passthrough(game, roll, amount):  # noqa: ARG001
        return amount

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=20, on_would_take_combat_damage=passthrough)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    trigger_evts = [e for e in result.events if isinstance(e, MonsterTriggerFired)]
    assert any(e.trigger == "on_would_take_combat_damage" for e in trigger_evts)


def test_on_would_take_combat_damage_receives_correct_roll():
    """Roll passed to the callback matches the roll in CombatRollResult."""
    from foursouls.model.commands import AttackMonster, RollCombat

    received = []

    def capture(game, roll, amount):  # noqa: ARG001
        received.append(roll)
        return amount

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=20, on_would_take_combat_damage=capture)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert received == [roll_evt.roll]


def test_on_would_take_combat_damage_not_called_on_miss():
    """Callback must not fire when the roll is a miss."""
    from foursouls.model.commands import AttackMonster, RollCombat

    fired = []

    def record(game, roll, amount):  # noqa: ARG001
        fired.append(True)
        return amount

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_miss_monster(on_would_take_combat_damage=record)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

    assert not fired


# ---------------------------------------------------------------------------
# on_miss
# ---------------------------------------------------------------------------

def test_on_miss_can_increase_miss_damage():
    """Callback returning 3 makes every miss deal 3 damage regardless of monster.attack."""
    from foursouls.model.commands import AttackMonster, RollCombat

    def triple(game, roll):  # noqa: ARG001
        return 3

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_miss_monster(attack=1, on_miss=triple)
    _plant(g, m)

    attacker = g.state.get_player(g.state.active_player_id)
    # Give the player enough HP so 3 damage doesn't clamp at 0
    attacker.hp = 10
    attacker.max_hp = 10
    hp_before = attacker.hp

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

    assert attacker.hp == hp_before - 3


def test_on_miss_emits_trigger_event():
    from foursouls.model.commands import AttackMonster, RollCombat

    def passthrough(game, roll):  # noqa: ARG001
        return 1

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_miss_monster(attack=1, on_miss=passthrough)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    trigger_evts = [e for e in result.events if isinstance(e, MonsterTriggerFired)]
    assert any(e.trigger == "on_miss" for e in trigger_evts)


def test_on_miss_receives_correct_roll():
    """Roll passed to on_miss matches the roll in CombatRollResult."""
    from foursouls.model.commands import AttackMonster, RollCombat

    received = []

    def capture(game, roll):  # noqa: ARG001
        received.append(roll)
        return 0  # no damage

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_miss_monster(on_miss=capture)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert received == [roll_evt.roll]


def test_on_miss_not_called_on_hit():
    """on_miss must not fire when the roll is a hit."""
    from foursouls.model.commands import AttackMonster, RollCombat

    fired = []

    def record(game, roll):  # noqa: ARG001
        fired.append(True)
        return 0

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=20, on_miss=record)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

    assert not fired


# ---------------------------------------------------------------------------
# on_would_die
# ---------------------------------------------------------------------------

def test_on_would_die_can_prevent_death():
    """Callback returning True keeps the monster alive after HP hits 0."""
    from foursouls.model.commands import AttackMonster, RollCombat

    def prevent(game):
        m = game.zones.monster_slots.get(game.combat.defender_slot)
        m.current_hp = 2   # heal so it survives
        return True

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=1, on_would_die=prevent)  # one hit kills → trigger
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

    # Death prevented → monster must still occupy the slot
    surviving = g.zones.monster_slots.get(0)
    assert surviving is not None
    assert surviving.current_hp == 2


def test_on_would_die_emits_trigger_event_with_roll_zero():
    from foursouls.model.commands import AttackMonster, RollCombat

    def prevent(game):
        game.zones.monster_slots.get(game.combat.defender_slot).current_hp = 2
        return True

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=1, on_would_die=prevent)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    trigger_evts = [e for e in result.events if isinstance(e, MonsterTriggerFired)]
    assert any(e.trigger == "on_would_die" and e.roll == 0 for e in trigger_evts)


def test_on_would_die_sets_prevent_death_used():
    from foursouls.model.commands import AttackMonster, RollCombat

    def prevent(game):
        game.zones.monster_slots.get(game.combat.defender_slot).current_hp = 5
        return True

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=1, on_would_die=prevent)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

    surviving = g.zones.monster_slots.get(0)
    assert surviving is not None
    assert surviving.prevent_death_used is True


def test_on_would_die_fires_only_once_per_turn():
    """Second lethal roll in the same combat must not invoke on_would_die again."""
    from foursouls.model.commands import AttackMonster, RollCombat

    call_count = []

    def prevent_once(game):
        call_count.append(1)
        # Restore 1 HP so the monster survives the first prevention
        game.zones.monster_slots.get(game.combat.defender_slot).current_hp = 1
        return True

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    # base_hp=1 → any hit kills; evade=1 → always hit
    m = _guaranteed_hit_monster(base_hp=1, on_would_die=prevent_once)
    _plant(g, m)

    # First roll: prevention triggers; combat remains active; monster healed to 1
    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())
    assert len(call_count) == 1
    assert g.combat is not None, "Combat should still be active after death prevention"

    # Second roll in the same combat: monster would die again, but flag is set
    g.step(RollCombat())

    # on_would_die must not have fired a second time
    assert len(call_count) == 1


def test_on_would_die_returning_false_does_not_prevent_death():
    """Callback returning False lets normal death resolution proceed."""
    from foursouls.model.commands import AttackMonster, RollCombat

    def no_prevent(game):  # noqa: ARG001
        return False

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=1, on_would_die=no_prevent)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    died_evts = [e for e in result.events if isinstance(e, MonsterDied)]
    assert died_evts, "Monster should have died when on_would_die returns False"


# ---------------------------------------------------------------------------
# on_death
# ---------------------------------------------------------------------------

def test_on_death_fires_after_monster_dies():
    from foursouls.model.commands import AttackMonster, RollCombat

    fired = []

    def record_death(game, roll):  # noqa: ARG001
        fired.append(roll)

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=1, on_death=record_death)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert fired == [roll_evt.roll]


def test_on_death_receives_correct_roll_via_last_combat_roll():
    """Roll passed to on_death equals last_combat_roll (= roll in CombatRollResult)."""
    from foursouls.model.commands import AttackMonster, RollCombat

    received = []

    def capture(game, roll):  # noqa: ARG001
        received.append(roll)

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=1, on_death=capture)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert received == [roll_evt.roll]


def test_on_death_emits_trigger_event():
    from foursouls.model.commands import AttackMonster, RollCombat

    def noop(game, roll):  # noqa: ARG001
        pass

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=1, on_death=noop)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    trigger_evts = [e for e in result.events if isinstance(e, MonsterTriggerFired)]
    assert any(e.trigger == "on_death" for e in trigger_evts)


def test_on_death_not_called_when_no_hook():
    """Registry monster with no on_death hook never fires MonsterTriggerFired(on_death)."""
    from foursouls.cards.monsters import FLY, make_monster_in_play
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    fly = make_monster_in_play(CardRef(InstanceId("fly"), FLY))
    _plant(g, fly)

    g.step(AttackMonster(slot_index=0))
    # Use enough rolls to guarantee a kill (FLY has base_hp=1, evade=2)
    # With evade=2 any roll ≥ 2 hits; we'll just roll and check events
    result = g.step(RollCombat())

    trigger_evts = [e for e in result.events if isinstance(e, MonsterTriggerFired)]
    assert not any(e.trigger == "on_death" for e in trigger_evts)
