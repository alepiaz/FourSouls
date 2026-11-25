from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from foursouls.engine.events import Event
from foursouls.model.refs import CardRef, PlayerId
from foursouls.model.target import AnyTarget


class _StrictDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AbilityKind(StrEnum):
    TRIGGERED = "triggered"
    ACTIVATED = "activated"
    STATIC = "static"
    REPLACEMENT = "replacement"


class EventTriggerDefinition(_StrictDefinition):
    type: Literal["event"] = "event"
    event_type: str = Field(min_length=1)


class AlwaysCondition(_StrictDefinition):
    type: Literal["always"] = "always"


class RollEqualsCondition(_StrictDefinition):
    type: Literal["roll_equals"] = "roll_equals"
    value: int = Field(ge=1, le=6)


class RollInCondition(_StrictDefinition):
    type: Literal["roll_in"] = "roll_in"
    values: tuple[int, ...] = Field(min_length=1)


class PositiveDamageCondition(_StrictDefinition):
    type: Literal["positive_damage"] = "positive_damage"


class SourceInZoneCondition(_StrictDefinition):
    type: Literal["source_in_zone"] = "source_in_zone"
    zone: Literal["monster_slot", "item", "character", "loot", "discard"]


class EventSourceIsAbilitySourceCondition(_StrictDefinition):
    type: Literal["event_source_is_ability_source"] = (
        "event_source_is_ability_source"
    )


ConditionDefinition = Annotated[
    Union[
        AlwaysCondition,
        RollEqualsCondition,
        RollInCondition,
        PositiveDamageCondition,
        SourceInZoneCondition,
        EventSourceIsAbilitySourceCondition,
    ],
    Field(discriminator="type"),
]


class SourceSelector(_StrictDefinition):
    type: Literal["source"] = "source"


class ControllerSelector(_StrictDefinition):
    type: Literal["controller"] = "controller"


class ActivePlayerSelector(_StrictDefinition):
    type: Literal["active_player"] = "active_player"


class TriggerTargetSelector(_StrictDefinition):
    type: Literal["trigger_target"] = "trigger_target"


class TriggeringPlayerSelector(_StrictDefinition):
    type: Literal["triggering_player"] = "triggering_player"


class RandomOtherPlayerSelector(_StrictDefinition):
    type: Literal["random_other_player"] = "random_other_player"


TargetSelectorDefinition = Annotated[
    Union[
        SourceSelector,
        ControllerSelector,
        ActivePlayerSelector,
        TriggerTargetSelector,
        TriggeringPlayerSelector,
        RandomOtherPlayerSelector,
    ],
    Field(discriminator="type"),
]


class TapSourceCost(_StrictDefinition):
    type: Literal["tap_source"] = "tap_source"


class PayCentsCost(_StrictDefinition):
    type: Literal["pay_cents"] = "pay_cents"
    amount: int = Field(gt=0)


CostDefinition = Annotated[
    Union[TapSourceCost, PayCentsCost],
    Field(discriminator="type"),
]


class GrantDeckAttackEffect(_StrictDefinition):
    type: Literal["grant_deck_attack"] = "grant_deck_attack"
    required: bool = False


class ModifyEventAmountEffect(_StrictDefinition):
    type: Literal["modify_event_amount"] = "modify_event_amount"
    delta: int


class PreventEventEffect(_StrictDefinition):
    type: Literal["prevent_event"] = "prevent_event"


class HealSourceEffect(_StrictDefinition):
    type: Literal["heal_source"] = "heal_source"
    amount: int = Field(gt=0)


class DealDamageEffect(_StrictDefinition):
    type: Literal["deal_damage"] = "deal_damage"
    amount: int = Field(gt=0)
    damage_type: Literal["combat", "ability"] = "ability"


class DestroySoulEffect(_StrictDefinition):
    type: Literal["destroy_soul"] = "destroy_soul"


class DestroySourceEffect(_StrictDefinition):
    type: Literal["destroy_source"] = "destroy_source"


class ModifySourceStatsEffect(_StrictDefinition):
    type: Literal["modify_source_stats"] = "modify_source_stats"
    attack_delta: int = 0
    evade_delta: int = 0
    duration: Literal["immediate", "end_of_turn", "permanent"] = "immediate"


EffectDefinition = Annotated[
    Union[
        GrantDeckAttackEffect,
        DealDamageEffect,
        ModifyEventAmountEffect,
        PreventEventEffect,
        HealSourceEffect,
        DestroySoulEffect,
        DestroySourceEffect,
        ModifySourceStatsEffect,
    ],
    Field(discriminator="type"),
]


class UsageLimitDefinition(_StrictDefinition):
    max_uses: int = Field(gt=0)
    reset: Literal["each_turn", "never"] = "never"


class AbilityDefinition(_StrictDefinition):
    ability_id: str = Field(min_length=1)
    kind: AbilityKind
    trigger: EventTriggerDefinition | None = None
    conditions: tuple[ConditionDefinition, ...] = ()
    costs: tuple[CostDefinition, ...] = ()
    targets: tuple[TargetSelectorDefinition, ...] = ()
    effects: tuple[EffectDefinition, ...] = Field(min_length=1)
    usage_limit: UsageLimitDefinition | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "AbilityDefinition":
        has_trigger = self.trigger is not None
        if self.kind in {AbilityKind.TRIGGERED, AbilityKind.REPLACEMENT} and not has_trigger:
            raise ValueError(f"{self.kind.value} abilities require a trigger")
        if self.kind in {AbilityKind.ACTIVATED, AbilityKind.STATIC} and has_trigger:
            raise ValueError(f"{self.kind.value} abilities cannot declare a trigger")
        if self.kind is not AbilityKind.ACTIVATED and self.costs:
            raise ValueError("only activated abilities can declare costs")
        return self


@dataclass(frozen=True, slots=True)
class AbilitySource:
    card_ref: CardRef
    zone: str
    zone_entry_id: str


@dataclass(slots=True)
class AbilityInstance:
    instance_id: str
    definition: AbilityDefinition
    source: AbilitySource
    controller_id: PlayerId
    uses: int = 0
    last_used_turn: int | None = None

    def can_use(self, turn_number: int) -> bool:
        limit = self.definition.usage_limit
        if limit is None:
            return True
        if limit.reset == "each_turn" and self.last_used_turn != turn_number:
            return True
        return self.uses < limit.max_uses

    def record_use(self, turn_number: int) -> None:
        if not self.can_use(turn_number):
            raise ValueError("ability usage limit reached")
        limit = self.definition.usage_limit
        if limit is not None and limit.reset == "each_turn" and self.last_used_turn != turn_number:
            self.uses = 0
        self.uses += 1
        self.last_used_turn = turn_number


@dataclass(frozen=True, slots=True)
class AbilityContext:
    ability_instance_id: str
    source: AbilitySource
    controller_id: PlayerId
    triggering_event: Event | None = None
    selected_targets: tuple[AnyTarget, ...] = ()
    usage_count: int = 0
