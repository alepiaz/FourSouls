from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game
    from foursouls.model.effects import Effect


# ── Trigger handler factories ─────────────────────────────────────────────────
#
# Each factory accepts YAML parameters and returns a callable whose signature
# matches one of the MonsterDef trigger hooks:
#   on_death(game, roll) -> None
#   on_miss(game, roll) -> int
#   on_would_take_combat_damage(game, roll, amount) -> int
#   on_would_die(game) -> bool


def _make_forced_extra_attack(roll_condition=None):
    def on_death(game: "Game", roll: int) -> None:
        if roll_condition is None or roll == roll_condition:
            from foursouls.rulesets.common.effects import ResetAttackEffect
            game.push_to_stack(
                controller_id=game.state.active_player_id,
                source="monster:forced_extra_attack",
                effect=ResetAttackEffect(),
                label="ForcedExtraAttack",
            )
    return on_death


def _make_optional_extra_attack():
    def on_death(game: "Game", roll: int) -> None:  # noqa: ARG001
        from foursouls.rulesets.common.effects import ResetAttackEffect
        game.push_to_stack(
            controller_id=game.state.active_player_id,
            source="monster:optional_extra_attack",
            effect=ResetAttackEffect(),
            label="MayAttackAgain",
        )
    return on_death


def _make_extra_miss_damage(roll_condition, amount):
    def on_miss(game: "Game", roll: int) -> int:
        monster = game.zones.monster_slots.get(game.combat.defender_slot)
        base = monster.attack + monster.attack_bonus
        return base + amount if roll == roll_condition else base
    return on_miss


def _make_shield_on_rolls(rolls):
    rolls_set = frozenset(rolls)

    def on_would_take_combat_damage(game: "Game", roll: int, amount: int) -> int:  # noqa: ARG001
        return 0 if roll in rolls_set else amount

    return on_would_take_combat_damage


def _make_death_prevention_with_heal(heal, evade_delta=0, attack_delta=0):
    def on_would_die(game: "Game") -> bool:
        defender = game.zones.monster_slots.get(game.combat.defender_slot)
        if defender is None:
            return False
        defender.current_hp = min(defender.base_hp, defender.current_hp + heal)
        defender.evade_bonus += evade_delta
        defender.attack_bonus += attack_delta
        return True
    return on_would_die


TRIGGER_REGISTRY = {
    "forced_extra_attack":        _make_forced_extra_attack,
    "optional_extra_attack":      _make_optional_extra_attack,
    "extra_miss_damage":          _make_extra_miss_damage,
    "shield_on_rolls":            _make_shield_on_rolls,
    "death_prevention_with_heal": _make_death_prevention_with_heal,
}


# ── Event effect factories ────────────────────────────────────────────────────
#
# Each factory accepts YAML parameters and returns a callable (game) -> Effect.


def _make_gain_cents(amount):
    def event_effect(game: "Game") -> "Effect":
        from foursouls.rulesets.common.effects import GainCentsEffect
        return GainCentsEffect(player_id=game.state.active_player_id, amount=amount)
    return event_effect


def _make_deal_damage(amount):
    def event_effect(game: "Game") -> "Effect":
        from foursouls.rulesets.common.effects import DealDamageEffect
        return DealDamageEffect(player_id=game.state.active_player_id, amount=amount)
    return event_effect


def _make_draw_loot():
    def event_effect(game: "Game") -> "Effect":
        from foursouls.rulesets.common.effects import DrawLoot1Effect
        return DrawLoot1Effect(
            player_id=game.state.active_player_id,
            loot_deck=game.zones.loot_deck,
            log=game.log,
        )
    return event_effect


def _resolve_inline_effect(cfg: dict, game: "Game") -> "Effect":
    """Resolve a nested effect config dict at call time (game context available)."""
    from foursouls.rulesets.common.effects import (
        DealDamageEffect, GainCentsEffect, DrawLoot1Effect, ResetAttackEffect,
    )
    cfg = dict(cfg)
    effect_type = cfg.pop("type")
    active_id = game.state.active_player_id
    if effect_type == "deal_damage":
        return DealDamageEffect(player_id=active_id, **cfg)
    if effect_type == "gain_cents":
        return GainCentsEffect(player_id=active_id, **cfg)
    if effect_type == "draw_loot":
        return DrawLoot1Effect(player_id=active_id, loot_deck=game.zones.loot_deck, log=game.log)
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
    "gain_cents":    _make_gain_cents,
    "deal_damage":   _make_deal_damage,
    "draw_loot":     _make_draw_loot,
    "roll_branches": _make_roll_branches,
    "reset_attack":  _make_reset_attack,
}


# ── Public builders ───────────────────────────────────────────────────────────

def build_trigger(config: dict):
    """Build a trigger callback from a validated YAML config dict."""
    cfg = dict(config)
    ability_type = cfg.pop("type")
    factory = TRIGGER_REGISTRY[ability_type]
    return factory(**cfg)


def build_event_effect(config: dict):
    """Build an event_effect factory from a validated YAML config dict."""
    cfg = dict(config)
    effect_type = cfg.pop("type")
    factory = EVENT_EFFECT_REGISTRY[effect_type]
    return factory(**cfg)
