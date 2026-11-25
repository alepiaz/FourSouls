from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from foursouls.engine.condition_evaluator import (
    ConditionEvaluationState,
    ConditionEvaluator,
)
from foursouls.engine.effect_registry import EffectRegistry
from foursouls.engine.events import Event
from foursouls.engine.target_resolver import (
    TargetResolution,
    TargetResolutionError,
    TargetResolver,
)
from foursouls.model.abilities import AbilityContext, AbilityInstance
from foursouls.model.refs import PlayerId
from foursouls.model.target import AnyTarget

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


@dataclass(slots=True)
class PendingTrigger:
    pending_id: int
    ability: AbilityInstance
    context: AbilityContext
    next_selector_index: int = 0
    choice: TargetResolution | None = None


@dataclass(slots=True)
class TriggerQueue:
    _items: deque[PendingTrigger] = field(default_factory=deque)
    _next_pending_id: int = 1

    def enqueue(
        self,
        ability: AbilityInstance,
        context: AbilityContext,
    ) -> PendingTrigger:
        pending = PendingTrigger(
            pending_id=self._next_pending_id,
            ability=ability,
            context=context,
        )
        self._next_pending_id += 1
        self._items.append(pending)
        return pending

    def peek(self) -> PendingTrigger | None:
        return self._items[0] if self._items else None

    def pop(self) -> PendingTrigger:
        if not self._items:
            raise IndexError("trigger queue is empty")
        return self._items.popleft()

    def find(self, pending_id: int) -> PendingTrigger | None:
        return next(
            (item for item in self._items if item.pending_id == pending_id),
            None,
        )

    def __len__(self) -> int:
        return len(self._items)


@dataclass(slots=True)
class AbilityEngine:
    condition_evaluator: ConditionEvaluator = field(
        default_factory=ConditionEvaluator
    )
    effect_registry: EffectRegistry = field(default_factory=EffectRegistry)
    trigger_queue: TriggerQueue = field(default_factory=TriggerQueue)

    def observe(
        self,
        event: Event,
        game: "Game",
    ) -> tuple[AbilityContext, ...]:
        subscriptions = game.event_dispatcher.subscriptions_for(type(event))
        contexts = game.event_dispatcher.dispatch(event)
        enqueued = []

        condition_state = ConditionEvaluationState(
            active_zone_entry_ids=game.zone_identities.active_zone_entry_ids
        )
        resolver = TargetResolver(game.zone_identities)

        for subscription, context in zip(
            subscriptions,
            contexts,
            strict=True,
        ):
            ability = subscription.ability
            if not ability.can_use(game.state.turn_number):
                continue
            if not self.condition_evaluator.matches(
                ability,
                context,
                condition_state,
            ):
                continue

            pending = self.trigger_queue.enqueue(ability, context)
            self._advance_targets(pending, resolver, game)
            enqueued.append(pending.context)

        return tuple(enqueued)

    def choose_target(
        self,
        pending_id: int,
        target: AnyTarget,
        chooser_id: PlayerId,
        game: "Game",
    ) -> PendingTrigger:
        pending = self.trigger_queue.find(pending_id)
        if pending is None:
            raise TargetResolutionError("pending trigger does not exist")
        choice = pending.choice
        if choice is None:
            raise TargetResolutionError("pending trigger does not need a choice")
        if choice.chooser_id != chooser_id:
            raise TargetResolutionError("wrong player attempted target choice")
        if target not in choice.candidates:
            raise TargetResolutionError("target is not an available candidate")

        pending.context = replace(
            pending.context,
            selected_targets=pending.context.selected_targets + (target,),
        )
        pending.next_selector_index += 1
        pending.choice = None
        self._advance_targets(
            pending,
            TargetResolver(game.zone_identities),
            game,
        )
        return pending

    def resolve_next(self, game: "Game") -> PendingTrigger | None:
        pending = self.trigger_queue.peek()
        if pending is None:
            return None
        if pending.choice is not None:
            raise TargetResolutionError("pending trigger still needs a target")
        if not pending.ability.can_use(game.state.turn_number):
            self.trigger_queue.pop()
            return None

        effects = self.effect_registry.build_sequence(
            pending.ability.definition.effects,
            pending.context,
            game,
        )
        self.trigger_queue.pop()
        pending.ability.record_use(game.state.turn_number)

        for index, effect in reversed(tuple(enumerate(effects))):
            game.push_to_stack(
                controller_id=pending.ability.controller_id,
                source=pending.ability.source.card_ref,
                effect=effect,
                label=(
                    f"Ability:{pending.ability.definition.ability_id}:{index}"
                ),
            )
        return pending

    @staticmethod
    def _advance_targets(
        pending: PendingTrigger,
        resolver: TargetResolver,
        game: "Game",
    ) -> None:
        selectors = pending.ability.definition.targets
        while pending.next_selector_index < len(selectors):
            selector = selectors[pending.next_selector_index]
            resolution = resolver.resolve(
                selector,
                pending.ability,
                pending.context,
                game,
            )
            if resolution.requires_choice:
                pending.choice = resolution
                return
            pending.context = replace(
                pending.context,
                selected_targets=(
                    pending.context.selected_targets + resolution.selected
                ),
            )
            pending.next_selector_index += 1
