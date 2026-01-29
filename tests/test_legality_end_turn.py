from foursouls.engine.game_loop import Game
from foursouls.model.commands import EndTurn, PassPriority
from foursouls.model.effects import AppendMarkerEffect
from foursouls.model.game_state import GameState
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import PlayerId
from foursouls.model.turn_state import TurnPhase


def _game_two_players_active_p1() -> Game:
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)
    gs = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    return Game(gs)


def test_end_turn_not_legal_by_default_phase_start():
    g = _game_two_players_active_p1()
    kinds = [c.kind for c in g.legal_commands()]
    assert "END_TURN" not in kinds


def test_end_turn_legal_only_in_action_phase_and_stack_empty_and_active_has_priority():
    g = _game_two_players_active_p1()
    g.state.turn.phase = TurnPhase.ACTION  # simulate being in action phase

    # stack empty, active has priority => legal
    kinds = [c.kind for c in g.legal_commands()]
    assert "END_TURN" in kinds


def test_end_turn_not_legal_if_stack_not_empty():
    g = _game_two_players_active_p1()
    g.state.turn.phase = TurnPhase.ACTION

    g.push_to_stack(
        controller_id=PlayerId("P1"),
        source="test",
        effect=AppendMarkerEffect("X"),
        label="X",
    )
    kinds = [c.kind for c in g.legal_commands()]
    assert "END_TURN" not in kinds


def test_step_end_turn_rejected_if_illegal():
    g = _game_two_players_active_p1()
    # still START phase => illegal
    try:
        g.step(EndTurn())
        assert False, "Expected ValueError for illegal EndTurn"
    except ValueError:
        pass


def test_end_turn_stays_legal_after_pass_when_action_and_stack_empty():
    g = _game_two_players_active_p1()
    g.state.turn.phase = TurnPhase.ACTION

    # Initially legal
    assert "END_TURN" in [c.kind for c in g.legal_commands()]

    # Pass once (would normally move priority away)
    g.step(PassPriority())

    # With Option B snap-back, active should still have priority => END_TURN still legal
    assert "END_TURN" in [c.kind for c in g.legal_commands()]
