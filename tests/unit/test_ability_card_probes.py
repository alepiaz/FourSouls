import pytest
import yaml
from pydantic import ValidationError

from foursouls.model.abilities import AbilityDefinition


def _round_trip(definition):
    serialized = yaml.safe_dump(definition.model_dump(mode="json"))
    return AbilityDefinition.model_validate(yaml.safe_load(serialized))


def test_the_bloat_composes_zone_entry_and_death_triggers():
    shared_resolution = {
        "conditions": [{"type": "source_in_zone", "zone": "monster_slot"}],
        "targets": [{"type": "random_other_player"}],
        "effects": [{"type": "deal_damage", "amount": 2}],
    }
    definitions = [
        AbilityDefinition.model_validate(
            {
                "ability_id": "the_bloat_entered_slot",
                "kind": "triggered",
                "trigger": {
                    "type": "event",
                    "event_type": "MonsterEnteredActiveSlot",
                },
                **shared_resolution,
            }
        ),
        AbilityDefinition.model_validate(
            {
                "ability_id": "the_bloat_died",
                "kind": "triggered",
                "trigger": {"type": "event", "event_type": "MonsterDied"},
                **shared_resolution,
            }
        ),
    ]

    restored = [_round_trip(definition) for definition in definitions]

    assert [definition.trigger.event_type for definition in restored] == [
        "MonsterEnteredActiveSlot",
        "MonsterDied",
    ]
    assert all(definition.targets[0].type == "random_other_player" for definition in restored)
    assert all(definition.effects[0].amount == 2 for definition in restored)


def test_cursed_psy_horf_composes_existing_item_event_and_damage():
    definition = AbilityDefinition.model_validate(
        {
            "ability_id": "cursed_psy_horf_item_damage",
            "kind": "triggered",
            "trigger": {"type": "event", "event_type": "ItemActivated"},
            "conditions": [
                {"type": "source_in_zone", "zone": "monster_slot"},
            ],
            "targets": [{"type": "triggering_player"}],
            "effects": [{"type": "deal_damage", "amount": 1}],
        }
    )

    restored = _round_trip(definition)

    assert restored.trigger.event_type == "ItemActivated"
    assert restored.targets[0].type == "triggering_player"
    assert restored.effects[0].type == "deal_damage"
    assert restored.effects[0].amount == 1


@pytest.mark.parametrize(
    ("card_id", "unsupported_fragment"),
    [
        (
            "wizoob_destroy_chosen_soul",
            {
                "targets": [{"type": "active_player_chooses_player"}],
                "effects": [{"type": "destroy_soul"}],
            },
        ),
        (
            "cursed_gaper_global_roll_aura",
            {
                "targets": [{"type": "all_monsters"}],
                "effects": [
                    {
                        "type": "modify_target_stats",
                        "attack_delta": 1,
                        "duration": "end_of_turn",
                    }
                ],
            },
        ),
        (
            "deaths_head_static_aura",
            {
                "targets": [{"type": "all_other_monsters"}],
                "effects": [
                    {
                        "type": "continuous_stat_modifier",
                        "attack_delta": 1,
                    }
                ],
            },
        ),
    ],
)
def test_future_roadmap_mechanics_fail_closed(card_id, unsupported_fragment):
    payload = {
        "ability_id": card_id,
        "kind": "triggered",
        "trigger": {"type": "event", "event_type": "PlaceholderEvent"},
        **unsupported_fragment,
    }

    with pytest.raises(ValidationError):
        AbilityDefinition.model_validate(payload)
