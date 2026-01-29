from foursouls.model.effects import AppendMarkerEffect, AlwaysFizzleEffect
from foursouls.model.game_state import GameState
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import PlayerId


def _gs():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)
    return GameState.from_players([p1, p2])


def test_append_marker_effect_applies():
    gs = _gs()
    eff = AppendMarkerEffect("A")

    assert eff.validate(gs)
    eff.apply(gs)

    assert gs.debug_markers == ["A"]


def test_always_fizzle_effect_validates_false():
    gs = _gs()
    eff = AlwaysFizzleEffect()

    assert not eff.validate(gs)
