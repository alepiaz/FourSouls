import pytest

from foursouls.cards.monsters import CURSED_CHEST, FLY, make_monster_in_play
from foursouls.cli.app import build_demo_game
from foursouls.engine.events import ItemActivated
from foursouls.engine.target_resolver import TargetResolver
from foursouls.engine.zone_identity import ZoneIdentityRegistry
from foursouls.model.abilities import (
    AbilityContext,
    AbilityDefinition,
    AbilityInstance,
)
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId
from foursouls.model.target import MonsterTarget, PlayerTarget, SoulTarget


def _ability(game, selector, card_ref=None):
    card_ref = card_ref or CardRef(InstanceId("source"), CardId("TEST"))
    source = game.zone_identities.enter(
        card_ref,
        zone="monster_slot",
        target=MonsterTarget(0),
    )
    definition = AbilityDefinition.model_validate(
        {
            "ability_id": "target-test",
            "kind": "triggered",
            "trigger": {"type": "event", "event_type": "ItemActivated"},
            "targets": [selector],
            "effects": [{"type": "prevent_event"}],
        }
    )
    ability = AbilityInstance(
        instance_id="target-test:instance",
        definition=definition,
        source=source,
        controller_id=PlayerId("A"),
    )
    context = AbilityContext(
        ability_instance_id=ability.instance_id,
        source=source,
        controller_id=ability.controller_id,
        triggering_event=ItemActivated(
            player_id=PlayerId("B"),
            source="item:test",
        ),
    )
    return ability, context


def test_zone_entry_identity_changes_after_leave_and_reentry():
    registry = ZoneIdentityRegistry()
    card_ref = CardRef(InstanceId("monster-1"), CardId("FLY"))

    first = registry.enter(
        card_ref,
        zone="monster_slot",
        target=MonsterTarget(0),
    )
    with pytest.raises(ValueError, match="already"):
        registry.enter(
            card_ref,
            zone="monster_slot",
            target=MonsterTarget(1),
        )

    assert registry.leave(first.zone_entry_id)
    second = registry.enter(
        card_ref,
        zone="monster_slot",
        target=MonsterTarget(1),
    )

    assert first.zone_entry_id != second.zone_entry_id
    assert registry.resolve(first.zone_entry_id) is None
    assert registry.resolve(second.zone_entry_id) == MonsterTarget(1)


def test_source_and_triggering_player_selectors_are_automatic():
    game = build_demo_game(["A", "B"], seed=42)
    source_ability, source_context = _ability(game, {"type": "source"})
    resolver = TargetResolver(game.zone_identities)

    source = resolver.resolve(
        source_ability.definition.targets[0],
        source_ability,
        source_context,
        game,
    )
    assert source.selected == (MonsterTarget(0),)

    triggering_definition = AbilityDefinition.model_validate(
        {
            "ability_id": "triggering-player",
            "kind": "triggered",
            "trigger": {"type": "event", "event_type": "ItemActivated"},
            "targets": [{"type": "triggering_player"}],
            "effects": [{"type": "prevent_event"}],
        }
    )
    triggering_ability = AbilityInstance(
        instance_id="triggering-player:instance",
        definition=triggering_definition,
        source=source_ability.source,
        controller_id=PlayerId("A"),
    )
    triggering_context = AbilityContext(
        ability_instance_id=triggering_ability.instance_id,
        source=triggering_ability.source,
        controller_id=PlayerId("A"),
        triggering_event=ItemActivated(
            player_id=PlayerId("B"),
            source="item:test",
        ),
    )
    result = resolver.resolve(
        triggering_definition.targets[0],
        triggering_ability,
        triggering_context,
        game,
    )
    assert result.selected == (PlayerTarget(PlayerId("B")),)


def test_random_other_player_is_seeded_and_excludes_controller():
    game = build_demo_game(["A", "B"], seed=42)
    ability, context = _ability(game, {"type": "random_other_player"})

    result = TargetResolver(game.zone_identities).resolve(
        ability.definition.targets[0],
        ability,
        context,
        game,
    )

    assert result.selected == (PlayerTarget(PlayerId("B")),)


def test_chosen_player_exposes_candidates_and_chooser():
    game = build_demo_game(["A", "B"], seed=42)
    ability, context = _ability(game, {"type": "chosen_player"})

    result = TargetResolver(game.zone_identities).resolve(
        ability.definition.targets[0],
        ability,
        context,
        game,
    )

    assert result.requires_choice
    assert result.chooser_id == PlayerId("A")
    assert result.candidates == (
        PlayerTarget(PlayerId("A")),
        PlayerTarget(PlayerId("B")),
    )


def test_chosen_soul_is_chosen_by_its_controller():
    game = build_demo_game(["A", "B"], seed=42)
    soul = CardRef(InstanceId("soul-1"), CardId("MONSTRO"))
    game.state.get_player(PlayerId("B")).souls.append(soul)
    ability, context = _ability(
        game,
        {"type": "chosen_soul", "player_target_index": 0},
    )
    context = AbilityContext(
        ability_instance_id=context.ability_instance_id,
        source=context.source,
        controller_id=context.controller_id,
        triggering_event=context.triggering_event,
        selected_targets=(PlayerTarget(PlayerId("B")),),
    )

    result = TargetResolver(game.zone_identities).resolve(
        ability.definition.targets[0],
        ability,
        context,
        game,
    )

    assert result.requires_choice
    assert result.chooser_id == PlayerId("B")
    assert result.candidates == (
        SoulTarget(PlayerId("B"), soul),
    )


def test_all_monsters_excludes_event_cards():
    game = build_demo_game(["A", "B"], seed=42)
    game.zones.monster_slots.set(
        0,
        make_monster_in_play(
            CardRef(InstanceId("fly"), FLY)
        ),
    )
    game.zones.monster_slots.set(
        1,
        make_monster_in_play(
            CardRef(InstanceId("event"), CURSED_CHEST)
        ),
    )
    ability, context = _ability(game, {"type": "all_monsters"})

    result = TargetResolver(game.zone_identities).resolve(
        ability.definition.targets[0],
        ability,
        context,
        game,
    )

    assert result.selected == (MonsterTarget(0),)


def test_game_zone_exit_cleans_subscriptions_and_durations():
    game = build_demo_game(["A", "B"], seed=42)
    card_ref = CardRef(InstanceId("leaving"), FLY)
    monster = make_monster_in_play(card_ref)
    monster.attack_bonus = 2
    game.zones.monster_slots.set(0, monster)
    source = game.zone_identities.enter(
        card_ref,
        zone="monster_slot",
        target=MonsterTarget(0),
    )
    definition = AbilityDefinition.model_validate(
        {
            "ability_id": "leaving-listener",
            "kind": "triggered",
            "trigger": {"type": "event", "event_type": "ItemActivated"},
            "effects": [{"type": "prevent_event"}],
        }
    )
    ability = AbilityInstance(
        instance_id="leaving-listener:instance",
        definition=definition,
        source=source,
        controller_id=PlayerId("A"),
    )
    game.event_dispatcher.subscribe(ItemActivated, ability)
    game.durations.register_monster_stats(
        zone_entry_id=source.zone_entry_id,
        monster=monster,
        attack_delta=2,
        evade_delta=0,
        expires_turn=game.state.turn_number,
    )

    assert game.leave_zone_entry(source.zone_entry_id)

    assert not game.zone_identities.is_active(source.zone_entry_id)
    assert not game.event_dispatcher.subscriptions_for(ItemActivated)
    assert game.durations.active_count() == 0
    assert monster.attack_bonus == 0
