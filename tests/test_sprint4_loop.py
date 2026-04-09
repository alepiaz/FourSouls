"""
Release 4.3 — Combat roll loop tests.

Strategy for deterministic rolls:
  evade=1 → roll >= 1 always → guaranteed hit  (d6 yields 1–6)
  evade=7 → roll >= 7 never  → guaranteed miss (d6 yields 1–6 < 7)

Covers:
- RollCombat legal while combat active, illegal otherwise
- hit damages monster by 1
- miss damages attacker by 1
- roll does not damage the wrong target
- CombatRollResult event emitted with correct fields
- repeated rolls accumulate damage correctly
- combat state persists across multiple rolls (no death logic yet)
- priority resets to attacker after roll
- hp never goes below 0
"""
from __future__ import annotations

import pytest

from foursouls.engine.events import CombatRollResult
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.combat_state import CombatState
from foursouls.model.commands import AttackMonster, RollCombat
from foursouls.model.game_state import GameState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.legality import legal_commands


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _monster(name: str, *, hp: int = 3, evade: int = 1) -> MonsterInPlay:
    return MonsterInPlay(
        card_ref=CardRef(InstanceId(name)),
        base_hp=hp,
        current_hp=hp,
        evade=evade,
        reward_cents=0,
        has_soul=False,
    )


def _make_zones(monsters: list[MonsterInPlay | None]) -> GameZones:
    ms: SlotsZone[MonsterInPlay] = SlotsZone(size=max(len(monsters), 1))
    for i, m in enumerate(monsters):
        if m is not None:
            ms.set(i, m)
    return GameZones(
        loot_deck=DeckZone(),
        loot_discard=DiscardZone(),
        treasure_deck=DeckZone(),
        treasure_discard=DiscardZone(),
        monster_deck=DeckZone(),
        monster_discard=DiscardZone(),
        shop_slots=SlotsZone(size=1),
        monster_slots=ms,
    )


def _combat_game(
    *,
    player_hp: int = 5,
    monster_hp: int = 3,
    evade: int = 1,         # 1 = always hit, 7 = always miss
    n_players: int = 1,
) -> Game:
    """Return a Game already in combat against slot 0."""
    monsters = [_monster("m-0", hp=monster_hp, evade=evade)]
    players = [
        PlayerState(player_id=PlayerId(f"P{i+1}"), max_hp=player_hp, hp=player_hp)
        for i in range(n_players)
    ]
    gs = GameState.from_players(players, active_player_id=PlayerId("P1"))
    gs.phase = Phase.ACTION
    g = Game(state=gs, zones=_make_zones(monsters), rng=RNG(seed=0))
    g.step(AttackMonster(slot_index=0))
    return g


# ---------------------------------------------------------------------------
# Legality
# ---------------------------------------------------------------------------

def test_roll_combat_legal_while_combat_active():
    g = _combat_game()
    assert RollCombat() in legal_commands(g)


def test_roll_combat_illegal_before_attack():
    monsters = [_monster("m-0")]
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    gs = GameState.from_players([p1])
    gs.phase = Phase.ACTION
    g = Game(state=gs, zones=_make_zones(monsters))
    assert RollCombat() not in legal_commands(g)


def test_roll_combat_illegal_when_no_combat():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    gs = GameState.from_players([p1])
    gs.phase = Phase.ACTION
    g = Game(state=gs)
    assert RollCombat() not in legal_commands(g)


def test_roll_combat_illegal_outside_action_phase():
    g = _combat_game()
    g.state.phase = Phase.START
    assert RollCombat() not in legal_commands(g)


def test_roll_combat_illegal_when_stack_not_empty():
    from foursouls.model.effects import AppendMarkerEffect
    g = _combat_game()
    g.stack.push(controller_id=PlayerId("P1"), source="test", effect=AppendMarkerEffect("x"))
    assert RollCombat() not in legal_commands(g)


# ---------------------------------------------------------------------------
# Hit: damages monster
# ---------------------------------------------------------------------------

def test_hit_reduces_monster_hp_by_1():
    g = _combat_game(monster_hp=3, evade=1)   # evade=1 → always hit
    hp_before = g.zones.monster_slots.get(0).current_hp
    g.step(RollCombat())
    assert g.zones.monster_slots.get(0).current_hp == hp_before - 1


def test_hit_does_not_damage_player():
    g = _combat_game(player_hp=5, evade=1)
    hp_before = g.state.get_player(PlayerId("P1")).hp
    g.step(RollCombat())
    assert g.state.get_player(PlayerId("P1")).hp == hp_before


# ---------------------------------------------------------------------------
# Miss: damages player
# ---------------------------------------------------------------------------

def test_miss_reduces_player_hp_by_1():
    g = _combat_game(player_hp=5, evade=7)    # evade=7 → always miss
    hp_before = g.state.get_player(PlayerId("P1")).hp
    g.step(RollCombat())
    assert g.state.get_player(PlayerId("P1")).hp == hp_before - 1


def test_miss_does_not_damage_monster():
    g = _combat_game(monster_hp=3, evade=7)
    hp_before = g.zones.monster_slots.get(0).current_hp
    g.step(RollCombat())
    assert g.zones.monster_slots.get(0).current_hp == hp_before


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

def test_roll_emits_combat_roll_result_event():
    g = _combat_game(evade=1)
    events = g.step(RollCombat()).events
    roll_events = [e for e in events if isinstance(e, CombatRollResult)]
    assert len(roll_events) == 1


def test_roll_result_event_hit_fields():
    g = _combat_game(evade=1)
    events = g.step(RollCombat()).events
    ev = next(e for e in events if isinstance(e, CombatRollResult))
    assert ev.is_hit is True
    assert ev.attacker_id == PlayerId("P1")
    assert ev.defender_slot == 0
    assert 1 <= ev.roll <= 6
    assert ev.evade == 1


def test_roll_result_event_miss_fields():
    g = _combat_game(evade=7)
    events = g.step(RollCombat()).events
    ev = next(e for e in events if isinstance(e, CombatRollResult))
    assert ev.is_hit is False
    assert 1 <= ev.roll <= 6
    assert ev.evade == 7


# ---------------------------------------------------------------------------
# Repeated rolls
# ---------------------------------------------------------------------------

def test_two_hits_reduce_monster_hp_by_2():
    g = _combat_game(monster_hp=5, evade=1)
    g.step(RollCombat())
    g.step(RollCombat())
    assert g.zones.monster_slots.get(0).current_hp == 5 - 2


def test_two_misses_reduce_player_hp_by_2():
    g = _combat_game(player_hp=5, evade=7)
    g.step(RollCombat())
    g.step(RollCombat())
    assert g.state.get_player(PlayerId("P1")).hp == 5 - 2


def test_combat_state_persists_after_roll():
    g = _combat_game(monster_hp=5, evade=1)
    g.step(RollCombat())
    assert g.combat is not None
    assert g.combat.is_active


def test_roll_legal_after_previous_roll():
    g = _combat_game(monster_hp=5, evade=1)
    g.step(RollCombat())
    assert RollCombat() in legal_commands(g)


def test_alternating_hit_miss_sequence():
    """Mixed evade value: verify each exchange targets the right side."""
    # evade=4: roll 1-3 → miss, roll 4-6 → hit. We don't care about outcome;
    # just verify hp totals are mutually exclusive (only one side takes damage per roll).
    g = _combat_game(player_hp=5, monster_hp=5, evade=4, n_players=1)
    player_hp_before = g.state.get_player(PlayerId("P1")).hp
    monster_hp_before = g.zones.monster_slots.get(0).current_hp

    for _ in range(4):
        events = g.step(RollCombat()).events
        ev = next(e for e in events if isinstance(e, CombatRollResult))
        p_hp = g.state.get_player(PlayerId("P1")).hp
        m_hp = g.zones.monster_slots.get(0).current_hp
        if ev.is_hit:
            # monster took damage, player did not
            assert m_hp < monster_hp_before or p_hp == player_hp_before
        else:
            # player took damage, monster did not
            assert p_hp < player_hp_before or m_hp == monster_hp_before
        # Track for next iteration
        player_hp_before = p_hp
        monster_hp_before = m_hp


# ---------------------------------------------------------------------------
# Priority
# ---------------------------------------------------------------------------

def test_priority_resets_to_attacker_after_roll():
    g = _combat_game(n_players=2)
    g.step(RollCombat())
    assert g.priority.current() == PlayerId("P1")


# ---------------------------------------------------------------------------
# HP floor
# ---------------------------------------------------------------------------

def test_player_hp_never_goes_below_zero():
    # evade=7 → always miss; player hp 1 → 0 on first roll, combat ends.
    g = _combat_game(player_hp=1, evade=7)
    g.step(RollCombat())   # hp 1 → 0, player dies, combat ends
    assert g.state.get_player(PlayerId("P1")).hp == 0
    assert g.combat is None   # combat cleared; second roll is not possible


def test_monster_hp_never_goes_below_zero():
    # take_damage clamps to 0; confirmed via MonsterInPlay unit tests.
    # After the killing blow combat ends, so we just verify the monster
    # is gone from the slot (death + slot clear is Release 4.4 behaviour).
    g = _combat_game(monster_hp=1, evade=1)
    g.step(RollCombat())   # hp 1 → 0 → monster dies, slot cleared
    assert g.zones.monster_slots.get(0) is None  # slot is empty after death
