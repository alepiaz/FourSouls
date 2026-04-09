"""
R7.4 — died_this_turn guard on TurnFlags; a player can only die once per turn.

Invariants tested
-----------------
- TurnFlags.died_this_turn defaults to False.
- resolve_player_death sets died_this_turn = True.
- died_this_turn resets to False on the next turn (via TurnFlags.reset()).
- A second death trigger in the same turn (hp already 0, guard active) emits no
  second PlayerDied event and does not call resolve_player_death again.

Sprint 7 acceptance
-------------------
Drive P1 (hp=1) to death, verify the flag, end the turn, verify it resets.
"""
from __future__ import annotations

import agents.combat_bot as combat_bot
from agents.pass_bot import choose_command as pass_command
from foursouls.engine.events import DeathPenaltyPaid, PlayerDied
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import AttackMonster, RollCombat
from foursouls.model.game_state import GameState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.setup import setup_game


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ref(name: str) -> CardRef:
    return CardRef(InstanceId(name))


def _miss_monster(hp: int = 5) -> MonsterInPlay:
    """evade=7 → always misses → player takes damage every roll."""
    return MonsterInPlay(
        card_ref=_ref("m-0"),
        base_hp=hp,
        current_hp=hp,
        evade=7,
        reward_cents=0,
        has_soul=False,
    )


def _game(*, player_hp: int = 1, n_players: int = 1) -> Game:
    players = [
        PlayerState(player_id=PlayerId(f"P{i+1}"), max_hp=player_hp, hp=player_hp)
        for i in range(n_players)
    ]
    state = GameState.from_players(players, active_player_id=PlayerId("P1"))
    state.phase = Phase.ACTION

    ms: SlotsZone[MonsterInPlay] = SlotsZone(size=1)
    ms.set(0, _miss_monster())

    zones = GameZones(
        loot_deck=DeckZone(),
        loot_discard=DiscardZone(),
        treasure_deck=DeckZone(),
        treasure_discard=DiscardZone(),
        monster_deck=DeckZone(),
        monster_discard=DiscardZone(),
        shop_slots=SlotsZone(size=1),
        monster_slots=ms,
    )
    g = Game(state=state, zones=zones, rng=RNG(seed=0))
    g.step(AttackMonster(slot_index=0))
    return g


# ---------------------------------------------------------------------------
# TurnFlags default
# ---------------------------------------------------------------------------

def test_died_this_turn_defaults_false():
    g = _game()
    assert g.state.turn_flags.died_this_turn is False


# ---------------------------------------------------------------------------
# Flag set on death
# ---------------------------------------------------------------------------

def test_died_this_turn_true_after_death():
    g = _game(player_hp=1)
    g.step(RollCombat())   # miss → hp 1→0 → resolve_player_death
    assert g.state.turn_flags.died_this_turn is True


def test_exactly_one_player_died_event():
    g = _game(player_hp=1)
    result = g.step(RollCombat())
    assert len([e for e in result.events if isinstance(e, PlayerDied)]) == 1


def test_exactly_one_death_penalty_event():
    g = _game(player_hp=1)
    result = g.step(RollCombat())
    assert len([e for e in result.events if isinstance(e, DeathPenaltyPaid)]) == 1


# ---------------------------------------------------------------------------
# Guard: second death trigger in same turn is suppressed
# ---------------------------------------------------------------------------

def test_guard_suppresses_second_death_trigger():
    """
    Manually set hp=0 and died_this_turn=True, then inject another miss scenario.
    The guard in resolve_roll must prevent a second PlayerDied from being emitted.

    We simulate this by pre-setting died_this_turn on a fresh game, letting a
    miss reduce hp below 0 (already 0), and confirming no PlayerDied is emitted.
    """
    g = _game(player_hp=2)   # two-hp player: first miss brings to 1, not dead yet
    # After AttackMonster, take one miss to reach hp=1 (still alive)
    g.step(RollCombat())   # hp 2→1, combat still active
    assert g.state.get_player(PlayerId("P1")).hp == 1
    assert g.combat is not None

    # Manually pre-set the guard as if death already happened this turn
    g.state.turn_flags.died_this_turn = True
    # Also manually drop hp to 0 to simulate the "already dead" state
    g.state.get_player(PlayerId("P1")).hp = 0

    # Another roll: is_hit=False (evade=7), hp already 0 — guard must block
    result = g.step(RollCombat())
    assert not any(isinstance(e, PlayerDied) for e in result.events)
    assert not any(isinstance(e, DeathPenaltyPaid) for e in result.events)


# ---------------------------------------------------------------------------
# Flag resets on new turn
# ---------------------------------------------------------------------------

def test_died_this_turn_resets_on_new_turn():
    """
    P1 dies, ends their turn; after EndTurn the new turn's TurnFlags must have
    died_this_turn=False.
    """
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=1, hp=1)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=4, hp=4)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))

    monster_cards = [_ref(f"m-{i}") for i in range(4)]
    loot_cards = [_ref(f"loot-{i}") for i in range(20)]
    treasure_cards = [_ref(f"treasure-{i}") for i in range(6)]

    g = setup_game(
        state,
        loot_cards=loot_cards,
        treasure_cards=treasure_cards,
        monster_cards=monster_cards,
        rng=RNG(seed=0),
        monster_slot_count=1,
    )
    g.zones.monster_slots.set(0, _miss_monster())

    # Advance through START → ACTION
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    # P1 attacks and dies
    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())
    assert g.state.turn_flags.died_this_turn is True

    # P1 ends their turn (phase is END after active-player death)
    g.step(pass_command(g))   # PassPriority accepted, then EndTurn via bot
    # Drive until P2 is active
    turn_before = g.state.turn_number
    for _ in range(10):
        if g.state.active_player_id == PlayerId("P2"):
            break
        g.step(combat_bot.choose_command(g))

    assert g.state.active_player_id == PlayerId("P2")
    assert g.state.turn_flags.died_this_turn is False


# ---------------------------------------------------------------------------
# Sprint 7 acceptance — full death flow with flag lifecycle
# ---------------------------------------------------------------------------

def test_sprint7_acceptance_died_this_turn_lifecycle():
    """
    Full sprint-7 acceptance:
      setup → P1 (hp=1) attacks guaranteed-miss monster →
      P1 dies → died_this_turn=True, phase=END →
      combat_bot issues EndTurn →
      P2's turn: died_this_turn=False →
      P2 passes → P1's second turn: died_this_turn=False, hp healed.
    """
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=1, hp=1)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=4, hp=4)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))

    g = setup_game(
        state,
        loot_cards=[_ref(f"loot-{i}") for i in range(20)],
        treasure_cards=[_ref(f"treasure-{i}") for i in range(6)],
        monster_cards=[_ref(f"m-{i}") for i in range(4)],
        rng=RNG(seed=0),
        monster_slot_count=1,
    )
    g.zones.monster_slots.set(0, _miss_monster())

    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    # P1 attacks and dies
    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

    assert g.state.get_player(PlayerId("P1")).hp == 0
    assert g.state.turn_flags.died_this_turn is True
    assert g.state.phase == Phase.END

    # Drive P1's END phase to EndTurn
    turn_start = g.state.turn_number
    for _ in range(10):
        if g.state.turn_number != turn_start:
            break
        g.step(combat_bot.choose_command(g))

    # P2's turn: flag reset
    assert g.state.active_player_id == PlayerId("P2")
    assert g.state.turn_flags.died_this_turn is False

    # Drive P2's whole turn with pass_bot
    while g.state.active_player_id == PlayerId("P2"):
        g.step(pass_command(g))

    # P1's second turn: healed, flag still False
    assert g.state.active_player_id == PlayerId("P1")
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    assert g.state.get_player(PlayerId("P1")).hp == 1   # healed to max_hp=1
    assert g.state.turn_flags.died_this_turn is False
    assert not g.state.turn_flags.attack_used
