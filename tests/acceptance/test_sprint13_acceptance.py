"""Sprint 13 behavior expressed through the Sprint 13.5 ability runtime."""
from __future__ import annotations

import pytest

from foursouls.cards.monsters import (
    BIG_SPIDER,
    BONY,
    CARRION_QUEEN,
    GAPER,
    HEADLESS_HORSEMAN,
    HORF,
    MEGA_FATTY,
    _DEFAULT,
    get_monster_def,
    make_monster_in_play,
)
from foursouls.cli.app import build_demo_game
from foursouls.engine.events import CombatRollResult
from foursouls.model.abilities import AbilityKind
from foursouls.model.combat_state import CombatState
from foursouls.model.commands import PassPriority
from foursouls.model.phase import Phase
from foursouls.model.refs import CardRef, InstanceId, PlayerId


EXPECTED_ABILITIES = (
    (GAPER, "gaper_forced_attack", AbilityKind.TRIGGERED, "MonsterDied"),
    (
        HORF,
        "horf_extra_miss_damage",
        AbilityKind.REPLACEMENT,
        "DamageWouldBeDealt",
    ),
    (
        BIG_SPIDER,
        "big_spider_optional_attack",
        AbilityKind.TRIGGERED,
        "MonsterDied",
    ),
    (
        CARRION_QUEEN,
        "carrion_queen_prevent_combat_damage",
        AbilityKind.REPLACEMENT,
        "DamageWouldBeDealt",
    ),
    (
        HEADLESS_HORSEMAN,
        "headless_horseman_prevent_death",
        AbilityKind.REPLACEMENT,
        "MonsterDeathWouldOccur",
    ),
    (BONY, "bony_attack_bonus", AbilityKind.TRIGGERED, "CombatRollResult"),
    (MEGA_FATTY, "mega_fatty_heal", AbilityKind.TRIGGERED, "DamageDealt"),
)


@pytest.mark.parametrize(
    "card_id,ability_id,kind,event_type",
    EXPECTED_ABILITIES,
)
def test_sprint13_cards_use_declarative_abilities(
    card_id,
    ability_id,
    kind,
    event_type,
):
    definition = get_monster_def(card_id)
    assert len(definition.abilities) == 1
    ability = definition.abilities[0]
    assert ability.ability_id == ability_id
    assert ability.kind is kind
    assert ability.trigger is not None
    assert ability.trigger.event_type == event_type


def test_legacy_callback_api_is_removed():
    definition = get_monster_def(GAPER)
    monster = make_monster_in_play(CardRef(InstanceId("gaper"), GAPER))

    for name in (
        "on_death",
        "on_miss",
        "on_would_take_combat_damage",
        "on_would_die",
        "on_attack_roll",
        "on_combat_damage_dealt",
    ):
        assert not hasattr(definition, name)
        assert not hasattr(monster, name)


def test_default_monster_has_no_abilities():
    assert _DEFAULT.abilities == ()


def test_monster_runtime_keeps_only_shared_transient_state():
    monster = make_monster_in_play(CardRef(InstanceId("horseman"), HEADLESS_HORSEMAN))
    assert monster.zone_entry_id is None
    assert monster.evade_bonus == 0
    assert monster.attack_bonus == 0


def test_combat_state_still_captures_last_roll():
    combat = CombatState(
        attacker_id=PlayerId("P1"),
        defender_slot=0,
        monster_ref=CardRef(InstanceId("monster")),
    )
    assert combat.last_combat_roll == 0
    combat.last_combat_roll = 4
    assert combat.last_combat_roll == 4


def test_headless_horseman_usage_is_per_turn():
    ability = get_monster_def(HEADLESS_HORSEMAN).abilities[0]
    assert ability.usage_limit is not None
    assert ability.usage_limit.max_uses == 1
    assert ability.usage_limit.reset == "each_turn"


def test_gaper_roll_condition_is_data():
    ability = get_monster_def(GAPER).abilities[0]
    assert [condition.type for condition in ability.conditions] == [
        "event_source_is_ability_source",
        "roll_equals",
    ]
    assert ability.conditions[1].value == 6


def test_bony_listener_is_registered_for_direct_slot_insertion():
    game = build_demo_game(seed=42)
    while game.state.phase != Phase.ACTION or not game.stack.empty():
        game.step(PassPriority())

    bony = make_monster_in_play(CardRef(InstanceId("direct-bony"), BONY))
    game.zones.monster_slots.set(0, bony)

    game.emit(
        CombatRollResult(
            attacker_id=game.state.active_player_id,
            defender_slot=1,
            roll=1,
            evade=3,
            is_hit=False,
        )
    )

    assert bony.zone_entry_id is not None
    assert len(game.ability_engine.trigger_queue) == 1
    assert game.activate_next_trigger()
    assert game.stack.top().label == "Ability:bony_attack_bonus:0"


def test_declarative_effects_preserve_printed_intent():
    expected = {
        GAPER: ("grant_deck_attack",),
        HORF: ("modify_event_amount",),
        BIG_SPIDER: ("grant_deck_attack",),
        CARRION_QUEEN: ("prevent_event",),
        HEADLESS_HORSEMAN: (
            "prevent_event",
            "heal_source",
            "modify_source_stats",
        ),
        BONY: ("modify_source_stats",),
        MEGA_FATTY: ("heal_source",),
    }

    for card_id, effect_types in expected.items():
        ability = get_monster_def(card_id).abilities[0]
        assert tuple(effect.type for effect in ability.effects) == effect_types
