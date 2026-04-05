"""
Sprint 4 acceptance slice.

Named tests mirror the acceptance criteria and serve as a living spec.
The integration targets prove that every Sprint 4 sub-feature coexists:

  setup_game → reach ACTION → declare attack → deterministic rolls
  → monster death OR player death → cleanup → (win) refill + reward + soul
  → attack_used resets on next turn → end-to-end turn cycle repeatable

Determinism strategy
--------------------
Win path  : monster evade=1 → every roll is a hit; monster hp=1 → dies on roll 1.
            Player cannot miss, so player HP is irrelevant.
Death path: monster evade=7 → every roll is a miss (d6 gives 1–6); player hp=1
            → player dies on roll 1.

Both scenarios run through setup_game for realistic game context.  After setup,
the monster in slot 0 is replaced with a precisely crafted MonsterInPlay so that
the outcome is reproducible regardless of RNG seed.

Sprint 1–3 regression guard
----------------------------
No existing behavior changes in this release; the full suite must pass.
The guard is enforced by running `pytest` at the repository level.
"""
from __future__ import annotations

import agents.combat_bot as combat_bot
from agents.pass_bot import choose_command as pass_command
from foursouls.engine.events import MonsterDied, PlayerDied, RewardGranted, SoulGranted
from foursouls.engine.rng import RNG
from foursouls.model.commands import AttackMonster, EndTurn, RollCombat
from foursouls.model.game_state import GameState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.legality import legal_commands
from foursouls.rulesets.common.setup import setup_game


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_loot_cards(n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"loot-{i}")) for i in range(n)]


def _make_treasure_cards(n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"treasure-{i}")) for i in range(n)]


def _make_monster_cards(n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"monster-{i}")) for i in range(n)]


def _setup(*, player_hp: int = 5, n_players: int = 1, seed: int = 0):
    """
    Minimal but realistic game via setup_game.

    Single monster slot so slot 0 always exists after injection.
    Enough loot/treasure cards to survive the full setup without emptying decks.
    """
    players = [
        PlayerState(player_id=PlayerId(f"P{i+1}"), max_hp=player_hp, hp=player_hp)
        for i in range(n_players)
    ]
    state = GameState.from_players(players, active_player_id=PlayerId("P1"))
    g = setup_game(
        state,
        loot_cards=_make_loot_cards(40),
        treasure_cards=_make_treasure_cards(10),
        monster_cards=_make_monster_cards(6),
        rng=RNG(seed=seed),
        shop_size=3,
        monster_slot_count=1,   # single slot → clean slot-0 assertions
    )
    return g


def _inject_monster(g, *, hp: int, evade: int,
                    reward_cents: int = 0, has_soul: bool = False,
                    name: str = "m-injected") -> MonsterInPlay:
    """Replace the monster in slot 0 with a precisely defined one."""
    m = MonsterInPlay(
        card_ref=CardRef(InstanceId(name)),
        base_hp=hp,
        current_hp=hp,
        evade=evade,
        reward_cents=reward_cents,
        has_soul=has_soul,
    )
    g.zones.monster_slots.set(0, m)
    return m


def _advance_to_action(g) -> None:
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))


def _drive_p1_turn(g, *, max_steps: int = 30) -> list:
    """
    Run combat_bot until P1's turn ends; collect all logged events.

    Termination: a turn ends when turn_number increments (on_end_turn fires),
    regardless of whether there are 1 or 2 players.
    """
    all_events: list = []
    turn_before = g.state.turn_number
    for _ in range(max_steps):
        if g.state.turn_number != turn_before:
            break
        all_events.extend(g.step(combat_bot.choose_command(g)))
    else:
        raise AssertionError("combat_bot did not finish P1's turn within step limit")
    return all_events


# ---------------------------------------------------------------------------
# Win path — monster dies
# ---------------------------------------------------------------------------

def test_win_combat_ends_after_kill():
    """Monster hp=1, evade=1 → dies on the first roll; combat is cleared."""
    g = _setup()
    _inject_monster(g, hp=1, evade=1)
    _advance_to_action(g)

    _drive_p1_turn(g)

    assert g.combat is None


def test_win_monster_slot_cleared_after_kill():
    """Dead monster's slot is empty when deck is exhausted."""
    g = _setup()
    _inject_monster(g, hp=1, evade=1)
    _advance_to_action(g)
    # Drain the monster deck so the slot stays empty after the kill.
    while not g.zones.monster_deck.empty():
        g.zones.monster_deck.draw(1)

    _drive_p1_turn(g)

    assert g.zones.monster_slots.get(0) is None


def test_win_slot_refills_from_deck():
    """Slot 0 is occupied after the kill when the monster deck still has cards."""
    g = _setup()   # setup_game fills monster_deck with leftover monster refs
    _inject_monster(g, hp=1, evade=1)
    _advance_to_action(g)
    assert not g.zones.monster_deck.empty()   # precondition

    _drive_p1_turn(g)

    assert g.zones.monster_slots.is_occupied(0)


def test_win_reward_cents_granted():
    """Attacker gains reward_cents on kill."""
    g = _setup()
    _inject_monster(g, hp=1, evade=1, reward_cents=7)
    p1 = g.state.get_player(PlayerId("P1"))
    p1.cents = 0
    _advance_to_action(g)

    _drive_p1_turn(g)

    assert p1.cents == 7


def test_win_soul_granted_for_soul_monster():
    """Attacker receives the monster's card_ref in their souls list."""
    g = _setup()
    m = _inject_monster(g, hp=1, evade=1, has_soul=True)
    _advance_to_action(g)

    _drive_p1_turn(g)

    assert m.card_ref in g.state.get_player(PlayerId("P1")).souls


def test_win_no_soul_for_non_soul_monster():
    """No soul entry when the killed monster has has_soul=False."""
    g = _setup()
    _inject_monster(g, hp=1, evade=1, has_soul=False)
    _advance_to_action(g)

    _drive_p1_turn(g)

    assert g.state.get_player(PlayerId("P1")).souls == []


def test_win_monster_died_event_in_log():
    g = _setup()
    _inject_monster(g, hp=1, evade=1)
    _advance_to_action(g)

    events = _drive_p1_turn(g)

    assert any(isinstance(e, MonsterDied) for e in events)


def test_win_reward_granted_event_in_log():
    g = _setup()
    _inject_monster(g, hp=1, evade=1, reward_cents=5)
    _advance_to_action(g)

    events = _drive_p1_turn(g)

    reward_evts = [e for e in events if isinstance(e, RewardGranted)]
    assert len(reward_evts) == 1
    assert reward_evts[0].cents == 5


def test_win_soul_granted_event_in_log():
    g = _setup()
    _inject_monster(g, hp=1, evade=1, has_soul=True)
    _advance_to_action(g)

    events = _drive_p1_turn(g)

    soul_evts = [e for e in events if isinstance(e, SoulGranted)]
    assert len(soul_evts) == 1
    assert soul_evts[0].player_id == PlayerId("P1")


def test_win_attack_used_true_after_kill():
    # Check attack_used mid-turn, before EndTurn resets it.
    g = _setup()
    _inject_monster(g, hp=1, evade=1)
    _advance_to_action(g)
    assert not g.state.turn_flags.attack_used   # precondition

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())   # monster dies

    assert g.state.turn_flags.attack_used


def test_win_turn_advances_after_kill():
    """After bot issues EndTurn, the active player changes."""
    g = _setup(n_players=2)
    _inject_monster(g, hp=1, evade=1)
    _advance_to_action(g)

    _drive_p1_turn(g)

    assert g.state.active_player_id == PlayerId("P2")


# ---------------------------------------------------------------------------
# Death path — player dies
# ---------------------------------------------------------------------------

def test_death_combat_cleared_on_player_death():
    """evade=7 → always miss; player hp=1 → dead on first roll."""
    # Check hp before EndTurn heals the player back to max.
    g = _setup(player_hp=1)
    _inject_monster(g, hp=5, evade=7)
    _advance_to_action(g)

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())   # hp 1 → 0; player dies

    assert g.combat is None
    assert g.state.get_player(PlayerId("P1")).hp == 0


def test_death_monster_survives_with_unchanged_hp():
    g = _setup(player_hp=1)
    m = _inject_monster(g, hp=5, evade=7)
    _advance_to_action(g)
    hp_before = m.current_hp

    _drive_p1_turn(g)

    assert g.zones.monster_slots.get(0) is not None
    assert g.zones.monster_slots.get(0).current_hp == hp_before


def test_death_player_died_event_in_log():
    g = _setup(player_hp=1)
    _inject_monster(g, hp=5, evade=7)
    _advance_to_action(g)

    events = _drive_p1_turn(g)

    assert any(isinstance(e, PlayerDied) for e in events)


def test_death_no_reward_on_player_death():
    """When the player dies, no RewardGranted event is emitted."""
    g = _setup(player_hp=1)
    _inject_monster(g, hp=5, evade=7, reward_cents=10)
    p1 = g.state.get_player(PlayerId("P1"))
    cents_before = p1.cents
    _advance_to_action(g)

    events = _drive_p1_turn(g)

    assert not any(isinstance(e, RewardGranted) for e in events)
    assert p1.cents == cents_before


def test_death_no_soul_on_player_death():
    g = _setup(player_hp=1)
    _inject_monster(g, hp=5, evade=7, has_soul=True)
    _advance_to_action(g)

    _drive_p1_turn(g)

    assert g.state.get_player(PlayerId("P1")).souls == []


def test_death_attack_used_true_after_death():
    # Check mid-turn, before EndTurn resets flags.
    g = _setup(player_hp=1)
    _inject_monster(g, hp=5, evade=7)
    _advance_to_action(g)

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())   # player dies

    assert g.state.turn_flags.attack_used


def test_death_end_turn_legal_after_player_death():
    g = _setup(player_hp=1)
    _inject_monster(g, hp=5, evade=7)
    _advance_to_action(g)
    # Drive only through combat (AttackMonster + RollCombat), stop before EndTurn.
    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())   # hp 1 → 0, combat ends

    assert EndTurn() in legal_commands(g)


def test_death_turn_advances_after_player_death():
    """Bot still issues EndTurn after player dies; turn advances normally."""
    g = _setup(player_hp=1, n_players=2)
    _inject_monster(g, hp=5, evade=7)
    _advance_to_action(g)

    _drive_p1_turn(g)

    assert g.state.active_player_id == PlayerId("P2")


# ---------------------------------------------------------------------------
# Attack-used resets on next turn
# ---------------------------------------------------------------------------

def test_attack_used_resets_on_next_turn_after_win():
    """After EndTurn, the new active player starts with attack_used=False."""
    g = _setup(n_players=2)
    _inject_monster(g, hp=1, evade=1)
    _advance_to_action(g)
    _drive_p1_turn(g)   # P1 wins combat, ends turn → P2 active

    assert g.state.active_player_id == PlayerId("P2")
    assert not g.state.turn_flags.attack_used


def test_attack_used_resets_on_p1_second_turn():
    """P1's attack_used is False again when P1's second turn reaches ACTION."""
    g = _setup(n_players=2)
    _inject_monster(g, hp=1, evade=1)
    _advance_to_action(g)
    _drive_p1_turn(g)   # P1 kills, ends turn

    # Drive P2's full turn with pass_bot
    while g.state.active_player_id == PlayerId("P2"):
        g.step(pass_command(g))

    # P1's second turn
    assert g.state.active_player_id == PlayerId("P1")
    _advance_to_action(g)
    assert not g.state.turn_flags.attack_used


def test_attack_used_resets_on_next_turn_after_death():
    g = _setup(player_hp=1, n_players=2)
    _inject_monster(g, hp=5, evade=7)
    _advance_to_action(g)
    _drive_p1_turn(g)   # P1 dies, ends turn → P2 active

    assert g.state.active_player_id == PlayerId("P2")
    assert not g.state.turn_flags.attack_used


# ---------------------------------------------------------------------------
# Full integration target — win path
# ---------------------------------------------------------------------------

def test_sprint4_integration_full_win_flow():
    """
    Integration target (win path):
      setup_game → START → ACTION
      P1 attacks slot 0 (hp=1, evade=1 → guaranteed kill on first roll)
      → MonsterDied, RewardGranted(7), SoulGranted
      → slot refills from deck
      → attack_used = True
      → EndTurn: P2 active, turn_number advances, attack_used resets
      → P2 passes through their turn
      → P1's second turn: attack_used = False
    """
    g = _setup(n_players=2, seed=42)
    m = _inject_monster(g, hp=1, evade=1, reward_cents=7, has_soul=True, name="m-target")
    deck_size_before = len(g.zones.monster_deck)
    _advance_to_action(g)

    assert g.state.phase == Phase.ACTION
    assert not g.state.turn_flags.attack_used

    # Run P1's full turn
    p1_events = _drive_p1_turn(g)

    # Combat resolved cleanly
    assert g.combat is None

    # Slot refilled (deck had cards)
    assert g.zones.monster_slots.is_occupied(0)
    assert len(g.zones.monster_deck) == deck_size_before - 1

    # Rewards granted
    assert g.state.get_player(PlayerId("P1")).cents == 7
    assert m.card_ref in g.state.get_player(PlayerId("P1")).souls

    # Events fired exactly once each
    assert len([e for e in p1_events if isinstance(e, MonsterDied)]) == 1
    assert len([e for e in p1_events if isinstance(e, RewardGranted)]) == 1
    assert len([e for e in p1_events if isinstance(e, SoulGranted)]) == 1

    # Turn advanced
    assert g.state.active_player_id == PlayerId("P2")
    assert g.state.turn_number == 2
    assert not g.state.turn_flags.attack_used

    # Drive P2's full turn with pass_bot
    while g.state.active_player_id == PlayerId("P2"):
        g.step(pass_command(g))

    # P1's second turn — attack available again
    assert g.state.active_player_id == PlayerId("P1")
    _advance_to_action(g)
    assert not g.state.turn_flags.attack_used
    assert any(isinstance(c, AttackMonster) for c in legal_commands(g))


# ---------------------------------------------------------------------------
# Full integration target — death path
# ---------------------------------------------------------------------------

def test_sprint4_integration_full_death_flow():
    """
    Integration target (death path):
      setup_game → START → ACTION
      P1 attacks slot 0 (evade=7, player hp=1 → player dies on first roll)
      → PlayerDied; no RewardGranted, no SoulGranted
      → monster still in slot with full hp
      → attack_used = True
      → EndTurn: P2 active, attack_used resets
      → P2 passes through their turn
      → P1's second turn: attack_used = False, hp healed to max
    """
    g = _setup(player_hp=1, n_players=2, seed=0)
    m = _inject_monster(g, hp=5, evade=7, reward_cents=10, has_soul=True, name="m-unkillable")
    _advance_to_action(g)

    p1_cents_before = g.state.get_player(PlayerId("P1")).cents

    # Drive only the combat (attack + one roll); stop before EndTurn.
    combat_events: list = []
    combat_events.extend(g.step(AttackMonster(slot_index=0)))
    combat_events.extend(g.step(RollCombat()))   # hp 1 → 0; player dies

    # Player died; combat cleared — checked before EndTurn heals.
    assert g.combat is None
    assert g.state.get_player(PlayerId("P1")).hp == 0

    # Monster untouched
    assert g.zones.monster_slots.get(0) is m
    assert m.current_hp == 5

    # No rewards
    assert not any(isinstance(e, RewardGranted) for e in combat_events)
    assert not any(isinstance(e, SoulGranted) for e in combat_events)
    assert g.state.get_player(PlayerId("P1")).cents == p1_cents_before
    assert g.state.get_player(PlayerId("P1")).souls == []

    # PlayerDied event present
    assert any(isinstance(e, PlayerDied) for e in combat_events)

    # Attack consumed
    assert g.state.turn_flags.attack_used

    # Now let the bot issue EndTurn and drive the rest of P1's turn.
    p1_events = _drive_p1_turn(g)

    # Turn advanced
    assert g.state.active_player_id == PlayerId("P2")
    assert g.state.turn_number == 2
    assert not g.state.turn_flags.attack_used

    # Drive P2
    while g.state.active_player_id == PlayerId("P2"):
        g.step(pass_command(g))

    # P1's second turn — healed to max and attack available again
    assert g.state.active_player_id == PlayerId("P1")
    _advance_to_action(g)
    assert not g.state.turn_flags.attack_used
    assert g.state.get_player(PlayerId("P1")).hp == g.state.get_player(PlayerId("P1")).max_hp
