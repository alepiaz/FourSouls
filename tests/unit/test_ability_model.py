from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from foursouls.engine.events import CombatRollResult
from foursouls.model.abilities import (
    AbilityContext,
    AbilityDefinition,
    AbilityInstance,
    AbilitySource,
)
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId


def _bony_definition():
    return AbilityDefinition.model_validate(
        {
            "ability_id": "bony_attack_bonus",
            "kind": "triggered",
            "trigger": {"type": "event", "event_type": "CombatRollResult"},
            "conditions": [
                {"type": "source_in_zone", "zone": "monster_slot"},
                {"type": "roll_equals", "value": 1},
            ],
            "targets": [{"type": "source"}],
            "effects": [
                {
                    "type": "modify_source_stats",
                    "attack_delta": 2,
                    "duration": "end_of_turn",
                }
            ],
        }
    )


def _source(name="bony-1"):
    return AbilitySource(
        card_ref=CardRef(InstanceId(name), CardId("BONY")),
        zone="monster_slot",
        zone_entry_id=f"{name}:entry-1",
    )


def test_composable_triggered_ability_is_validated_and_immutable():
    definition = _bony_definition()

    assert definition.trigger.event_type == "CombatRollResult"
    assert [condition.type for condition in definition.conditions] == [
        "source_in_zone",
        "roll_equals",
    ]
    assert definition.effects[0].attack_delta == 2

    with pytest.raises(ValidationError):
        definition.effects[0].attack_delta = 99


@pytest.mark.parametrize(
    "bad_fragment",
    [
        {"kind": "triggered"},
        {
            "kind": "triggered",
            "trigger": {"type": "event", "event_type": "CombatRollResult"},
            "effects": [{"type": "python", "callable": "os.system"}],
        },
        {
            "kind": "triggered",
            "trigger": {"type": "event", "event_type": "CombatRollResult"},
            "effects": [{"type": "prevent_event", "unexpected": True}],
        },
    ],
)
def test_invalid_or_executable_ability_shapes_are_rejected(bad_fragment):
    payload = {
        "ability_id": "invalid",
        "effects": [{"type": "prevent_event"}],
        **bad_fragment,
    }

    with pytest.raises(ValidationError):
        AbilityDefinition.model_validate(payload)


def test_non_activated_ability_cannot_declare_costs():
    with pytest.raises(ValidationError, match="only activated abilities"):
        AbilityDefinition.model_validate(
            {
                "ability_id": "invalid_paid_trigger",
                "kind": "triggered",
                "trigger": {"type": "event", "event_type": "MonsterDied"},
                "costs": [{"type": "pay_cents", "amount": 1}],
                "effects": [{"type": "grant_deck_attack"}],
            }
        )


def test_per_instance_usage_is_independent_and_resets_each_turn():
    definition = AbilityDefinition.model_validate(
        {
            "ability_id": "once_each_turn",
            "kind": "replacement",
            "trigger": {"type": "event", "event_type": "MonsterWouldDie"},
            "effects": [{"type": "prevent_event"}],
            "usage_limit": {"max_uses": 1, "reset": "each_turn"},
        }
    )
    first = AbilityInstance("ability-1", definition, _source("one"), PlayerId("A"))
    second = AbilityInstance("ability-2", definition, _source("two"), PlayerId("A"))

    first.record_use(turn_number=3)

    assert not first.can_use(turn_number=3)
    assert second.can_use(turn_number=3)
    assert first.can_use(turn_number=4)

    first.record_use(turn_number=4)
    assert first.uses == 1
    assert first.last_used_turn == 4


def test_runtime_context_captures_source_event_and_targets():
    source = _source()
    event = CombatRollResult(
        attacker_id=PlayerId("A"),
        defender_slot=0,
        roll=1,
        evade=3,
        is_hit=False,
    )
    context = AbilityContext(
        ability_instance_id="ability-1",
        source=source,
        controller_id=PlayerId("A"),
        triggering_event=event,
        usage_count=0,
    )

    assert context.source.zone_entry_id == "bony-1:entry-1"
    assert context.triggering_event is event

    with pytest.raises(FrozenInstanceError):
        context.usage_count = 1
