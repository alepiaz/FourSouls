from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game
    from foursouls.model.effects import Effect


# Event-card effect factories remain imperative until their roll branches move
# onto the shared dice stack in Sprint 15.


def _resolve_inline_effect(cfg: dict, game: "Game") -> "Effect":
    from foursouls.rulesets.common.effects import (
        DealDamageEffect,
        DrawLoot1Effect,
        GainCentsEffect,
        ResetAttackEffect,
    )

    cfg = dict(cfg)
    effect_type = cfg.pop("type")
    active_id = game.state.active_player_id
    if effect_type == "deal_damage":
        return DealDamageEffect(player_id=active_id, **cfg)
    if effect_type == "gain_cents":
        return GainCentsEffect(player_id=active_id, **cfg)
    if effect_type == "draw_loot":
        return DrawLoot1Effect(
            player_id=active_id,
            loot_deck=game.zones.loot_deck,
            log=game.log,
        )
    if effect_type == "reset_attack":
        return ResetAttackEffect()
    raise ValueError(f"Unknown inline effect type: {effect_type!r}")


def _make_roll_branches(branches: dict):
    def event_effect(game: "Game") -> "Effect":
        from foursouls.rulesets.common.effects import LootRollEffect

        resolved = {
            roll_val: _resolve_inline_effect(branch_cfg, game)
            for roll_val, branch_cfg in branches.items()
        }
        return LootRollEffect(branches=resolved, rng=game.rng)

    return event_effect


def _make_reset_attack():
    def event_effect(game: "Game") -> "Effect":  # noqa: ARG001
        from foursouls.rulesets.common.effects import ResetAttackEffect

        return ResetAttackEffect()

    return event_effect


EVENT_EFFECT_REGISTRY = {
    "roll_branches": _make_roll_branches,
    "reset_attack": _make_reset_attack,
}


def build_event_effect(config: dict):
    """Build an event-card effect factory from validated YAML."""
    cfg = dict(config)
    effect_type = cfg.pop("type")
    factory = EVENT_EFFECT_REGISTRY[effect_type]
    return factory(**cfg)
