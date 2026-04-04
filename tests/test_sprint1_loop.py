"""
Sprint 1 integration test — D2 + D5 acceptance proof.

D2: simulate 3 full turns using a pass bot (PASS until EndTurn is legal).
D5: event log emitted during EndTurn captures TurnEnded, ActivePlayerChanged,
    PhaseChanged, and StackItemPushed(Loot1) in a single step.
"""
from agents.pass_bot import choose_command
from foursouls.engine.events import (
    ActivePlayerChanged,
    PhaseChanged,
    StackItemPushed,
    TurnEnded,
)
from foursouls.engine.rng import RNG
from foursouls.model.game_state import GameState
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.setup import setup_game
from foursouls.rulesets.common.turn import enter_start_phase


def _make_cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _new_game():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    return setup_game(
        state,
        loot_cards=_make_cards("loot", 40),
        treasure_cards=_make_cards("treasure", 10),
        monster_cards=_make_cards("monster", 10),
        rng=RNG(seed=1),
    )


def test_simulate_three_turns():
    """
    D2 acceptance: drive the game through 3 complete turns using only PASS
    and END_TURN.  After 3 turns the turn_number must be 4 (incremented once
    per EndTurn).
    """
    g = _new_game()
    enter_start_phase(g)  # queue Loot1 for P1 (turn 1)

    player_sequence = []

    for _ in range(60):  # hard ceiling to catch infinite loops
        if g.state.turn_number > 3:
            break
        cmd = choose_command(g)
        from foursouls.model.commands import EndTurn
        if isinstance(cmd, EndTurn):
            player_sequence.append(g.state.active_player_id)
        g.step(cmd)

    assert g.state.turn_number == 4, f"Expected turn 4, got {g.state.turn_number}"

    # Turn rotation: P1 → P2 → P1 (2-player cycle)
    assert player_sequence == [
        PlayerId("P1"),
        PlayerId("P2"),
        PlayerId("P1"),
    ]

    # Each player received loot every turn they were active
    p1_hand = g.state.get_player(PlayerId("P1")).hand
    p2_hand = g.state.get_player(PlayerId("P2")).hand
    # P1 was active in turns 1 and 3 → 2 extra loot cards on top of starting hand
    assert len(p1_hand) == 3 + 2   # starting 3 + 2 Loot1 draws
    # P2 was active in turn 2 → 1 extra loot card
    assert len(p2_hand) == 3 + 1


def test_end_turn_step_emits_milestone_events():
    """
    D5 acceptance: the events returned from step(EndTurn) must include
    TurnEnded, ActivePlayerChanged, PhaseChanged(ACTION→START),
    and StackItemPushed(label='Loot1').
    """
    g = _new_game()
    enter_start_phase(g)

    # Drive to ACTION phase
    while g.state.phase != Phase.ACTION:
        g.step(choose_command(g))

    events = g.step(choose_command(g))  # EndTurn step

    names = [e.name for e in events]

    assert "TurnEnded" in names
    assert "ActivePlayerChanged" in names
    assert "PhaseChanged" in names
    assert "StackItemPushed" in names  # Loot1 queued for next player

    turn_ended = next(e for e in events if isinstance(e, TurnEnded))
    assert turn_ended.player_id == PlayerId("P1")
    assert turn_ended.turn_number == 1

    player_changed = next(e for e in events if isinstance(e, ActivePlayerChanged))
    assert player_changed.old_player_id == PlayerId("P1")
    assert player_changed.new_player_id == PlayerId("P2")

    phase_changed = next(e for e in events if isinstance(e, PhaseChanged))
    assert phase_changed.old_phase == Phase.ACTION
    assert phase_changed.new_phase == Phase.START

    loot1_pushed = next(e for e in events if isinstance(e, StackItemPushed))
    assert loot1_pushed.label == "Loot1"
    assert loot1_pushed.controller_id == PlayerId("P2")
