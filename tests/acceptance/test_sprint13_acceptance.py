"""
Sprint 13 acceptance — monster trigger substrate and combat integration.
Covers R13.1 (trigger data model, event, end-of-turn reset) and R13.2
(trigger hooks wired into combat: last_combat_roll, evade_bonus, attack_bonus,
on_would_take_combat_damage, on_miss, on_would_die, on_death).
"""
from __future__ import annotations

import pytest

from foursouls.cards.monsters import (
    GAPER, HORF, MonsterDef, _DEFAULT, get_monster_def, make_monster_in_play,
)
from foursouls.cli.app import build_demo_game
from foursouls.engine.events import (
    CombatRollResult,
    DamageDealt,
    MonsterDied,
    MonsterTriggerFired,
)
from foursouls.engine.rng import RNG
from foursouls.model.combat_state import CombatState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.game_state import GameState
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.setup import setup_game

from agents.pass_bot import choose_command as pass_command


# ---------------------------------------------------------------------------
# R13.1 — Monster trigger substrate
# ---------------------------------------------------------------------------

def test_combat_state_last_combat_roll_defaults_to_zero():
    cs = CombatState(
        attacker_id=PlayerId("P1"),
        defender_slot=0,
        monster_ref=CardRef(InstanceId("m1")),
    )
    assert cs.last_combat_roll == 0


def test_combat_state_last_combat_roll_is_mutable():
    cs = CombatState(
        attacker_id=PlayerId("P1"),
        defender_slot=0,
        monster_ref=CardRef(InstanceId("m1")),
    )
    cs.last_combat_roll = 4
    assert cs.last_combat_roll == 4


def test_monster_def_trigger_hooks_default_to_none():
    defn = get_monster_def(GAPER)
    assert defn.on_death is None
    assert defn.on_miss is None
    assert defn.on_would_take_combat_damage is None
    assert defn.on_would_die is None


def test_default_monster_def_trigger_hooks_none():
    assert _DEFAULT.on_death is None
    assert _DEFAULT.on_miss is None
    assert _DEFAULT.on_would_take_combat_damage is None
    assert _DEFAULT.on_would_die is None


def test_monster_def_trigger_hooks_excluded_from_equality():
    def dummy(game, roll):  # noqa: ARG001
        pass

    a = MonsterDef(card_id=CardId("X"), base_hp=1, evade=1, attack=1, has_soul=False)
    b = MonsterDef(card_id=CardId("X"), base_hp=1, evade=1, attack=1, has_soul=False,
                   on_death=dummy)
    assert a == b


def test_monster_def_trigger_hooks_excluded_from_hash():
    def dummy(game, roll):  # noqa: ARG001
        pass

    a = MonsterDef(card_id=CardId("X"), base_hp=1, evade=1, attack=1, has_soul=False)
    b = MonsterDef(card_id=CardId("X"), base_hp=1, evade=1, attack=1, has_soul=False,
                   on_death=dummy)
    assert hash(a) == hash(b)


def test_monster_def_can_carry_on_death_callback():
    fired = []

    def my_on_death(game, roll):  # noqa: ARG001
        fired.append(roll)

    defn = MonsterDef(
        card_id=CardId("TEST"), base_hp=1, evade=1, attack=1, has_soul=False,
        on_death=my_on_death,
    )
    assert defn.on_death is my_on_death
    defn.on_death(None, 6)  # type: ignore[arg-type]
    assert fired == [6]


def test_monster_in_play_new_fields_default_to_zero_or_false():
    m = make_monster_in_play(CardRef(InstanceId("g1"), GAPER))
    assert m.prevent_death_used is False
    assert m.evade_bonus == 0
    assert m.attack_bonus == 0


def test_monster_in_play_fields_are_mutable():
    m = make_monster_in_play(CardRef(InstanceId("g1"), GAPER))
    m.prevent_death_used = True
    m.evade_bonus = 1
    m.attack_bonus = -1
    assert m.prevent_death_used is True
    assert m.evade_bonus == 1
    assert m.attack_bonus == -1


def test_monster_trigger_fired_can_be_constructed():
    evt = MonsterTriggerFired(card_id=GAPER, trigger="on_death", roll=6)
    assert evt.card_id == GAPER
    assert evt.trigger == "on_death"
    assert evt.roll == 6
    assert evt.name == "MonsterTriggerFired"


def test_monster_trigger_fired_roll_zero_for_non_roll_trigger():
    evt = MonsterTriggerFired(card_id=None, trigger="on_would_die", roll=0)
    assert evt.roll == 0
    assert evt.card_id is None


@pytest.mark.parametrize("trigger", [
    "on_death", "on_miss", "on_would_take_combat_damage", "on_would_die",
])
def test_monster_trigger_fired_all_trigger_names(trigger):
    evt = MonsterTriggerFired(card_id=HORF, trigger=trigger, roll=3)
    assert evt.trigger == trigger


def _two_player_action_game():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    cards = lambda prefix, n: [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]
    g = setup_game(
        state,
        loot_cards=cards("loot", 40),
        treasure_cards=cards("treasure", 10),
        monster_cards=cards("monster", 10),
        rng=RNG(seed=0),
    )
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))
    return g


def test_end_of_turn_resets_prevent_death_used():
    g = _two_player_action_game()
    idx = g.zones.monster_slots.filled_indices()[0]
    monster = g.zones.monster_slots.get(idx)
    monster.prevent_death_used = True
    monster.evade_bonus = 2
    monster.attack_bonus = -1

    from foursouls.model.commands import EndTurn
    g.step(EndTurn())

    m_after = g.zones.monster_slots.get(idx)
    if m_after is not None:
        assert m_after.prevent_death_used is False
        assert m_after.evade_bonus == 0
        assert m_after.attack_bonus == 0


# ---------------------------------------------------------------------------
# R13.2 — Combat integration helpers
# ---------------------------------------------------------------------------

def _advance_to_action(g) -> None:
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))


def _plant(g, monster: MonsterInPlay, slot: int = 0) -> None:
    g.zones.monster_slots.set(slot, monster)


def _guaranteed_hit_monster(**kwargs) -> MonsterInPlay:
    kw = dict(base_hp=10, evade=1, attack=0, has_soul=False)
    kw.update(kwargs)
    return _make_stub(**kw)


def _guaranteed_miss_monster(**kwargs) -> MonsterInPlay:
    kw = dict(base_hp=10, evade=7, attack=1, has_soul=False)
    kw.update(kwargs)
    return _make_stub(**kw)


def _make_stub(*, base_hp=5, evade=1, attack=0, has_soul=False,
               on_death=None, on_miss=None,
               on_would_take_combat_damage=None, on_would_die=None) -> MonsterInPlay:
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
# R13.2 — last_combat_roll
# ---------------------------------------------------------------------------

def test_last_combat_roll_stored_after_hit():
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    _plant(g, _guaranteed_hit_monster(base_hp=20))

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    if g.combat is not None:
        assert g.combat.last_combat_roll == roll_evt.roll
    else:
        assert roll_evt.roll in range(1, 7)


def test_last_combat_roll_stored_after_miss():
    from foursouls.model.commands import AttackMonster, RollCombat

    roll_seen = []

    def capture(game, roll):
        roll_seen.append(roll)
        return 0

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    _plant(g, _guaranteed_miss_monster(on_miss=capture))

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert roll_seen == [roll_evt.roll]


# ---------------------------------------------------------------------------
# R13.2 — evade_bonus
# ---------------------------------------------------------------------------

def test_evade_bonus_makes_monster_impossible_to_hit():
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=10, attack=0)
    m.evade_bonus = 6
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert not roll_evt.is_hit
    assert roll_evt.evade == 7


def test_evade_bonus_reported_in_roll_result():
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _make_stub(base_hp=10, evade=3, attack=0)
    m.evade_bonus = 2
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert roll_evt.evade == 5


def test_evade_bonus_zero_default_unchanged():
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=10, attack=0)
    assert m.evade_bonus == 0
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert roll_evt.is_hit


# ---------------------------------------------------------------------------
# R13.2 — attack_bonus
# ---------------------------------------------------------------------------

def test_monster_attack_bonus_increases_miss_damage():
    from foursouls.model.commands import AttackMonster, PassPriority, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_miss_monster(attack=1)
    m.attack_bonus = 2
    _plant(g, m)

    attacker = g.state.get_player(g.state.active_player_id)
    attacker.hp = 10
    attacker.max_hp = 10
    hp_before = attacker.hp

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())
    g.step(PassPriority())   # P1 passes
    g.step(PassPriority())   # P2 passes → CombatMissDamageEffect resolves

    assert attacker.hp == hp_before - 3


def test_negative_attack_bonus_reduces_miss_damage():
    from foursouls.model.commands import AttackMonster, PassPriority, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_miss_monster(attack=2)
    m.attack_bonus = -1
    _plant(g, m)

    attacker = g.state.get_player(g.state.active_player_id)
    hp_before = attacker.hp

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())
    g.step(PassPriority())   # P1 passes
    g.step(PassPriority())   # P2 passes → CombatMissDamageEffect resolves

    assert attacker.hp == hp_before - 1


def test_attack_bonus_zero_default_unchanged():
    from foursouls.model.commands import AttackMonster, PassPriority, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_miss_monster(attack=2)
    assert m.attack_bonus == 0
    _plant(g, m)

    attacker = g.state.get_player(g.state.active_player_id)
    hp_before = attacker.hp

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())
    g.step(PassPriority())   # P1 passes
    g.step(PassPriority())   # P2 passes → CombatMissDamageEffect resolves

    assert attacker.hp == hp_before - 2


# ---------------------------------------------------------------------------
# R13.2 — on_would_take_combat_damage
# ---------------------------------------------------------------------------

def test_on_would_take_combat_damage_can_reduce_damage_to_zero():
    from foursouls.model.commands import AttackMonster, RollCombat

    def block_all(game, roll, amount):  # noqa: ARG001
        return 0

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=5, on_would_take_combat_damage=block_all)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

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
# R13.2 — on_miss
# ---------------------------------------------------------------------------

def test_on_miss_can_increase_miss_damage():
    from foursouls.model.commands import AttackMonster, PassPriority, RollCombat

    def triple(game, roll):  # noqa: ARG001
        return 3

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_miss_monster(attack=1, on_miss=triple)
    _plant(g, m)

    attacker = g.state.get_player(g.state.active_player_id)
    attacker.hp = 10
    attacker.max_hp = 10
    hp_before = attacker.hp

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())
    g.step(PassPriority())   # P1 passes
    g.step(PassPriority())   # P2 passes → CombatMissDamageEffect resolves

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
    from foursouls.model.commands import AttackMonster, RollCombat

    received = []

    def capture(game, roll):  # noqa: ARG001
        received.append(roll)
        return 0

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_miss_monster(on_miss=capture)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    roll_evt = _roll_result(result.events)
    assert received == [roll_evt.roll]


def test_on_miss_not_called_on_hit():
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
# R13.2 — on_would_die
# ---------------------------------------------------------------------------

def test_on_would_die_can_prevent_death():
    from foursouls.model.commands import AttackMonster, RollCombat

    def prevent(game):
        m = game.zones.monster_slots.get(game.combat.defender_slot)
        m.current_hp = 2
        return True

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=1, on_would_die=prevent)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

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
    from foursouls.model.commands import AttackMonster, RollCombat

    call_count = []

    def prevent_once(game):
        call_count.append(1)
        game.zones.monster_slots.get(game.combat.defender_slot).current_hp = 1
        return True

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    m = _guaranteed_hit_monster(base_hp=1, on_would_die=prevent_once)
    _plant(g, m)

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())
    assert len(call_count) == 1
    assert g.combat is not None

    g.step(RollCombat())
    assert len(call_count) == 1


def test_on_would_die_returning_false_does_not_prevent_death():
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
    assert died_evts


# ---------------------------------------------------------------------------
# R13.2 — on_death
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
    from foursouls.cards.monsters import FLY, make_monster_in_play
    from foursouls.model.commands import AttackMonster, RollCombat

    g = build_demo_game(seed=0)
    _advance_to_action(g)
    fly = make_monster_in_play(CardRef(InstanceId("fly"), FLY))
    _plant(g, fly)

    g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())

    trigger_evts = [e for e in result.events if isinstance(e, MonsterTriggerFired)]
    assert not any(e.trigger == "on_death" for e in trigger_evts)
