import pytest

from foursouls.cards.monsters import THE_BLOAT, get_monster_def
from foursouls.engine.condition_evaluator import (
    ConditionEvaluationState,
    ConditionEvaluator,
)
from foursouls.engine.events import (
    CombatRollResult,
    DamageDealt,
    ItemActivated,
    MonsterDied,
    MonsterEnteredActiveSlot,
)
from foursouls.model.abilities import (
    AbilityContext,
    AbilityDefinition,
    AbilityInstance,
    AbilitySource,
)
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId


def _instance(conditions, event_type=CombatRollResult, name="ability"):
    definition = AbilityDefinition.model_validate(
        {
            "ability_id": name,
            "kind": "triggered",
            "trigger": {"type": "event", "event_type": event_type.__name__},
            "conditions": conditions,
            "effects": [{"type": "prevent_event"}],
        }
    )
    source = AbilitySource(
        card_ref=CardRef(InstanceId("source-1"), CardId("TEST")),
        zone="monster_slot",
        zone_entry_id="source-1:entry-2",
    )
    return AbilityInstance(
        instance_id=f"{name}:instance",
        definition=definition,
        source=source,
        controller_id=PlayerId("A"),
    )


def _context(ability, event):
    return AbilityContext(
        ability_instance_id=ability.instance_id,
        source=ability.source,
        controller_id=ability.controller_id,
        triggering_event=event,
    )


@pytest.mark.parametrize(
    "conditions,roll,expected",
    [
        ([{"type": "roll_equals", "value": 4}], 4, True),
        ([{"type": "roll_equals", "value": 4}], 3, False),
        ([{"type": "roll_in", "values": [2, 5]}], 5, True),
        ([{"type": "roll_in", "values": [2, 5]}], 6, False),
    ],
)
def test_roll_conditions_use_typed_combat_events(conditions, roll, expected):
    ability = _instance(conditions)
    event = CombatRollResult(
        attacker_id=PlayerId("A"),
        defender_slot=0,
        roll=roll,
        evade=4,
        is_hit=roll >= 4,
    )

    assert ConditionEvaluator().matches(
        ability,
        _context(ability, event),
    ) is expected


def test_roll_condition_does_not_read_unrelated_event_fields():
    ability = _instance(
        [{"type": "roll_equals", "value": 4}],
        event_type=ItemActivated,
    )
    event = ItemActivated(player_id=PlayerId("A"), source="item:4")

    assert not ConditionEvaluator().matches(ability, _context(ability, event))


@pytest.mark.parametrize("amount,expected", [(0, False), (1, True), (3, True)])
def test_positive_damage_uses_actual_damage(amount, expected):
    ability = _instance(
        [{"type": "positive_damage"}],
        event_type=DamageDealt,
    )
    event = DamageDealt(
        source_player_id=None,
        source_monster_slot=0,
        target_player_id=PlayerId("A"),
        target_monster_slot=None,
        amount=amount,
        reason="combat_miss",
    )

    assert ConditionEvaluator().matches(
        ability,
        _context(ability, event),
    ) is expected


def test_zone_condition_requires_the_current_zone_entry_identity():
    ability = _instance(
        [{"type": "source_in_zone", "zone": "monster_slot"}],
        event_type=ItemActivated,
    )
    context = _context(
        ability,
        ItemActivated(player_id=PlayerId("B"), source="item:test"),
    )
    evaluator = ConditionEvaluator()

    assert evaluator.matches(
        ability,
        context,
        ConditionEvaluationState(
            active_zone_entry_ids=frozenset({"source-1:entry-2"})
        ),
    )
    assert not evaluator.matches(
        ability,
        context,
        ConditionEvaluationState(
            active_zone_entry_ids=frozenset({"source-1:entry-1"})
        ),
    )


def test_bloat_death_matches_only_its_own_card_instance():
    definition = get_monster_def(THE_BLOAT).abilities[1]
    source_ref = CardRef(InstanceId("bloat-1"), THE_BLOAT)
    source = AbilitySource(
        card_ref=source_ref,
        zone="monster_slot",
        zone_entry_id="bloat-1:entry-1",
    )
    ability = AbilityInstance(
        instance_id="bloat-death",
        definition=definition,
        source=source,
        controller_id=PlayerId("A"),
    )
    own_death = MonsterDied(
        attacker_id=PlayerId("A"),
        slot_index=0,
        card_ref=source_ref,
        monster_name="THE_BLOAT",
        had_soul=True,
    )
    other_death = MonsterDied(
        attacker_id=PlayerId("A"),
        slot_index=1,
        card_ref=CardRef(InstanceId("fly-1"), CardId("FLY")),
        monster_name="FLY",
        had_soul=False,
    )
    evaluator = ConditionEvaluator()

    assert evaluator.matches(ability, _context(ability, own_death))
    assert not evaluator.matches(ability, _context(ability, other_death))


def test_entry_source_matching_distinguishes_card_instances():
    ability = _instance(
        [{"type": "event_source_is_ability_source"}],
        event_type=MonsterEnteredActiveSlot,
    )
    matching = MonsterEnteredActiveSlot(
        slot_index=0,
        card_ref=ability.source.card_ref,
    )
    other = MonsterEnteredActiveSlot(
        slot_index=0,
        card_ref=CardRef(InstanceId("source-2"), CardId("TEST")),
    )

    assert ConditionEvaluator().matches(
        ability,
        _context(ability, matching),
    )
    assert not ConditionEvaluator().matches(
        ability,
        _context(ability, other),
    )


def test_context_from_different_instance_is_rejected():
    ability = _instance([{"type": "always"}])
    context = AbilityContext(
        ability_instance_id="other-instance",
        source=ability.source,
        controller_id=ability.controller_id,
        triggering_event=CombatRollResult(
            attacker_id=PlayerId("A"),
            defender_slot=0,
            roll=1,
            evade=4,
            is_hit=False,
        ),
    )

    with pytest.raises(ValueError, match="different instance"):
        ConditionEvaluator().matches(ability, context)
