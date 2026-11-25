from __future__ import annotations

from dataclasses import dataclass

from foursouls.engine.condition_evaluator import (
    ConditionEvaluationState,
    ConditionEvaluator,
)
from foursouls.engine.events import DamageWouldBeDealt
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
        subscriptions = game.event_dispatcher.subscriptions_for(type(event))
        contexts = game.event_dispatcher.dispatch(event)
        state = ConditionEvaluationState(
            active_zone_entry_ids=game.zone_identities.active_zone_entry_ids
        )
        amount = event.amount
        prevented = False
        applied = []

        for subscription, context in zip(
            subscriptions,
            contexts,
            strict=True,
        ):
            ability = subscription.ability
            if ability.definition.kind is not AbilityKind.REPLACEMENT:
                continue
            if not ability.can_use(game.state.turn_number):
                continue
            if not self.condition_evaluator.matches(
                ability,
                context,
                state,
            ):
                continue

            changed = False
            for effect in ability.definition.effects:
                if isinstance(effect, ModifyEventAmountEffect):
                    amount = max(0, amount + effect.delta)
                    changed = True
                elif isinstance(effect, PreventEventEffect):
                    amount = 0
                    prevented = True
                    changed = True
                    break
                else:
                    raise ReplacementPipelineError(
                        f"{type(effect).__name__} is not a replacement effect"
                    )

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
