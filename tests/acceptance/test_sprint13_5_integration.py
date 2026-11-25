"""R13.5.8 deterministic integration and regression coverage."""
from __future__ import annotations

from foursouls.cards.monsters import (
    BONY,
    CURSED_PSY_HORF,
    FLY,
    HEADLESS_HORSEMAN,
    THE_BLOAT,
    make_monster_in_play,
)
from foursouls.engine.events import (
    CombatRollResult,
    EffectFizzled,
    ItemActivated,
    MonsterDeathWouldOccur,
    StackItemCancelled,
)
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.abilities import AbilityDefinition
from foursouls.model.commands import PassPriority
from foursouls.model.game_state import GameState
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.combat import (
    activate_monster_in_slot,
    check_all_monster_deaths_out_of_combat,
    place_monster_card,
    unregister_monster_abilities,
)
from foursouls.rulesets.common.effects import CancelStackItemEffect


def _ref(name, card_id):
    return CardRef(InstanceId(name), card_id)


def _game(seed=0, player_names=("A", "B")):
    players = []
    for name in player_names:
        player_id = PlayerId(name)
        player = PlayerState(
            player_id=player_id,
            max_hp=10,
            hp=10,
        )
        player.character = ItemInPlay(
            card_ref=CardRef(InstanceId(f"character-{name}")),
            eternal=True,
        )
        players.append(player)

    state = GameState.from_players(
        players,
        active_player_id=players[0].player_id,
    )
    state.phase = Phase.ACTION
    monster_slots: SlotsZone[MonsterInPlay] = SlotsZone(size=3)
    zones = GameZones(
        loot_deck=DeckZone(),
        loot_discard=DiscardZone(),
        treasure_deck=DeckZone(),
        treasure_discard=DiscardZone(),
        monster_deck=DeckZone(),
        monster_discard=DiscardZone(),
        shop_slots=SlotsZone(size=2),
        monster_slots=monster_slots,
    )
    return Game(state=state, zones=zones, rng=RNG(seed=seed))


def _resolve_one(game):
    events = []
    for _ in game.state.turn_order:
        events.extend(game.step(PassPriority()).events)
    return events


def _resolve_all(game):
    events = []
    guard = 0
    while not game.stack.empty():
        events.extend(_resolve_one(game))
        guard += 1
        assert guard < 20
    return events


def _roll_event(game, roll=1):
    return CombatRollResult(
        attacker_id=game.state.active_player_id,
        defender_slot=2,
        roll=roll,
        evade=3,
        is_hit=False,
    )


def test_simultaneous_monster_triggers_resolve_fifo():
    game = _game()
    place_monster_card(game, 0, _ref("bony-1", BONY))
    place_monster_card(game, 1, _ref("bony-2", BONY))
    first = game.zones.monster_slots.get(0)
    second = game.zones.monster_slots.get(1)

    game.emit(_roll_event(game))
    assert len(game.ability_engine.trigger_queue) == 2
    assert game.ability_engine.trigger_queue.peek().ability.source.card_ref == first.card_ref

    assert game.activate_next_trigger()
    assert game.stack.top().source == first.card_ref
    assert len(game.ability_engine.trigger_queue) == 1

    _resolve_one(game)
    assert first.attack_bonus == 2
    assert second.attack_bonus == 0
    assert game.stack.top().source == second.card_ref

    _resolve_one(game)
    assert second.attack_bonus == 2
    assert game.stack.empty()


def test_composed_effects_keep_yaml_order_on_lifo_stack():
    game = _game()
    definition = AbilityDefinition.model_validate(
        {
            "ability_id": "ordered_damage",
            "kind": "triggered",
            "trigger": {"type": "event", "event_type": "ItemActivated"},
            "targets": [{"type": "triggering_player"}],
            "effects": [
                {"type": "deal_damage", "amount": 1},
                {"type": "deal_damage", "amount": 2},
            ],
        }
    )
    monster = make_monster_in_play(_ref("composition", FLY))
    monster.abilities = (definition,)
    game.zones.monster_slots.set(0, monster)
    target = game.state.get_player(PlayerId("B"))

    game.emit(ItemActivated(player_id=PlayerId("B"), source="test"))
    assert game.activate_next_trigger()
    assert game.stack.top().label == "Ability:ordered_damage:0"

    _resolve_one(game)
    assert target.hp == 9
    assert game.stack.top().label == "Ability:ordered_damage:1"

    _resolve_one(game)
    assert target.hp == 7


def test_source_leaving_play_fizzles_then_reentry_gets_new_identity():
    game = _game()
    place_monster_card(game, 0, _ref("bony", BONY))
    bony = game.zones.monster_slots.get(0)
    old_entry = bony.zone_entry_id

    game.emit(_roll_event(game))
    game.activate_next_trigger()
    place_monster_card(game, 0, _ref("cover", FLY), cover=True)

    events = _resolve_one(game)
    assert any(isinstance(event, EffectFizzled) for event in events)
    assert bony.attack_bonus == 0
    assert not game.zone_identities.is_active(old_entry)

    cover = game.zones.monster_slots.get(0)
    unregister_monster_abilities(game, cover)
    uncovered = game.zones.monster_slots.remove_top(0)
    assert uncovered is bony
    activate_monster_in_slot(game, 0, uncovered)
    assert bony.zone_entry_id != old_entry

    game.emit(_roll_event(game))
    game.activate_next_trigger()
    _resolve_all(game)
    assert bony.attack_bonus == 2


def test_trigger_stack_item_can_be_cancelled_without_applying_effect():
    game = _game()
    place_monster_card(game, 0, _ref("bony", BONY))
    bony = game.zones.monster_slots.get(0)

    game.emit(_roll_event(game))
    game.activate_next_trigger()
    ability_item = game.stack.top()
    game.push_to_stack(
        controller_id=game.state.active_player_id,
        source="test:cancel",
        effect=CancelStackItemEffect(
            target_stack_id=ability_item.stack_id,
            stack=game.stack,
            log=game.log,
        ),
        label="CancelAbility",
    )

    events = _resolve_one(game)
    assert any(isinstance(event, StackItemCancelled) for event in events)
    assert not game.stack.contains(ability_item.stack_id)
    assert bony.attack_bonus == 0


def test_usage_and_duration_state_are_independent_per_incarnation():
    game = _game()
    place_monster_card(game, 0, _ref("horseman-1", HEADLESS_HORSEMAN))
    place_monster_card(game, 1, _ref("horseman-2", HEADLESS_HORSEMAN))
    first = game.zones.monster_slots.get(0)
    second = game.zones.monster_slots.get(1)
    first.current_hp = 0
    second.current_hp = 0

    check_all_monster_deaths_out_of_combat(game)

    assert (first.current_hp, second.current_hp) == (2, 2)
    assert (first.attack_bonus, second.attack_bonus) == (-1, -1)
    assert (first.evade_bonus, second.evade_bonus) == (1, 1)
    subscriptions = game.event_dispatcher.subscriptions_for(
        MonsterDeathWouldOccur
    )
    assert [item.ability.uses for item in subscriptions] == [1, 1]
    assert game.durations.active_count() == 2

    first.current_hp = 0
    second.current_hp = 0
    check_all_monster_deaths_out_of_combat(game)

    assert game.zones.monster_slots.get(0) is None
    assert game.zones.monster_slots.get(1) is None
    assert game.durations.active_count() == 0


def test_sync_is_idempotent_and_does_not_duplicate_dispatch():
    game = _game()
    place_monster_card(game, 0, _ref("psy-horf", CURSED_PSY_HORF))
    game.sync_monster_abilities()
    game.sync_monster_abilities()

    assert len(game.event_dispatcher.subscriptions_for(ItemActivated)) == 1
    game.emit(ItemActivated(player_id=PlayerId("B"), source="test"))
    assert len(game.ability_engine.trigger_queue) == 1


def _deterministic_scenario(seed):
    game = _game(seed=seed, player_names=("A", "B", "C"))
    place_monster_card(game, 0, _ref("bloat", THE_BLOAT))
    before_resolution = tuple(
        game.state.get_player(player_id).hp
        for player_id in game.state.turn_order
    )
    events = [type(event).__name__ for event in game.log.events]
    events.extend(type(event).__name__ for event in _resolve_all(game))
    after_resolution = tuple(
        game.state.get_player(player_id).hp
        for player_id in game.state.turn_order
    )
    return before_resolution, after_resolution, tuple(events)


def test_same_seed_and_actions_produce_same_state_and_events():
    first = _deterministic_scenario(73)
    second = _deterministic_scenario(73)

    assert first == second
    assert first[0] == (10, 10, 10)
    assert sorted(first[1]) == [8, 10, 10]
