"""
Release 4.5 — Player death + combat cancellation tests.

Strategy:
  evade=7 → roll >= 7 never → guaranteed miss → player takes damage every roll.
  evade=1 → roll >= 1 always → guaranteed hit  → monster takes damage every roll.

Covers:
- player death exits combat
- monster survives with unchanged hp if player dies first
- attack_used remains True after player death
- PlayerDied event emitted with correct fields
- RollCombat illegal after player death (combat over)
- player death does not trigger a second cleanup (game.combat is None, not cleared twice)
- post-death state is stable: EndTurn is legal, phase unchanged, priority on attacker
- player death does not double-trigger when hp already 0 on a subsequent miss (no second event)
- multi-miss path: player survives several misses then dies on the last one
"""
from __future__ import annotations

import pytest

from foursouls.engine.events import PlayerDied
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import AttackMonster, EndTurn, PassPriority, RollCombat
from foursouls.model.game_state import GameState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.legality import legal_commands


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _monster(name: str = "m-0", *, hp: int = 5, evade: int = 7) -> MonsterInPlay:
    """Default: high evade → always misses → player takes all damage."""
    return MonsterInPlay(
        card_ref=CardRef(InstanceId(name)),
        base_hp=hp,
        current_hp=hp,
        evade=evade,
        reward_coin=0,
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


def _roll_miss(g: Game) -> tuple:
    """
    Roll once (guaranteed miss for evade=7) and drain the CombatMissDamageEffect
    from the stack by passing priority.  Returns a tuple of all events from
    both steps combined.

    R14.1: miss damage is now a stack item, so damage only applies after the
    priority holder passes.  Single-player games need exactly one pass.
    """
    roll_events = g.step(RollCombat()).events
    resolve_events = g.step(PassPriority()).events
    return roll_events + resolve_events


def _game(*, player_hp: int = 1, monster_hp: int = 5, evade: int = 7) -> Game:
    """
    Return a Game already in combat against slot 0.

    Default: player_hp=1, evade=7 (always miss) → player dies on the first roll.
    """
    monsters = [_monster(hp=monster_hp, evade=evade)]
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=player_hp, hp=player_hp)
    gs = GameState.from_players([p1], active_player_id=PlayerId("P1"))
    gs.phase = Phase.ACTION
    g = Game(state=gs, zones=_make_zones(monsters), rng=RNG(seed=0))
    g.step(AttackMonster(slot_index=0))
    return g


# ---------------------------------------------------------------------------
# Combat exits on player death
# ---------------------------------------------------------------------------

def test_player_death_clears_combat():
    g = _game(player_hp=1)
    _roll_miss(g)
    assert g.combat is None


def test_roll_combat_illegal_after_player_death():
    g = _game(player_hp=1)
    _roll_miss(g)
    assert RollCombat() not in legal_commands(g)


# ---------------------------------------------------------------------------
# Monster survives
# ---------------------------------------------------------------------------

def test_monster_hp_unchanged_when_player_dies():
    g = _game(player_hp=1, monster_hp=5, evade=7)
    monster_hp_before = g.zones.monster_slots.get(0).current_hp
    _roll_miss(g)
    # Monster is still in slot and has taken no damage
    assert g.zones.monster_slots.get(0) is not None
    assert g.zones.monster_slots.get(0).current_hp == monster_hp_before


def test_monster_slot_occupied_after_player_death():
    g = _game(player_hp=1)
    _roll_miss(g)
    assert g.zones.monster_slots.is_occupied(0)


# ---------------------------------------------------------------------------
# Attack remains spent
# ---------------------------------------------------------------------------

def test_attack_used_true_after_player_death():
    g = _game(player_hp=1)
    _roll_miss(g)
    assert g.state.turn_flags.attack_used is True


# ---------------------------------------------------------------------------
# PlayerDied event
# ---------------------------------------------------------------------------

def test_player_died_event_emitted():
    g = _game(player_hp=1)
    events = _roll_miss(g)  # PlayerDied now comes from the PassPriority resolution
    death_events = [e for e in events if isinstance(e, PlayerDied)]
    assert len(death_events) == 1


def test_player_died_event_fields():
    g = _game(player_hp=1)
    events = _roll_miss(g)
    ev = next(e for e in events if isinstance(e, PlayerDied))
    assert ev.player_id == PlayerId("P1")
    assert ev.slot_index == 0


def test_no_player_died_event_on_surviving_player():
    g = _game(player_hp=5, evade=7)   # survives the first miss
    # R14.1: roll step pushes miss damage; no PlayerDied yet
    events = g.step(RollCombat()).events
    assert not any(isinstance(e, PlayerDied) for e in events)
    # Resolve — player loses 1 HP but still alive
    g.step(PassPriority())
    assert g.state.get_player(PlayerId("P1")).hp == 4


# ---------------------------------------------------------------------------
# No double-trigger
# ---------------------------------------------------------------------------

def test_player_death_emits_exactly_one_event():
    """Even if hp is already 0, a second roll must not be possible."""
    g = _game(player_hp=1)
    events = _roll_miss(g)   # hp 1 → 0, combat ends
    assert len([e for e in events if isinstance(e, PlayerDied)]) == 1
    # Combat is gone; cannot roll again
    assert g.combat is None


# ---------------------------------------------------------------------------
# Post-death state is stable
# ---------------------------------------------------------------------------

def test_end_turn_legal_after_player_death():
    g = _game(player_hp=1)
    _roll_miss(g)
    assert EndTurn() in legal_commands(g)


def test_phase_is_end_after_active_player_death():
    # R7.3: active-player death advances phase from ACTION to END.
    g = _game(player_hp=1)
    _roll_miss(g)
    assert g.state.phase == Phase.END


def test_priority_on_attacker_after_player_death():
    g = _game(player_hp=1)
    _roll_miss(g)
    assert g.priority.current() == PlayerId("P1")


def test_player_hp_is_zero_after_death():
    g = _game(player_hp=1)
    _roll_miss(g)
    assert g.state.get_player(PlayerId("P1")).hp == 0


# ---------------------------------------------------------------------------
# Multi-miss path: player survives N-1 misses then dies on the last one
# ---------------------------------------------------------------------------

def test_player_dies_after_multiple_misses():
    g = _game(player_hp=3, evade=7)  # 3 misses needed

    _roll_miss(g)
    assert g.state.get_player(PlayerId("P1")).hp == 2
    assert g.combat is not None

    _roll_miss(g)
    assert g.state.get_player(PlayerId("P1")).hp == 1
    assert g.combat is not None

    events = _roll_miss(g)    # killing miss
    assert g.state.get_player(PlayerId("P1")).hp == 0
    assert g.combat is None
    assert any(isinstance(e, PlayerDied) for e in events)
