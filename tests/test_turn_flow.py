from foursouls.engine.events import StackItemResolved
from foursouls.engine.game_loop import Game
from foursouls.model.commands import EndTurn, PassPriority
from foursouls.model.game_state import GameState
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.model.turn_state import TurnPhase
from foursouls.engine.zones import DeckZone


def test_loot1_is_scheduled_in_start_and_moves_to_action_on_resolution():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)

    deck = DeckZone(
        cards=[CardRef(InstanceId("L1")), CardRef(InstanceId("L2"))]
    )  # L2 is top
    gs = GameState.from_players(
        [p1, p2], active_player_id=PlayerId("P1"), loot_deck=deck
    )

    g = Game(gs)

    # First PASS should schedule Loot1 and pass priority
    g.step(PassPriority())
    assert g.state.turn.phase == TurnPhase.START  # still START until Loot1 resolves

    # Second PASS resolves Loot1 (all passed)
    events = g.step(PassPriority())
    assert any(isinstance(e, StackItemResolved) and e.label == "LOOT_1" for e in events)

    # Active player drew 1 loot
    assert len(g.state.get_player(PlayerId("P1")).hand) == 1
    assert g.state.get_player(PlayerId("P1")).hand[0].instance_id == InstanceId(
        "L2"
    )  # top drawn
    assert g.state.turn.phase == TurnPhase.ACTION


def test_end_turn_advances_player_and_schedules_next_loot1():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)

    deck = DeckZone(
        cards=[
            CardRef(InstanceId("A")),
            CardRef(InstanceId("B")),
            CardRef(InstanceId("C")),
        ]
    )
    gs = GameState.from_players(
        [p1, p2], active_player_id=PlayerId("P1"), loot_deck=deck
    )
    g = Game(gs)

    # Resolve P1 Loot1 -> ACTION
    g.step(PassPriority())
    g.step(PassPriority())
    assert g.state.turn.phase == TurnPhase.ACTION
    assert g.state.active_player_id == PlayerId("P1")
    assert g.state.turn.number == 1

    # End turn -> should advance to P2 and schedule Loot1 for P2 (stack non-empty)
    g.step(EndTurn())
    assert g.state.active_player_id == PlayerId("P2")
    assert g.state.turn.number == 2
    assert g.state.turn.phase == TurnPhase.START
