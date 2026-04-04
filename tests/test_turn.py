from foursouls.engine.rng import RNG
from foursouls.model.commands import EndTurn, PassPriority
from foursouls.model.game_state import GameState
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.setup import setup_game
from foursouls.rulesets.common.turn import enter_start_phase


def _make_cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _game_two_players():
    """Two-player game fully set up with zones, Loot1 NOT yet queued."""
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    return setup_game(
        state,
        loot_cards=_make_cards("loot", 20),
        treasure_cards=_make_cards("treasure", 10),
        monster_cards=_make_cards("monster", 10),
        rng=RNG(seed=0),
    )


def test_start_phase_queues_loot1():
    g = _game_two_players()
    assert g.stack.empty()

    enter_start_phase(g)

    assert not g.stack.empty()
    assert g.stack.top().label == "Loot1"
    assert g.stack.top().controller_id == PlayerId("P1")
    assert g.state.phase == Phase.START


def test_after_loot1_resolves_and_all_passed_phase_becomes_action():
    g = _game_two_players()
    enter_start_phase(g)   # stack: [Loot1], phase: START

    hand_before = len(g.state.get_player(PlayerId("P1")).hand)

    # Both pass → Loot1 resolves (draws 1 card), stack becomes empty
    g.step(PassPriority())  # P1 passes
    g.step(PassPriority())  # P2 passes → Loot1 resolved
    assert g.stack.empty()
    assert g.state.phase == Phase.START  # still START; need one more pass cycle
    assert len(g.state.get_player(PlayerId("P1")).hand) == hand_before + 1

    # Both pass again on empty stack → AllPlayersPassed → START→ACTION
    g.step(PassPriority())  # P1 passes
    g.step(PassPriority())  # P2 passes → AllPlayersPassed

    assert g.state.phase == Phase.ACTION


def test_end_turn_advances_player_and_phase_start_and_queues_loot1():
    g = _game_two_players()
    enter_start_phase(g)

    # Advance through START phase so we can reach ACTION
    g.step(PassPriority())
    g.step(PassPriority())  # Loot1 resolves
    g.step(PassPriority())
    g.step(PassPriority())  # AllPlayersPassed → ACTION
    assert g.state.phase == Phase.ACTION

    p1 = g.state.get_player(PlayerId("P1"))
    p1.hp = 1  # damage P1 to verify heal

    g.step(EndTurn())

    # Active player advanced to P2
    assert g.state.active_player_id == PlayerId("P2")
    # Phase reset to START
    assert g.state.phase == Phase.START
    # Turn number bumped
    assert g.state.turn_number == 2
    # P1 healed to full
    assert p1.hp == p1.max_hp
    # Loot1 queued for P2
    assert not g.stack.empty()
    assert g.stack.top().label == "Loot1"
    assert g.stack.top().controller_id == PlayerId("P2")
