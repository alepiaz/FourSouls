from __future__ import annotations

from collections.abc import Iterable

from foursouls.model.abilities import (
    AbilityInstance,
    CostDefinition,
    PayCentsCost,
    TapSourceCost,
)


class CostPaymentError(ValueError):
    pass


class CostEngine:
    def can_pay_all(
        self,
        ability: AbilityInstance,
        costs: Iterable[CostDefinition],
        game,
    ) -> bool:
        costs = tuple(costs)
        player = game.state.get_player(ability.controller_id)
        cents_required = sum(
            cost.amount
            for cost in costs
            if isinstance(cost, PayCentsCost)
        )
        if player.cents < cents_required:
            return False

        tap_costs = [
            cost for cost in costs if isinstance(cost, TapSourceCost)
        ]
        if len(tap_costs) > 1:
            return False
        if tap_costs:
            source = _source_item(ability, game)
            if source is None or source.is_tapped:
                return False

        return all(
            isinstance(cost, (PayCentsCost, TapSourceCost))
            for cost in costs
        )

    def pay_all(
        self,
        ability: AbilityInstance,
        costs: Iterable[CostDefinition],
        game,
    ) -> None:
        costs = tuple(costs)
        if not self.can_pay_all(ability, costs, game):
            raise CostPaymentError("ability costs cannot be paid")

        player = game.state.get_player(ability.controller_id)
        player.cents -= sum(
            cost.amount
            for cost in costs
            if isinstance(cost, PayCentsCost)
        )
        if any(isinstance(cost, TapSourceCost) for cost in costs):
            source = _source_item(ability, game)
            if source is None:
                raise CostPaymentError("tap source disappeared during payment")
            source.tap()


class AbilityActivationManager:
    def __init__(self, cost_engine: CostEngine | None = None) -> None:
        self.cost_engine = cost_engine or CostEngine()

    def can_activate(self, ability: AbilityInstance, game) -> bool:
        return (
            ability.can_use(game.state.turn_number)
            and self.cost_engine.can_pay_all(
                ability,
                ability.definition.costs,
                game,
            )
        )

    def commit(self, ability: AbilityInstance, game) -> None:
        if not self.can_activate(ability, game):
            raise CostPaymentError(
                "ability usage limit or cost prevents activation"
            )
        self.cost_engine.pay_all(
            ability,
            ability.definition.costs,
            game,
        )
        ability.record_use(game.state.turn_number)


def _source_item(ability: AbilityInstance, game):
    player = game.state.get_player(ability.controller_id)
    candidates = []
    if player.character is not None:
        candidates.append(player.character)
    candidates.extend(player.items)
    return next(
        (
            item
            for item in candidates
            if item.card_ref == ability.source.card_ref
        ),
        None,
    )
