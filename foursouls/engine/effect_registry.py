from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from foursouls.model.abilities import (
    AbilityContext,
    DealDamageEffect as DealDamageDefinition,
    EffectDefinition,
    GrantDeckAttackEffect as GrantDeckAttackDefinition,
    HealSourceEffect as HealSourceDefinition,
    ModifyEventAmountEffect,
    ModifySourceStatsEffect as ModifySourceStatsDefinition,
    PreventEventEffect,
)
from foursouls.model.effects import Effect
from foursouls.model.target import MonsterTarget, PlayerTarget
from foursouls.rulesets.common.effects import (
    DealDamageEffect,
    GrantDeckAttackEffect,
    HealMonsterEffect,
    ModifyMonsterStatsEffect,
)

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


class EffectBuildError(ValueError):
    pass


EffectBuilder = Callable[[object, AbilityContext, "Game"], Effect]


class EffectRegistry:
    def __init__(self) -> None:
        self._builders: dict[type[object], EffectBuilder] = {}
        self.register(GrantDeckAttackDefinition, self._build_grant_deck_attack)
        self.register(DealDamageDefinition, self._build_deal_damage)
        self.register(HealSourceDefinition, self._build_heal_source)
        self.register(ModifySourceStatsDefinition, self._build_modify_source_stats)
        self.register(ModifyEventAmountEffect, self._replacement_only)
        self.register(PreventEventEffect, self._replacement_only)

    def register(
        self,
        definition_type: type[object],
        builder: EffectBuilder,
        *,
        replace: bool = False,
    ) -> None:
        if definition_type in self._builders and not replace:
            raise ValueError(
                f"builder already registered for {definition_type.__name__}"
            )
        self._builders[definition_type] = builder

    def build(
        self,
        definition: EffectDefinition,
        context: AbilityContext,
        game: "Game",
    ) -> Effect:
        builder = self._builders.get(type(definition))
        if builder is None:
            raise EffectBuildError(
                f"no effect builder for {type(definition).__name__}"
            )
        return builder(definition, context, game)

    def build_sequence(
        self,
        definitions: Iterable[EffectDefinition],
        context: AbilityContext,
        game: "Game",
    ) -> tuple[Effect, ...]:
        return tuple(
            self.build(definition, context, game)
            for definition in definitions
        )

    @staticmethod
    def _build_grant_deck_attack(
        definition: object,
        context: AbilityContext,
        game: "Game",
    ) -> Effect:
        if not isinstance(definition, GrantDeckAttackDefinition):
            raise TypeError("invalid grant-deck-attack definition")
        return GrantDeckAttackEffect(required=definition.required)

    @staticmethod
    def _build_deal_damage(
        definition: object,
        context: AbilityContext,
        game: "Game",
    ) -> Effect:
        if not isinstance(definition, DealDamageDefinition):
            raise TypeError("invalid damage definition")
        target = _single_target(context, PlayerTarget)
        return DealDamageEffect(
            player_id=target.player_id,
            amount=definition.amount,
            damage_type=definition.damage_type,
        )

    @staticmethod
    def _build_heal_source(
        definition: object,
        context: AbilityContext,
        game: "Game",
    ) -> Effect:
        if not isinstance(definition, HealSourceDefinition):
            raise TypeError("invalid heal-source definition")
        target, monster = _source_monster(context, game)
        return HealMonsterEffect(
            monster_slots=game.zones.monster_slots,
            slot_index=target.slot_index,
            monster=monster,
            amount=definition.amount,
        )

    @staticmethod
    def _build_modify_source_stats(
        definition: object,
        context: AbilityContext,
        game: "Game",
    ) -> Effect:
        if not isinstance(definition, ModifySourceStatsDefinition):
            raise TypeError("invalid source-stat definition")
        if definition.duration != "end_of_turn":
            raise EffectBuildError(
                "source stat modifiers currently require end_of_turn duration"
            )
        target, monster = _source_monster(context, game)
        return ModifyMonsterStatsEffect(
            monster_slots=game.zones.monster_slots,
            slot_index=target.slot_index,
            monster=monster,
            attack_delta=definition.attack_delta,
            evade_delta=definition.evade_delta,
        )

    @staticmethod
    def _replacement_only(
        definition: object,
        context: AbilityContext,
        game: "Game",
    ) -> Effect:
        raise EffectBuildError(
            f"{type(definition).__name__} requires the replacement pipeline"
        )


def _single_target(context: AbilityContext, target_type: type[object]):
    if len(context.selected_targets) != 1:
        raise EffectBuildError("effect requires exactly one resolved target")
    target = context.selected_targets[0]
    if not isinstance(target, target_type):
        raise EffectBuildError(
            f"effect requires {target_type.__name__}, got {type(target).__name__}"
        )
    return target


def _source_monster(
    context: AbilityContext,
    game: "Game",
) -> tuple[MonsterTarget, object]:
    if game.zones is None:
        raise EffectBuildError("game zones are not initialized")
    target = _single_target(context, MonsterTarget)
    monster = game.zones.monster_slots.get(target.slot_index)
    if monster is None or monster.card_ref != context.source.card_ref:
        raise EffectBuildError("resolved source monster is no longer in that slot")
    return target, monster
