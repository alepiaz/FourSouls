from foursouls.engine.rng import RNG
from foursouls.model.effect_context import EffectContext
from foursouls.model.effects import AppendMarkerEffect, AlwaysFizzleEffect
from foursouls.model.game_state import GameState
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import PlayerId


def _ctx():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)
    gs = GameState.from_players([p1, p2])
    return EffectContext(state=gs, rng=RNG(seed=0))


def test_append_marker_effect_applies():
    ctx = _ctx()
    eff = AppendMarkerEffect("A")

    assert eff.validate(ctx)
    eff.apply(ctx)

    assert ctx.state.debug_markers == ["A"]


def test_always_fizzle_effect_validates_false():
    ctx = _ctx()
    eff = AlwaysFizzleEffect()

    assert not eff.validate(ctx)
