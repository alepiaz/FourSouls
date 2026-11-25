from foursouls.cards.monsters import (
    CURSED_PSY_HORF,
    THE_BLOAT,
    get_monster_def,
    make_monster_in_play,
)
from foursouls.model.abilities import (
    AbilityDefinition,
    DealDamageEffect,
    RandomOtherPlayerSelector,
    TriggeringPlayerSelector,
)
from foursouls.model.refs import CardRef, InstanceId


def test_the_bloat_loads_two_composable_triggered_abilities():
    monster = get_monster_def(THE_BLOAT)

    assert (monster.base_hp, monster.evade, monster.attack) == (5, 3, 2)
    assert monster.has_soul
    assert monster.reward_treasure == 1
    assert [ability.ability_id for ability in monster.abilities] == [
        "the_bloat_enter_damage",
        "the_bloat_death_damage",
    ]
    assert [ability.trigger.event_type for ability in monster.abilities] == [
        "MonsterEnteredActiveSlot",
        "MonsterDied",
    ]
    assert all(isinstance(ability, AbilityDefinition) for ability in monster.abilities)
    assert all(isinstance(ability.targets[0], RandomOtherPlayerSelector)
               for ability in monster.abilities)
    assert all(ability.effects == (DealDamageEffect(amount=2),)
               for ability in monster.abilities)


def test_cursed_psy_horf_reuses_item_event_and_damage_effect():
    monster = get_monster_def(CURSED_PSY_HORF)

    assert (monster.base_hp, monster.evade, monster.attack) == (1, 5, 1)
    assert monster.reward_loot == 2
    assert len(monster.abilities) == 1

    ability = monster.abilities[0]
    assert ability.trigger.event_type == "ItemActivated"
    assert isinstance(ability.targets[0], TriggeringPlayerSelector)
    assert ability.effects == (DealDamageEffect(amount=1),)


def test_runtime_monsters_keep_validated_ability_definitions():
    card_ref = CardRef(InstanceId("bloat-probe"), THE_BLOAT)

    monster = make_monster_in_play(card_ref)

    assert monster.abilities == get_monster_def(THE_BLOAT).abilities
    assert monster.abilities[0].effects[0].amount == 2
