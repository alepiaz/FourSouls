from foursouls.engine.stack import Stack
from foursouls.model.commands import EndTurn, PassPriority
from foursouls.model.effects import AppendMarkerEffect
from foursouls.model.game_state import GameState
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import PlayerId
from foursouls.rulesets.common.legality import legal_commands


def _state(phase: Phase = Phase.ACTION) -> GameState:
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    gs = GameState.from_players([p1])
    gs.phase = phase
    return gs


def test_pass_always_legal():
    cmds = legal_commands(_state(Phase.START), Stack())
    assert any(isinstance(c, PassPriority) for c in cmds)


def test_end_turn_legal_in_action_phase_with_empty_stack():
    cmds = legal_commands(_state(Phase.ACTION), Stack())
    assert any(isinstance(c, EndTurn) for c in cmds)


def test_end_turn_illegal_when_stack_not_empty():
    stack = Stack()
    stack.push(
        controller_id=PlayerId("P1"),
        source="test",
        effect=AppendMarkerEffect("x"),
    )
    cmds = legal_commands(_state(Phase.ACTION), stack)
    assert not any(isinstance(c, EndTurn) for c in cmds)


def test_end_turn_illegal_outside_action_phase():
    for phase in (Phase.START, Phase.END):
        cmds = legal_commands(_state(phase), Stack())
        assert not any(isinstance(c, EndTurn) for c in cmds), f"EndTurn should not be legal in {phase}"
