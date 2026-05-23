from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game
    from foursouls.model.effects import Effect
    from foursouls.model.target import AnyTarget


# ── Tap effect factories ──────────────────────────────────────────────────────
# Each factory returns: make_tap_effect(target, game) -> Effect


def _make_aoe_damage(amount):
    def make_tap_effect(target: "AnyTarget", game: "Game") -> "Effect":
        from foursouls.rulesets.common.effects import AoDamageEffect
        return AoDamageEffect(amount=amount, monster_slots=game.zones.monster_slots)
    return make_tap_effect


def _make_prevent_damage_to_target(amount):
    def make_tap_effect(target: "AnyTarget", game: "Game") -> "Effect":
        from foursouls.model.target import PlayerTarget
        from foursouls.rulesets.common.effects import PreventDamageEffect, PreventDamageToMonsterEffect
        if isinstance(target, PlayerTarget):
            return PreventDamageEffect(player_id=target.player_id, amount=amount)
        return PreventDamageToMonsterEffect(
            slot_index=target.slot_index, amount=amount,
            monster_slots=game.zones.monster_slots,
        )
    return make_tap_effect


TAP_EFFECT_REGISTRY = {
    "aoe_damage":               _make_aoe_damage,
    "prevent_damage_to_target": _make_prevent_damage_to_target,
}


# ── Lifecycle hook factories ──────────────────────────────────────────────────
# on_enters_play(game, player_id) -> None


def _make_set_damage_cap(amount):
    def on_enters_play(game: "Game", player_id: object) -> None:
        game.state.get_player(player_id).damage_cap = amount  # type: ignore[arg-type]
    return on_enters_play


def _make_increase_attack_bonus(amount):
    def on_enters_play(game: "Game", player_id: object) -> None:
        game.state.get_player(player_id).attack_bonus += amount  # type: ignore[arg-type]
    return on_enters_play


LIFECYCLE_REGISTRY = {
    "set_damage_cap":        _make_set_damage_cap,
    "increase_attack_bonus": _make_increase_attack_bonus,
}


# ── Public builders ───────────────────────────────────────────────────────────

def build_tap_effect(config: dict):
    """Build a tap-effect factory from a validated YAML config dict."""
    cfg = dict(config)
    effect_type = cfg.pop("type")
    return TAP_EFFECT_REGISTRY[effect_type](**cfg)


def build_lifecycle_hook(hook_name: str, config: dict):
    """Build a lifecycle hook callable from a validated YAML config dict."""
    cfg = dict(config)
    hook_type = cfg.pop("type")
    return LIFECYCLE_REGISTRY[hook_type](**cfg)
