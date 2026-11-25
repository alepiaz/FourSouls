from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar

from foursouls.engine.events import Event
from foursouls.model.abilities import AbilityContext, AbilityInstance


EventT = TypeVar("EventT", bound=Event)


@dataclass(frozen=True, slots=True)
class EventSubscription:
    subscription_id: int
    event_type: type[Event]
    ability: AbilityInstance

    @property
    def zone_entry_id(self) -> str:
        return self.ability.source.zone_entry_id


@dataclass(slots=True)
class EventDispatcher:
    _subscriptions: dict[type[Event], list[EventSubscription]] = field(
        default_factory=dict
    )
    _next_subscription_id: int = 1

    def subscribe(
        self,
        event_type: type[EventT],
        ability: AbilityInstance,
    ) -> EventSubscription:
        if not issubclass(event_type, Event):
            raise TypeError("event_type must be an Event subclass")

        trigger = ability.definition.trigger
        if trigger is None:
            raise ValueError("only abilities with event triggers can subscribe")
        if trigger.event_type != event_type.__name__:
            raise ValueError(
                f"ability expects {trigger.event_type}, not {event_type.__name__}"
            )

        subscriptions = self._subscriptions.setdefault(event_type, [])
        if any(item.ability.instance_id == ability.instance_id for item in subscriptions):
            raise ValueError(
                f"ability instance {ability.instance_id!r} is already subscribed "
                f"to {event_type.__name__}"
            )

        subscription = EventSubscription(
            subscription_id=self._next_subscription_id,
            event_type=event_type,
            ability=ability,
        )
        self._next_subscription_id += 1
        subscriptions.append(subscription)
        return subscription

    def unsubscribe(self, subscription_id: int) -> bool:
        for event_type, subscriptions in tuple(self._subscriptions.items()):
            remaining = [
                item
                for item in subscriptions
                if item.subscription_id != subscription_id
            ]
            if len(remaining) == len(subscriptions):
                continue
            if remaining:
                self._subscriptions[event_type] = remaining
            else:
                del self._subscriptions[event_type]
            return True
        return False

    def unsubscribe_zone_entry(self, zone_entry_id: str) -> int:
        removed = 0
        for event_type, subscriptions in tuple(self._subscriptions.items()):
            remaining = [
                item
                for item in subscriptions
                if item.zone_entry_id != zone_entry_id
            ]
            removed += len(subscriptions) - len(remaining)
            if remaining:
                self._subscriptions[event_type] = remaining
            else:
                del self._subscriptions[event_type]
        return removed

    def dispatch(self, event: Event) -> tuple[AbilityContext, ...]:
        subscriptions = tuple(self._subscriptions.get(type(event), ()))
        return tuple(
            AbilityContext(
                ability_instance_id=item.ability.instance_id,
                source=item.ability.source,
                controller_id=item.ability.controller_id,
                triggering_event=event,
                usage_count=item.ability.uses,
            )
            for item in subscriptions
        )

    def subscriptions_for(
        self,
        event_type: type[EventT],
    ) -> tuple[EventSubscription, ...]:
        return tuple(self._subscriptions.get(event_type, ()))
