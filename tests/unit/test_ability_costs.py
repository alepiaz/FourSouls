import pytest

from foursouls.cli.app import build_demo_game
from foursouls.engine.cost_engine import (
    AbilityActivationManager,
    CostEngine,
    CostPaymentError,
)
from foursouls.model.abilities import (
    AbilityDefinition,
    AbilityInstance,
    AbilitySource,
)
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId


def _activated_ability(game, *, cents=2, max_uses=1):
    card_ref = CardRef(InstanceId("paid-item"), CardId("PAID_ITEM"))
    player = game.state.get_player(PlayerId("A"))
    player.gain_treasure(card_ref)
    definition = AbilityDefinition.model_validate(
        {
            "ability_id": "paid_tap",
            "kind": "activated",
            "costs": [
                {"type": "pay_cents", "amount": cents},
                {"type": "tap_source"},
            ],
            "effects": [{"type": "grant_deck_attack"}],
            "usage_limit": {
                "max_uses": max_uses,
                "reset": "each_turn",
            },
        }
    )
    ability = AbilityInstance(
        instance_id="paid_tap:instance",
        definition=definition,
        source=AbilitySource(
            card_ref=card_ref,
            zone="item",
            zone_entry_id="paid-item:item:1",
        ),
        controller_id=PlayerId("A"),
    )
    return ability, player, player.items[-1]


def test_activation_pays_all_costs_and_records_usage_once():
    game = build_demo_game(["A", "B"], seed=42)
    ability, player, item = _activated_ability(game, cents=2)
    player.cents = 5
    manager = AbilityActivationManager()

    assert manager.can_activate(ability, game)
    manager.commit(ability, game)

    assert player.cents == 3
    assert item.is_tapped
    assert ability.uses == 1
    assert ability.last_used_turn == game.state.turn_number
    assert not manager.can_activate(ability, game)


def test_failed_payment_is_atomic():
    game = build_demo_game(["A", "B"], seed=42)
    ability, player, item = _activated_ability(game, cents=4)
    player.cents = 3

    with pytest.raises(CostPaymentError):
        AbilityActivationManager().commit(ability, game)

    assert player.cents == 3
    assert not item.is_tapped
    assert ability.uses == 0


def test_multiple_coin_costs_are_checked_as_a_total():
    game = build_demo_game(["A", "B"], seed=42)
    card_ref = CardRef(InstanceId("coin-item"), CardId("COIN_ITEM"))
    player = game.state.get_player(PlayerId("A"))
    player.cents = 4
    definition = AbilityDefinition.model_validate(
        {
            "ability_id": "double_payment",
            "kind": "activated",
            "costs": [
                {"type": "pay_cents", "amount": 3},
                {"type": "pay_cents", "amount": 2},
            ],
            "effects": [{"type": "grant_deck_attack"}],
        }
    )
    ability = AbilityInstance(
        instance_id="double-payment",
        definition=definition,
        source=AbilitySource(card_ref, "item", "coin-item:item:1"),
        controller_id=PlayerId("A"),
    )

    assert not CostEngine().can_pay_all(
        ability,
        definition.costs,
        game,
    )
    assert player.cents == 4


def test_each_turn_usage_resets_but_costs_still_apply():
    game = build_demo_game(["A", "B"], seed=42)
    ability, player, item = _activated_ability(game, cents=1)
    player.cents = 3
    manager = AbilityActivationManager()
    manager.commit(ability, game)

    game.state.turn_number += 1
    item.untap()

    assert manager.can_activate(ability, game)
    manager.commit(ability, game)
    assert player.cents == 1
    assert ability.uses == 1
    assert ability.last_used_turn == game.state.turn_number
