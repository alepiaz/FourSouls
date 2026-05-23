"""
R5.2 — Legal action query API tests.

Covers:
- get_legal_actions returns a LegalAction for every legal command
- PassPriority action has key "pass" and correct kind
- EndTurn action has key "end_turn"
- PlayLoot action carries card_id and card_name in metadata
- PlayLoot key encodes card_id and instance_id
- BuyShop action carries slot_index, item_name, and cost in metadata
- AttackMonster action carries monster_name, hp, evade in metadata
- RollCombat action carries monster and attacker stats in metadata
- ActivateCharacterAbility action carries character info in metadata
- every action's .command matches what game.legal_commands() returns
- game.get_legal_actions() delegates correctly
- descriptions are non-empty strings
"""
from __future__ import annotations

import pytest

from foursouls.cards.monsters import GAPER, make_monster_in_play
from foursouls.engine.actions import LegalAction, get_legal_actions
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import (
    AttackMonster,
    BuyShop,
    EndTurn,
    PassPriority,
    PlayLoot,
    RollCombat,
)
from foursouls.model.game_state import GameState
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.legality import TREASURE_COST


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

P1 = PlayerId("P1")
COIN_ID = CardId("LOOT_COIN")
TREASURE_ID = CardId("HEALTH_POTION")


def _coin(n: int) -> CardRef:
    return CardRef(InstanceId(f"c{n}"), COIN_ID)


def _treasure(n: int) -> CardRef:
    return CardRef(InstanceId(f"t{n}"), TREASURE_ID)


def _gaper(n: int) -> MonsterInPlay:
    return make_monster_in_play(CardRef(InstanceId(f"m{n}"), GAPER))


def _zones(
    *,
    hand: list[CardRef] | None = None,
    shop: list[CardRef] | None = None,
    monsters: list[MonsterInPlay] | None = None,
) -> GameZones:
    shop_cards = shop or []
    shop_slots: SlotsZone[CardRef] = SlotsZone(size=max(len(shop_cards), 1))
    for i, c in enumerate(shop_cards):
        shop_slots.set(i, c)

    monster_list = monsters or []
    m_slots: SlotsZone[MonsterInPlay] = SlotsZone(size=max(len(monster_list), 1))
    for i, m in enumerate(monster_list):
        m_slots.set(i, m)

    return GameZones(
        loot_deck=DeckZone(),
        loot_discard=DiscardZone(),
        treasure_deck=DeckZone(),
        treasure_discard=DiscardZone(),
        monster_deck=DeckZone(),
        monster_discard=DiscardZone(),
        shop_slots=shop_slots,
        monster_slots=m_slots,
    )


def _game_in_action(
    *,
    hand: list[CardRef] | None = None,
    shop: list[CardRef] | None = None,
    monsters: list[MonsterInPlay] | None = None,
    cents: int = 0,
    with_character: bool = False,
) -> Game:
    character = None
    if with_character:
        char_ref = CardRef(InstanceId("char0"), CardId("MAGDALENE"))
        character = ItemInPlay(card_ref=char_ref)
    p1 = PlayerState(player_id=P1, max_hp=4, hp=4, cents=cents)
    p1.character = character
    if hand:
        p1.hand.extend(hand)
    gs = GameState.from_players([p1], active_player_id=P1)
    gs.phase = Phase.ACTION
    zones = _zones(hand=hand, shop=shop, monsters=monsters)
    return Game(state=gs, zones=zones)


def _actions_by_kind(game: Game) -> dict[str, list[LegalAction]]:
    out: dict[str, list[LegalAction]] = {}
    for a in get_legal_actions(game):
        out.setdefault(a.kind, []).append(a)
    return out


# ---------------------------------------------------------------------------
# Structure: commands ↔ actions parity
# ---------------------------------------------------------------------------

def test_action_count_matches_legal_commands():
    g = _game_in_action(hand=[_coin(1)], shop=[_treasure(0)], monsters=[_gaper(0)], cents=TREASURE_COST)
    assert len(get_legal_actions(g)) == len(g.legal_commands())


def test_every_action_command_is_in_legal_commands():
    g = _game_in_action(hand=[_coin(1)], shop=[_treasure(0)], monsters=[_gaper(0)], cents=TREASURE_COST)
    legal = g.legal_commands()
    for action in get_legal_actions(g):
        assert action.command in legal


def test_action_kind_matches_command_kind():
    g = _game_in_action(hand=[_coin(1)])
    for action in get_legal_actions(g):
        assert action.kind == action.command.kind


# ---------------------------------------------------------------------------
# PassPriority
# ---------------------------------------------------------------------------

def test_pass_priority_key():
    g = _game_in_action()
    by_kind = _actions_by_kind(g)
    assert "PASS" in by_kind
    assert by_kind["PASS"][0].key == "pass"


def test_pass_priority_description_nonempty():
    g = _game_in_action()
    by_kind = _actions_by_kind(g)
    assert by_kind["PASS"][0].description


# ---------------------------------------------------------------------------
# EndTurn
# ---------------------------------------------------------------------------

def test_end_turn_key():
    g = _game_in_action()
    by_kind = _actions_by_kind(g)
    assert "END_TURN" in by_kind
    assert by_kind["END_TURN"][0].key == "end_turn"


# ---------------------------------------------------------------------------
# PlayLoot
# ---------------------------------------------------------------------------

def test_play_loot_present_when_card_in_hand():
    g = _game_in_action(hand=[_coin(1)])
    by_kind = _actions_by_kind(g)
    assert "PLAY_LOOT" in by_kind


def test_play_loot_key_encodes_card_and_instance():
    coin = _coin(7)
    g = _game_in_action(hand=[coin])
    by_kind = _actions_by_kind(g)
    a = by_kind["PLAY_LOOT"][0]
    assert COIN_ID in a.key
    assert coin.instance_id in a.key


def test_play_loot_metadata_card_id():
    coin = _coin(3)
    g = _game_in_action(hand=[coin])
    a = _actions_by_kind(g)["PLAY_LOOT"][0]
    assert a.metadata["card_id"] == str(COIN_ID)


def test_play_loot_metadata_card_name():
    coin = _coin(3)
    g = _game_in_action(hand=[coin])
    a = _actions_by_kind(g)["PLAY_LOOT"][0]
    # card_name is the human-readable display name, not the raw card ID
    assert a.metadata["card_name"] == "Loot Coin"


def test_play_loot_metadata_instance_id():
    coin = _coin(3)
    g = _game_in_action(hand=[coin])
    a = _actions_by_kind(g)["PLAY_LOOT"][0]
    assert a.metadata["instance_id"] == str(coin.instance_id)


def test_play_loot_one_action_per_card_in_hand():
    g = _game_in_action(hand=[_coin(1), _coin(2), _coin(3)])
    by_kind = _actions_by_kind(g)
    assert len(by_kind["PLAY_LOOT"]) == 3


def test_play_loot_keys_are_unique_for_different_instances():
    g = _game_in_action(hand=[_coin(1), _coin(2)])
    play_actions = _actions_by_kind(g)["PLAY_LOOT"]
    keys = [a.key for a in play_actions]
    assert len(set(keys)) == 2


# ---------------------------------------------------------------------------
# BuyShop
# ---------------------------------------------------------------------------

def test_buy_shop_present_when_affordable():
    g = _game_in_action(shop=[_treasure(0)], cents=TREASURE_COST)
    by_kind = _actions_by_kind(g)
    assert "BUY_SHOP" in by_kind


def test_buy_shop_absent_when_broke():
    g = _game_in_action(shop=[_treasure(0)], cents=0)
    by_kind = _actions_by_kind(g)
    assert "BUY_SHOP" not in by_kind


def test_buy_shop_key_encodes_slot():
    g = _game_in_action(shop=[_treasure(0)], cents=TREASURE_COST)
    a = _actions_by_kind(g)["BUY_SHOP"][0]
    assert a.key == "buy:0"


def test_buy_shop_metadata_slot_index():
    g = _game_in_action(shop=[_treasure(0)], cents=TREASURE_COST)
    a = _actions_by_kind(g)["BUY_SHOP"][0]
    assert a.metadata["slot_index"] == 0


def test_buy_shop_metadata_cost():
    g = _game_in_action(shop=[_treasure(0)], cents=TREASURE_COST)
    a = _actions_by_kind(g)["BUY_SHOP"][0]
    assert a.metadata["cost"] == TREASURE_COST


def test_buy_shop_metadata_item_name():
    from foursouls.cli.render import pretty_name
    t = _treasure(0)
    g = _game_in_action(shop=[t], cents=TREASURE_COST)
    a = _actions_by_kind(g)["BUY_SHOP"][0]
    assert a.metadata["item_name"] == pretty_name(str(TREASURE_ID))


# ---------------------------------------------------------------------------
# AttackMonster
# ---------------------------------------------------------------------------

def test_attack_monster_present_when_monsters_exist():
    g = _game_in_action(monsters=[_gaper(0)])
    by_kind = _actions_by_kind(g)
    assert "ATTACK_MONSTER" in by_kind


def test_attack_monster_key_encodes_slot():
    g = _game_in_action(monsters=[_gaper(0)])
    a = _actions_by_kind(g)["ATTACK_MONSTER"][0]
    assert a.key == "attack:0"


def test_attack_monster_metadata_monster_name():
    from foursouls.cli.render import pretty_name
    g = _game_in_action(monsters=[_gaper(0)])
    a = _actions_by_kind(g)["ATTACK_MONSTER"][0]
    assert a.metadata["monster_name"] == pretty_name(str(GAPER))


def test_attack_monster_metadata_hp():
    m = _gaper(0)
    g = _game_in_action(monsters=[m])
    a = _actions_by_kind(g)["ATTACK_MONSTER"][0]
    assert a.metadata["monster_hp"] == m.current_hp


def test_attack_monster_metadata_evade():
    m = _gaper(0)
    g = _game_in_action(monsters=[m])
    a = _actions_by_kind(g)["ATTACK_MONSTER"][0]
    assert a.metadata["monster_evade"] == m.evade


def test_attack_monster_one_action_per_slot():
    g = _game_in_action(monsters=[_gaper(0), _gaper(1)])
    # Two monster slots
    m_slots = g.zones.monster_slots
    m_slots.set(1, _gaper(1))
    by_kind = _actions_by_kind(g)
    assert len(by_kind["ATTACK_MONSTER"]) == 2


# ---------------------------------------------------------------------------
# RollCombat
# ---------------------------------------------------------------------------

def test_roll_combat_present_during_active_combat():
    from foursouls.model.commands import AttackMonster
    g = _game_in_action(monsters=[_gaper(0)])
    g.step(AttackMonster(slot_index=0))
    by_kind = _actions_by_kind(g)
    assert "ROLL_COMBAT" in by_kind


def test_roll_combat_key():
    g = _game_in_action(monsters=[_gaper(0)])
    g.step(AttackMonster(slot_index=0))
    a = _actions_by_kind(g)["ROLL_COMBAT"][0]
    assert a.key == "roll_combat"


def test_roll_combat_metadata_monster_name():
    from foursouls.cli.render import pretty_name
    g = _game_in_action(monsters=[_gaper(0)])
    g.step(AttackMonster(slot_index=0))
    a = _actions_by_kind(g)["ROLL_COMBAT"][0]
    assert a.metadata["monster_name"] == pretty_name(str(GAPER))


def test_roll_combat_metadata_attacker_hp():
    g = _game_in_action(monsters=[_gaper(0)])
    g.step(AttackMonster(slot_index=0))
    a = _actions_by_kind(g)["ROLL_COMBAT"][0]
    assert a.metadata["attacker_hp"] == 4


# ---------------------------------------------------------------------------
# ActivateCharacterAbility
# ---------------------------------------------------------------------------

def test_activate_character_present_when_untapped():
    g = _game_in_action(with_character=True)
    by_kind = _actions_by_kind(g)
    assert "ACTIVATE_CHARACTER_ABILITY" in by_kind


def test_activate_character_key():
    g = _game_in_action(with_character=True)
    a = _actions_by_kind(g)["ACTIVATE_CHARACTER_ABILITY"][0]
    assert a.key == "activate_character"


def test_activate_character_metadata_card_id():
    g = _game_in_action(with_character=True)
    a = _actions_by_kind(g)["ACTIVATE_CHARACTER_ABILITY"][0]
    assert a.metadata["character_card_id"] == "MAGDALENE"


# ---------------------------------------------------------------------------
# game.get_legal_actions() delegation
# ---------------------------------------------------------------------------

def test_game_method_returns_same_as_function():
    g = _game_in_action(hand=[_coin(1)], monsters=[_gaper(0)])
    via_method = g.get_legal_actions()
    via_function = get_legal_actions(g)
    assert len(via_method) == len(via_function)
    for m, f in zip(via_method, via_function):
        assert m.key == f.key
        assert m.command == f.command


# ---------------------------------------------------------------------------
# All descriptions are non-empty strings
# ---------------------------------------------------------------------------

def test_all_descriptions_nonempty():
    g = _game_in_action(
        hand=[_coin(1)],
        shop=[_treasure(0)],
        monsters=[_gaper(0)],
        cents=TREASURE_COST,
        with_character=True,
    )
    for a in get_legal_actions(g):
        assert isinstance(a.description, str) and a.description
