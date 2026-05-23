from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from foursouls.model.effects import Effect


# ── Loot effect factories ─────────────────────────────────────────────────────
#
# Each factory accepts YAML parameters and returns a callable:
#   make_effect(controller_id, *, target, monster_slots, rng, loot_deck, log, stack) -> Effect
#
# Unused kwargs are absorbed with **_ so callers can always pass the full
# context bag without knowing which keys each card needs.


def _make_gain_cents(amount):
    def make_effect(controller_id, *, target=None, **_) -> "Effect":
        from foursouls.rulesets.common.effects import GainCentsEffect
        return GainCentsEffect(player_id=controller_id, amount=amount)
    return make_effect


def _make_deal_damage_to_target(amount):
    def make_effect(controller_id, *, target, monster_slots=None, **_) -> "Effect":
        from foursouls.model.target import PlayerTarget
        from foursouls.rulesets.common.effects import DealDamageEffect, DealDamageToMonsterEffect
        if isinstance(target, PlayerTarget):
            return DealDamageEffect(player_id=target.player_id, amount=amount, damage_type="ability")
        return DealDamageToMonsterEffect(slot_index=target.slot_index, amount=amount, monster_slots=monster_slots)
    return make_effect


def _make_prevent_damage_to_target(amount):
    def make_effect(controller_id, *, target, monster_slots=None, **_) -> "Effect":
        from foursouls.model.target import PlayerTarget
        from foursouls.rulesets.common.effects import PreventDamageEffect, PreventDamageToMonsterEffect
        if isinstance(target, PlayerTarget):
            return PreventDamageEffect(player_id=target.player_id, amount=amount)
        return PreventDamageToMonsterEffect(slot_index=target.slot_index, amount=amount, monster_slots=monster_slots)
    return make_effect


def _make_cancel_stack_item():
    def make_effect(controller_id, *, target, stack, log=None, **_) -> "Effect":
        from foursouls.rulesets.common.effects import CancelStackItemEffect
        return CancelStackItemEffect(target_stack_id=target.stack_id, stack=stack, log=log)
    return make_effect


def _resolve_inline_loot_effect(cfg: dict, *, loot_deck=None, log=None, **_) -> "Effect":
    cfg = dict(cfg)
    effect_type = cfg.pop("type")
    from foursouls.rulesets.common.effects import (
        AllPlayersGainCentsEffect, AllPlayersDrawLootEffect, AllPlayersTakeDamageEffect,
    )
    if effect_type == "all_gain_cents":
        return AllPlayersGainCentsEffect(**cfg)
    if effect_type == "all_draw_loot":
        return AllPlayersDrawLootEffect(loot_deck=loot_deck, log=log, **cfg)
    if effect_type == "all_take_damage":
        return AllPlayersTakeDamageEffect(**cfg)
    raise ValueError(f"Unknown inline loot effect type: {effect_type!r}")


def _make_roll_branches(branches: dict):
    def make_effect(controller_id, *, rng, loot_deck=None, log=None, **_) -> "Effect":
        from foursouls.rulesets.common.effects import LootRollEffect
        resolved = {
            roll_val: _resolve_inline_loot_effect(branch_cfg, loot_deck=loot_deck, log=log)
            for roll_val, branch_cfg in branches.items()
        }
        return LootRollEffect(branches=resolved, rng=rng)
    return make_effect


LOOT_EFFECT_REGISTRY = {
    "gain_cents":               _make_gain_cents,
    "deal_damage_to_target":    _make_deal_damage_to_target,
    "prevent_damage_to_target": _make_prevent_damage_to_target,
    "cancel_stack_item":        _make_cancel_stack_item,
    "roll_branches":            _make_roll_branches,
}


def build_loot_effect(config: dict):
    """Build a loot effect factory from a validated YAML config dict."""
    cfg = dict(config)
    effect_type = cfg.pop("type")
    factory = LOOT_EFFECT_REGISTRY[effect_type]
    return factory(**cfg)
