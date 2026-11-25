"""Regression tests for priority ownership, loot cleanup and demo decks."""
from foursouls.cards.loot import BUTTER_BEAN, LOOT_COIN
from foursouls.cards.treasures import MAMA_MEGA, TREASURE_REGISTRY
from foursouls.cli.app import _loot_deck, _monster_deck, _treasure_deck, build_demo_game
from foursouls.model.commands import (
    ActivateItem, AttackMonster, BuyShop, EndTurn, PassPriority, PlayLoot, RollCombat,
)
from foursouls.model.phase import Phase
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.model.target import StackItemTarget


def _action_game():
    game = build_demo_game(["A", "B"], seed=42)
    while game.state.phase != Phase.ACTION:
        game.step(PassPriority())
    return game


def test_off_turn_actions_belong_to_priority_holder():
    game = _action_game()
    a = game.state.get_player(PlayerId("A"))
    b = game.state.get_player(PlayerId("B"))
    a.hand[:] = [CardRef(InstanceId("a-coin"), LOOT_COIN)]
    b.hand[:] = [CardRef(InstanceId("b-coin"), LOOT_COIN)]
    a.cents = 10
    a.gain_treasure(CardRef(InstanceId("a-item"), MAMA_MEGA))
    b.gain_treasure(CardRef(InstanceId("b-item"), MAMA_MEGA))
    game.state.turn_flags.extra_loot_plays["B"] = 1
    game.step(PassPriority())
    assert game.priority.current() == PlayerId("B")
    commands = game.legal_commands()
    assert not any(isinstance(c, (EndTurn, BuyShop, AttackMonster, RollCombat)) for c in commands)
    assert [c.card_ref for c in commands if isinstance(c, PlayLoot)] == b.hand
    assert not any(isinstance(c, ActivateItem) and c.instance_id == InstanceId("a-item") for c in commands)
    command = ActivateItem(instance_id=InstanceId("b-item"))
    assert command in commands
    game.step(command)
    assert b.items[-1].is_tapped
    assert not a.items[-1].is_tapped
    assert game.stack._items[-1].controller_id == PlayerId("B")


def test_cancelled_loot_is_discarded_once():
    game = _action_game()
    a = game.state.get_player(PlayerId("A"))
    coin = CardRef(InstanceId("cancelled-coin"), LOOT_COIN)
    bean = CardRef(InstanceId("cancelling-bean"), BUTTER_BEAN)
    a.hand[:] = [coin, bean]
    game.state.turn_flags.loot_plays_allowed = 2
    game.step(PlayLoot(card_ref=coin))
    target = StackItemTarget(stack_id=game.stack._items[-1].stack_id)
    game.step(PlayLoot(card_ref=bean, target=target))
    game.step(PassPriority())
    game.step(PassPriority())
    assert game.zones.loot_discard.cards.count(coin) == 1
    assert game.zones.loot_discard.cards.count(bean) == 1
    assert a.cents == 0


def test_demo_decks_are_populated():
    loot, monsters, treasures = _loot_deck(), _monster_deck(), _treasure_deck()
    assert len(loot) == 40
    assert len({c.card_id for c in loot}) == 10
    assert len({c.card_id for c in monsters}) == 15
    assert all(c.card_id in TREASURE_REGISTRY for c in treasures)
    assert all(not TREASURE_REGISTRY[c.card_id].eternal for c in treasures)
    assert len({c.instance_id for c in loot + monsters + treasures}) == len(loot + monsters + treasures)
