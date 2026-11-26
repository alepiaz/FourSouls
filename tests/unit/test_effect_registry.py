import pytest
from pydantic import ValidationError

from foursouls.cards.monsters import THE_BLOAT, make_monster_in_play
from foursouls.cli.app import build_demo_game
from foursouls.engine.effect_registry import EffectBuildError, EffectRegistry
from foursouls.model.abilities import (
    AbilityContext,
    AbilityDefinition,
    AbilitySource,
    DealDamageEffect as DealDamageDefinition,
    DestroySoulEffect as DestroySoulDefinition,
    DestroySourceEffect as DestroySourceDefinition,
    GrantDeckAttackEffect as GrantDeckAttackDefinition,
    HealSourceEffect,
    ModifySourceStatsEffect,
    PreventEventEffect,
)
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.model.target import MonsterTarget, PlayerTarget, SoulTarget
from foursouls.rulesets.common.effects import (
    DealDamageEffect,
    DestroyMonsterEffect,
    DestroySoulEffect,
    GrantDeckAttackEffect,
    HealMonsterEffect,
    ModifyMonsterStatsEffect,
)


def _game():
    return build_demo_game(["A", "B"], seed=42)


def _context(card_ref, targets=()):
    return AbilityContext(
        ability_instance_id="ability-1",
        source=AbilitySource(
            card_ref=card_ref,
            zone="monster_slot",
            zone_entry_id=f"{card_ref.instance_id}:entry-1",
        ),
        controller_id=PlayerId("A"),
        selected_targets=targets,
    )


def test_damage_type_belongs_only_to_damage_definition():
    damage = DealDamageDefinition(amount=2, damage_type="combat")
    assert damage.damage_type == "combat"

    with pytest.raises(ValidationError):
        GrantDeckAttackDefinition.model_validate(
            {"required": True, "damage_type": "ability"}
        )


def test_registry_builds_bloat_damage_for_resolved_player_target():
    game = _game()
    definition = make_monster_in_play(
        CardRef(InstanceId("bloat"), THE_BLOAT)
    ).abilities[0].effects[0]
    context = _context(
        CardRef(InstanceId("bloat"), THE_BLOAT),
        (PlayerTarget(PlayerId("B")),),
    )

    effect = EffectRegistry().build(definition, context, game)

    assert isinstance(effect, DealDamageEffect)
    assert effect.player_id == PlayerId("B")
    assert effect.amount == 2
    before = game.state.get_player(PlayerId("B")).hp
    effect.apply(game.state)
    assert game.state.get_player(PlayerId("B")).hp == max(0, before - 2)


def test_composed_effects_preserve_definition_order():
    game = _game()
    definitions = (
        GrantDeckAttackDefinition(required=True),
        DealDamageDefinition(amount=1),
    )
    context = _context(
        CardRef(InstanceId("source")),
        (PlayerTarget(PlayerId("B")),),
    )

    effects = EffectRegistry().build_sequence(definitions, context, game)

    assert [type(effect) for effect in effects] == [
        GrantDeckAttackEffect,
        DealDamageEffect,
    ]
    assert effects[0].required is True


def test_heal_source_captures_the_current_monster_instance():
    game = _game()
    card_ref = CardRef(InstanceId("bloat"), THE_BLOAT)
    monster = make_monster_in_play(card_ref)
    monster.current_hp = 1
    game.zones.monster_slots.set(0, monster)
    context = _context(card_ref, (MonsterTarget(0),))

    effect = EffectRegistry().build(
        HealSourceEffect(amount=2),
        context,
        game,
    )

    assert isinstance(effect, HealMonsterEffect)
    assert effect.validate(game.state)
    effect.apply(game.state)
    assert monster.current_hp == 3


def test_end_of_turn_source_stat_effect_is_atomic():
    game = _game()
    card_ref = CardRef(InstanceId("bloat"), THE_BLOAT)
    monster = make_monster_in_play(card_ref)
    game.zones.monster_slots.set(0, monster)
    context = _context(card_ref, (MonsterTarget(0),))

    effect = EffectRegistry().build(
        ModifySourceStatsEffect(
            attack_delta=2,
            evade_delta=-1,
            duration="end_of_turn",
        ),
        context,
        game,
    )

    assert isinstance(effect, ModifyMonsterStatsEffect)
    effect.apply(game.state)
    assert monster.attack_bonus == 2
    assert monster.evade_bonus == -1
    assert game.durations.active_count() == 1

    assert game.durations.expire_end_of_turn(
        game.state.turn_number
    ) == 1
    assert monster.attack_bonus == 0
    assert monster.evade_bonus == 0
    assert game.durations.active_count() == 0


def test_zone_exit_expires_only_that_entry_modifiers():
    game = _game()
    first_ref = CardRef(InstanceId("first"), THE_BLOAT)
    second_ref = CardRef(InstanceId("second"), THE_BLOAT)
    first = make_monster_in_play(first_ref)
    second = make_monster_in_play(second_ref)
    game.zones.monster_slots.set(0, first)
    game.zones.monster_slots.set(1, second)

    for slot, monster, card_ref in (
        (0, first, first_ref),
        (1, second, second_ref),
    ):
        context = _context(card_ref, (MonsterTarget(slot),))
        effect = EffectRegistry().build(
            ModifySourceStatsEffect(
                attack_delta=1,
                duration="end_of_turn",
            ),
            context,
            game,
        )
        effect.apply(game.state)

    assert game.durations.expire_zone_entry(
        "first:entry-1"
    ) == 1
    assert first.attack_bonus == 0
    assert second.attack_bonus == 1
    assert game.durations.active_count() == 1


def test_source_effect_rejects_a_stale_or_wrong_slot():
    game = _game()
    card_ref = CardRef(InstanceId("bloat"), THE_BLOAT)
    context = _context(card_ref, (MonsterTarget(0),))

    with pytest.raises(EffectBuildError, match="no longer"):
        EffectRegistry().build(HealSourceEffect(amount=1), context, game)


def test_replacement_definitions_cannot_enter_normal_effect_registry():
    game = _game()
    context = _context(CardRef(InstanceId("source")))

    with pytest.raises(EffectBuildError, match="replacement pipeline"):
        EffectRegistry().build(PreventEventEffect(), context, game)


def test_non_end_of_turn_stat_duration_is_deferred():
    game = _game()
    card_ref = CardRef(InstanceId("bloat"), THE_BLOAT)
    monster = make_monster_in_play(card_ref)
    game.zones.monster_slots.set(0, monster)
    context = _context(card_ref, (MonsterTarget(0),))

    with pytest.raises(EffectBuildError, match="end_of_turn"):
        EffectRegistry().build(
            ModifySourceStatsEffect(attack_delta=1, duration="permanent"),
            context,
            game,
        )


def test_destroy_soul_uses_the_preselected_soul_instance():
    game = _game()
    soul = CardRef(InstanceId("soul-1"), THE_BLOAT)
    player = game.state.get_player(PlayerId("B"))
    player.souls.append(soul)
    context = _context(
        CardRef(InstanceId("wizoob")),
        (SoulTarget(PlayerId("B"), soul),),
    )

    effect = EffectRegistry().build(
        DestroySoulDefinition(),
        context,
        game,
    )

    assert isinstance(effect, DestroySoulEffect)
    assert effect.validate(game.state)
    effect.apply(game.state)
    assert soul not in player.souls
    assert not effect.validate(game.state)


def test_destroy_source_marks_the_exact_monster_for_death_processing():
    game = _game()
    card_ref = CardRef(InstanceId("deaths-head"), THE_BLOAT)
    monster = make_monster_in_play(card_ref)
    game.zones.monster_slots.set(1, monster)
    context = _context(card_ref, (MonsterTarget(1),))

    effect = EffectRegistry().build(
        DestroySourceDefinition(),
        context,
        game,
    )

    assert isinstance(effect, DestroyMonsterEffect)
    assert effect.validate(game.state)
    effect.apply(game.state)
    assert monster.current_hp == 0
    assert not effect.validate(game.state)
