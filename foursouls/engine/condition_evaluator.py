from __future__ import annotations

from dataclasses import dataclass

from foursouls.engine.events import (
    CombatRollResult,
    DamageDealt,
    DamageWouldBeDealt,
    MonsterDied,
    MonsterDeathWouldOccur,
    MonsterEnteredActiveSlot,
)
from foursouls.model.abilities import (
    AbilityContext,
    AbilityInstance,
    AlwaysCondition,
    ConditionDefinition,
    EventSourceIsAbilitySourceCondition,
    EventTargetIsAbilitySourceCondition,
    PositiveDamageCondition,
    RollEqualsCondition,
    RollInCondition,
    SourceInZoneCondition,
)


@dataclass(frozen=True, slots=True)
class ConditionEvaluationState:
    active_zone_entry_ids: frozenset[str] = frozenset()


class ConditionEvaluator:
    def matches(
        self,
        ability: AbilityInstance,
        context: AbilityContext,
        state: ConditionEvaluationState = ConditionEvaluationState(),
    ) -> bool:
        if context.ability_instance_id != ability.instance_id:
            raise ValueError("ability context belongs to a different instance")

        event = context.triggering_event
        trigger = ability.definition.trigger
        if event is None or trigger is None:
            return False
        if trigger.event_type != type(event).__name__:
            return False

        return all(
            self.evaluate(condition, context, state)
            for condition in ability.definition.conditions
        )

    def evaluate(
        self,
        condition: ConditionDefinition,
        context: AbilityContext,
        state: ConditionEvaluationState,
    ) -> bool:
        event = context.triggering_event

        if isinstance(condition, AlwaysCondition):
            return True

        if isinstance(condition, RollEqualsCondition):
            return (
                isinstance(
                    event,
                    (CombatRollResult, DamageWouldBeDealt, MonsterDied),
                )
                and (
                    event.kill_roll
                    if isinstance(event, MonsterDied)
                    else event.roll
                )
                == condition.value
            )

        if isinstance(condition, RollInCondition):
            return (
                isinstance(
                    event,
                    (CombatRollResult, DamageWouldBeDealt, MonsterDied),
                )
                and (
                    event.kill_roll
                    if isinstance(event, MonsterDied)
                    else event.roll
                )
                in condition.values
            )

        if isinstance(condition, PositiveDamageCondition):
            return (
                isinstance(event, (DamageDealt, DamageWouldBeDealt))
                and event.amount > 0
            )

        if isinstance(condition, SourceInZoneCondition):
            return (
                context.source.zone == condition.zone
                and context.source.zone_entry_id
                in state.active_zone_entry_ids
            )

        if isinstance(condition, EventSourceIsAbilitySourceCondition):
            if isinstance(
                event,
                (
                    MonsterDied,
                    MonsterDeathWouldOccur,
                    MonsterEnteredActiveSlot,
                ),
            ):
                return event.card_ref == context.source.card_ref
            if isinstance(event, (DamageDealt, DamageWouldBeDealt)):
                return event.source_card_ref == context.source.card_ref
            return False

        if isinstance(condition, EventTargetIsAbilitySourceCondition):
            return (
                isinstance(
                    event,
                    (DamageWouldBeDealt, MonsterDeathWouldOccur),
                )
                and (
                    event.card_ref
                    if isinstance(event, MonsterDeathWouldOccur)
                    else event.target_card_ref
                )
                == context.source.card_ref
            )

        raise TypeError(f"Unsupported condition: {type(condition).__name__}")
