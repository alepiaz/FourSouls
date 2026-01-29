from foursouls.engine.events import (
    EffectFizzled,
    PriorityPassed,
    StackItemResolved,
    WindowEnded,
)
from foursouls.engine.game_loop import Game
from foursouls.model.commands import PassPriority
from foursouls.model.effects import AlwaysFizzleEffect, AppendMarkerEffect
from foursouls.model.game_state import GameState
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import PlayerId
from foursouls.model.turn_state import TurnPhase


def _game_two_players_active_p1() -> Game:
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)
    gs = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    gs.turn.phase = TurnPhase.ACTION  # prevent auto Loot1 scheduling in kernel tests
    return Game(gs)


def test_pass_pass_resolves_one_item():
    g = _game_two_players_active_p1()

    g.push_to_stack(
        controller_id=PlayerId("P1"),
        source="test",
        effect=AppendMarkerEffect("A"),
        label="A",
    )

    e1 = g.step(PassPriority())
    assert any(isinstance(e, PriorityPassed) for e in e1)
    assert g.state.debug_markers == []

    e2 = g.step(PassPriority())
    assert any(isinstance(e, StackItemResolved) for e in e2)
    assert g.state.debug_markers == ["A"]


def test_resolves_lifo_order_two_items():
    g = _game_two_players_active_p1()

    g.push_to_stack(
        controller_id=PlayerId("P1"),
        source="test",
        effect=AppendMarkerEffect("A"),
        label="A",
    )
    g.push_to_stack(
        controller_id=PlayerId("P1"),
        source="test",
        effect=AppendMarkerEffect("B"),
        label="B",
    )

    # First resolution cycle resolves B
    g.step(PassPriority())
    g.step(PassPriority())
    assert g.state.debug_markers == ["B"]

    # Second resolution cycle resolves A
    g.step(PassPriority())
    g.step(PassPriority())
    assert g.state.debug_markers == ["B", "A"]


def test_effect_fizzles_emits_event():
    g = _game_two_players_active_p1()

    g.push_to_stack(
        controller_id=PlayerId("P1"),
        source="test",
        effect=AlwaysFizzleEffect(),
        label="F",
    )

    g.step(PassPriority())
    events = g.step(PassPriority())

    assert any(isinstance(e, EffectFizzled) for e in events)
    assert g.state.debug_markers == []


def test_window_ends_when_stack_empty_and_all_pass():
    g = _game_two_players_active_p1()

    g.step(PassPriority())
    events = g.step(PassPriority())

    assert any(isinstance(e, WindowEnded) for e in events)
