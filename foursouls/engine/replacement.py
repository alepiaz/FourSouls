from __future__ import annotations

from dataclasses import dataclass, replace

from foursouls.engine.condition_evaluator import (
    ConditionEvaluationState,
    ConditionEvaluator,
)
from foursouls.engine.events import (
    DamageWouldBeDealt,
    Event,
    MonsterDeathWouldOccur,
)
from foursouls.engine.target_resolver import TargetResolver
from foursouls.model.abilities import (
    AbilityKind,
    ModifyEventAmountEffect,
    PreventEventEffect,
)


class ReplacementPipelineError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DamageReplacementResult:
    original_amount: int
    amount: int
    prevented: bool
    applied_ability_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EventReplacementResult:
    prevented: bool
    applied_ability_ids: tuple[str, ...]


class ReplacementPipeline:
    def __init__(
        self,
        condition_evaluator: ConditionEvaluator | None = None,
    ) -> None:
        self.condition_evaluator = (
            condition_evaluator or ConditionEvaluator()
        )

    def apply_damage(
        self,
        event: DamageWouldBeDealt,
        game,
    ) -> DamageReplacementResult:
        amount = event.amount
        prevented = False
        applied = []

        for ability, context in self._matching(event, game):
            context = self._resolve_targets(ability, context, game)
            changed = False

            for definition in ability.definition.effects:
                if isinstance(definition, ModifyEventAmountEffect):
                    amount = max(0, amount + definition.delta)
                    changed = True
                elif isinstance(definition, PreventEventEffect):
                    amount = 0
                    prevented = True
                    changed = True
                else:
                    effect = game.ability_engine.effect_registry.build(
                        definition,
                        context,
                        game,
                    )
                    if effect.validate(game.state):
                        effect.apply(game.state)
                        changed = True

            if changed:
                ability.record_use(game.state.turn_number)
                applied.append(ability.instance_id)
            if prevented:
                break

        return DamageReplacementResult(
            original_amount=event.amount,
            amount=amount,
            prevented=prevented,
            applied_ability_ids=tuple(applied),
        )

    def apply_monster_death(
        self,
        event: MonsterDeathWouldOccur,
        game,
    ) -> EventReplacementResult:
        prevented = False
        applied = []

        for ability, context in self._matching(event, game):
            context = self._resolve_targets(ability, context, game)
            changed = False

            for definition in ability.definition.effects:
                if isinstance(definition, PreventEventEffect):
                    prevented = True
                    changed = True
                elif isinstance(definition, ModifyEventAmountEffect):
                    raise ReplacementPipelineError(
                        "monster-death replacement cannot modify an amount"
                    )
                else:
                    effect = game.ability_engine.effect_registry.build(
                        definition,
                        context,
                        game,
                    )
                    if effect.validate(game.state):
                        effect.apply(game.state)
                        changed = True

            if changed:
                ability.record_use(game.state.turn_number)
                applied.append(ability.instance_id)
            if prevented:
                break

        return EventReplacementResult(
            prevented=prevented,
            applied_ability_ids=tuple(applied),
        )

    def _matching(self, event: Event, game):
        game.sync_monster_abilities()
        subscriptions = game.event_dispatcher.subscriptions_for(type(event))
        contexts = game.event_dispatcher.dispatch(event)
        state = ConditionEvaluationState(
            active_zone_entry_ids=game.zone_identities.active_zone_entry_ids
        )

        for subscription, context in zip(
            subscriptions,
            contexts,
            strict=True,
        ):
            ability = subscription.ability
            if ability.definition.kind is not AbilityKind.REPLACEMENT:
                continue
            if ability.source.zone == "monster_slot":
                ability.controller_id = game.state.active_player_id
                context = replace(
                    context,
                    controller_id=game.state.active_player_id,
                )
            if not ability.can_use(game.state.turn_number):
                continue
            if self.condition_evaluator.matches(ability, context, state):
                yield ability, context

    @staticmethod
    def _resolve_targets(ability, context, game):
        resolver = TargetResolver(game.zone_identities)
        for selector in ability.definition.targets:
            resolution = resolver.resolve(
                selector,
                ability,
                context,
                game,
            )
            if resolution.requires_choice:
                raise ReplacementPipelineError(
                    "replacement effects cannot pause for a target choice"
                )
            context = replace(
                context,
                selected_targets=(
                    context.selected_targets + resolution.selected
                ),
            )
        return context
