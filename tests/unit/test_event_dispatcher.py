import pytest

from foursouls.cli.app import build_demo_game
from foursouls.engine.event_dispatcher import EventDispatcher
from foursouls.engine.events import CombatRollResult, ItemActivated
from foursouls.model.abilities import (
    AbilityDefinition,
    AbilityInstance,
    AbilitySource,
)
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId


def _ability(instance_id, event_type, zone_entry_id):
    definition = AbilityDefinition.model_validate(
        {
            "ability_id": f"{instance_id}_definition",
            "kind": "triggered",
            "trigger": {"type": "event", "event_type": event_type.__name__},
            "effects": [{"type": "prevent_event"}],
        }
    )
    source = AbilitySource(
        card_ref=CardRef(InstanceId(instance_id), CardId("TEST_MONSTER")),
        zone="monster_slot",
        zone_entry_id=zone_entry_id,
    )
    return AbilityInstance(
        instance_id=instance_id,
        definition=definition,
        source=source,
        controller_id=PlayerId("A"),
    )


def test_dispatch_is_typed_and_preserves_subscription_order():
    dispatcher = EventDispatcher()
    first = _ability("first", ItemActivated, "entry-1")
    second = _ability("second", ItemActivated, "entry-2")
    ignored = _ability("roll", CombatRollResult, "entry-3")
    dispatcher.subscribe(ItemActivated, first)
    dispatcher.subscribe(ItemActivated, second)
    dispatcher.subscribe(CombatRollResult, ignored)

    event = ItemActivated(player_id=PlayerId("B"), source="item:test")
    contexts = dispatcher.dispatch(event)

    assert [context.ability_instance_id for context in contexts] == [
        "first",
        "second",
    ]
    assert all(context.triggering_event is event for context in contexts)


def test_zone_entry_unsubscribe_removes_only_that_incarnation():
    dispatcher = EventDispatcher()
    old = _ability("old", ItemActivated, "same-card:entry-1")
    current = _ability("current", ItemActivated, "same-card:entry-2")
    dispatcher.subscribe(ItemActivated, old)
    dispatcher.subscribe(ItemActivated, current)

    assert dispatcher.unsubscribe_zone_entry("same-card:entry-1") == 1
    assert dispatcher.unsubscribe_zone_entry("missing") == 0

    contexts = dispatcher.dispatch(
        ItemActivated(player_id=PlayerId("A"), source="item:test")
    )
    assert [context.ability_instance_id for context in contexts] == ["current"]


def test_subscription_rejects_wrong_event_type_and_duplicates():
    dispatcher = EventDispatcher()
    ability = _ability("item-listener", ItemActivated, "entry-1")

    with pytest.raises(ValueError, match="expects ItemActivated"):
        dispatcher.subscribe(CombatRollResult, ability)

    dispatcher.subscribe(ItemActivated, ability)
    with pytest.raises(ValueError, match="already subscribed"):
        dispatcher.subscribe(ItemActivated, ability)


def test_game_emit_records_and_dispatches_event_once():
    game = build_demo_game(["A", "B"], seed=42)
    ability = _ability("game-listener", ItemActivated, "entry-1")
    game.event_dispatcher.subscribe(ItemActivated, ability)
    event = ItemActivated(player_id=PlayerId("B"), source="item:test")

    contexts = game.emit(event)

    assert [context.ability_instance_id for context in contexts] == [
        "game-listener"
    ]
    assert sum(logged is event for logged in game.log.events) == 1
