import pytest

from foursouls.cards.monsters import (
    CARRION_QUEEN,
    CURSED_PSY_HORF,
    FLY,
    get_monster_def,
    make_monster_in_play,
)
from foursouls.cli.app import build_demo_game
from foursouls.engine.events import (
    DamageWouldBeDealt,
    ItemActivated,
    MonsterDied,
)
from foursouls.engine.replacement import ReplacementPipeline
from foursouls.engine.target_resolver import TargetResolutionError
from foursouls.model.abilities import (
    AbilityDefinition,
    AbilityInstance,
)
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.model.target import MonsterTarget, PlayerTarget, SoulTarget


def _register_monster_ability(game, card_ref, definition, slot=0):
    monster = make_monster_in_play(card_ref)
    game.zones.monster_slots.set(slot, monster)
    source = game.zone_identities.enter(
        card_ref,
        zone="monster_slot",
        target=MonsterTarget(slot),
    )
    ability = AbilityInstance(
        instance_id=f"{card_ref.instance_id}:{definition.ability_id}",
        definition=definition,
        source=source,
        controller_id=game.state.active_player_id,
    )
    event_type = {
        "ItemActivated": ItemActivated,
        "MonsterDied": MonsterDied,
        "DamageWouldBeDealt": DamageWouldBeDealt,
    }[definition.trigger.event_type]
    game.event_dispatcher.subscribe(event_type, ability)
    return monster, ability


def test_cursed_psy_horf_trigger_is_queued_then_put_on_stack():
    game = build_demo_game(["A", "B"], seed=42)
    card_ref = CardRef(InstanceId("psy-horf"), CURSED_PSY_HORF)
    definition = get_monster_def(CURSED_PSY_HORF).abilities[0]
    _, ability = _register_monster_ability(game, card_ref, definition)
    target_player = game.state.get_player(PlayerId("B"))
    hp_before = target_player.hp
    stack_before = len(game.stack)

    contexts = game.emit(
        ItemActivated(player_id=PlayerId("B"), source="item:test")
    )

    assert len(contexts) == 1
    assert len(game.ability_engine.trigger_queue) == 1
    assert target_player.hp == hp_before

    pending = game.ability_engine.resolve_next(game)
    assert pending is not None
    assert pending.ability is ability
    assert len(game.stack) == stack_before + 1
    assert target_player.hp == hp_before

    item = game.stack.pop()
    assert item.effect.validate(game.state)
    item.effect.apply(game.state)
    assert target_player.hp == hp_before - 1


def test_wizoob_two_stage_choice_preserves_choice_ownership():
    game = build_demo_game(["A", "B"], seed=42)
    soul = CardRef(InstanceId("soul"), CARRION_QUEEN)
    game.state.get_player(PlayerId("B")).souls.append(soul)
    definition = AbilityDefinition.model_validate(
        {
            "ability_id": "wizoob_destroy_soul",
            "kind": "triggered",
            "trigger": {"type": "event", "event_type": "MonsterDied"},
            "targets": [
                {"type": "chosen_player"},
                {"type": "chosen_soul", "player_target_index": 0},
            ],
            "effects": [{"type": "destroy_soul"}],
        }
    )
    card_ref = CardRef(InstanceId("wizoob"), FLY)
    _, ability = _register_monster_ability(game, card_ref, definition)
    event = MonsterDied(
        attacker_id=PlayerId("A"),
        slot_index=0,
        card_ref=card_ref,
        monster_name="WIZOOB",
        had_soul=False,
    )

    game.emit(event)
    pending = game.ability_engine.trigger_queue.peek()
    assert pending is not None
    assert pending.choice.chooser_id == PlayerId("A")

    game.ability_engine.choose_target(
        pending.pending_id,
        PlayerTarget(PlayerId("B")),
        PlayerId("A"),
        game,
    )
    assert pending.choice.chooser_id == PlayerId("B")
    assert pending.choice.candidates == (
        SoulTarget(PlayerId("B"), soul),
    )

    with pytest.raises(TargetResolutionError, match="wrong player"):
        game.ability_engine.choose_target(
            pending.pending_id,
            SoulTarget(PlayerId("B"), soul),
            PlayerId("A"),
            game,
        )

    game.ability_engine.choose_target(
        pending.pending_id,
        SoulTarget(PlayerId("B"), soul),
        PlayerId("B"),
        game,
    )
    assert pending.choice is None

    game.ability_engine.resolve_next(game)
    item = game.stack.pop()
    item.effect.apply(game.state)
    assert soul not in game.state.get_player(PlayerId("B")).souls
    assert ability.uses == 1


def test_carrion_queen_prevents_only_matching_roll_damage_to_itself():
    game = build_demo_game(["A", "B"], seed=42)
    card_ref = CardRef(InstanceId("queen"), CARRION_QUEEN)
    definition = AbilityDefinition.model_validate(
        {
            "ability_id": "queen_prevention",
            "kind": "replacement",
            "trigger": {
                "type": "event",
                "event_type": "DamageWouldBeDealt",
            },
            "conditions": [
                {"type": "source_in_zone", "zone": "monster_slot"},
                {"type": "event_target_is_ability_source"},
                {"type": "roll_in", "values": [4, 5]},
            ],
            "effects": [{"type": "prevent_event"}],
        }
    )
    _, ability = _register_monster_ability(game, card_ref, definition)
    pipeline = ReplacementPipeline()

    prevented = pipeline.apply_damage(
        DamageWouldBeDealt(
            source_player_id=PlayerId("A"),
            source_monster_slot=None,
            target_player_id=None,
            target_monster_slot=0,
            amount=1,
            reason="combat_hit",
            roll=4,
            target_card_ref=card_ref,
        ),
        game,
    )
    assert prevented.prevented
    assert prevented.amount == 0
    assert prevented.applied_ability_ids == (ability.instance_id,)

    wrong_roll = pipeline.apply_damage(
        DamageWouldBeDealt(
            source_player_id=PlayerId("A"),
            source_monster_slot=None,
            target_player_id=None,
            target_monster_slot=0,
            amount=1,
            reason="combat_hit",
            roll=6,
            target_card_ref=card_ref,
        ),
        game,
    )
    assert not wrong_roll.prevented
    assert wrong_roll.amount == 1

    other_target = pipeline.apply_damage(
        DamageWouldBeDealt(
            source_player_id=PlayerId("A"),
            source_monster_slot=None,
            target_player_id=None,
            target_monster_slot=1,
            amount=1,
            reason="combat_hit",
            roll=4,
            target_card_ref=CardRef(InstanceId("fly"), FLY),
        ),
        game,
    )
    assert not other_target.prevented
    assert other_target.amount == 1
