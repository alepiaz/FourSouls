"""
R13.1 — Monster trigger substrate tests.

Verifies that the new data-model fields exist with correct defaults, that
MonsterTriggerFired is a well-formed event, and that per-turn monster flags
are reset by on_end_turn.  No actual trigger callbacks are wired yet (that
is R13.2+); these tests validate the substrate alone.
"""
from __future__ import annotations

import pytest

from foursouls.cards.monsters import (
    GAPER, HORF, MonsterDef, _DEFAULT, get_monster_def, make_monster_in_play,
)
from foursouls.engine.events import MonsterTriggerFired
from foursouls.engine.rng import RNG
from foursouls.model.combat_state import CombatState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.setup import setup_game
from foursouls.model.game_state import GameState
from foursouls.model.player_state import PlayerState
from foursouls.model.phase import Phase

from agents.pass_bot import choose_command as pass_command


# ---------------------------------------------------------------------------
# CombatState — last_combat_roll
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


# ---------------------------------------------------------------------------
# MonsterDef — trigger hook fields
# ---------------------------------------------------------------------------

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
    """Two MonsterDefs that differ only in their hooks compare equal."""
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


# ---------------------------------------------------------------------------
# MonsterInPlay — new per-turn fields
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# MonsterTriggerFired event
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# End-of-turn reset — prevent_death_used / evade_bonus / attack_bonus
# ---------------------------------------------------------------------------

def _two_player_action_game() -> object:
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
    # Manually dirty a monster's per-turn flag
    idx = g.zones.monster_slots.filled_indices()[0]
    monster = g.zones.monster_slots.get(idx)
    monster.prevent_death_used = True
    monster.evade_bonus = 2
    monster.attack_bonus = -1

    # End the turn
    from foursouls.model.commands import EndTurn
    g.step(EndTurn())

    # After EndTurn, monster healback also resets the three trigger flags
    # (the new active player's start phase is now running; we check the same slot)
    m_after = g.zones.monster_slots.get(idx)
    # The slot may have been refilled; if so the new monster also starts clean.
    if m_after is not None:
        assert m_after.prevent_death_used is False
        assert m_after.evade_bonus == 0
        assert m_after.attack_bonus == 0
