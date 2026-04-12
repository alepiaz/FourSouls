"""
Release 4.0 — Monster runtime scaffold tests.

Covers:
- setup creates MonsterInPlay for every occupied monster slot
- current_hp starts equal to base_hp
- deterministic setup (same seed) produces identical monster slots
- empty slots remain None
- monster metadata does not appear in player or shop zones
- real monster definitions (FLY, GAPER, SPIDER) instantiate correctly
"""
from __future__ import annotations


from foursouls.cards.monsters import (
    FLY,
    GAPER,
    SPIDER,
    make_monster_in_play,
)
from foursouls.engine.rng import RNG
from foursouls.model.game_state import GameState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.setup import setup_game


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _monster_card(card_id: CardId, name: str) -> CardRef:
    return CardRef(InstanceId(name), card_id)


def _two_player_state() -> GameState:
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    return GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))


def _setup(**kwargs) -> object:
    defaults = dict(
        loot_cards=_cards("loot", 20),
        treasure_cards=_cards("treasure", 10),
        rng=RNG(seed=0),
    )
    defaults.update(kwargs)
    return setup_game(_two_player_state(), **defaults)


# ---------------------------------------------------------------------------
# Unit tests: make_monster_in_play
# ---------------------------------------------------------------------------

def test_fly_stats():
    ref = _monster_card(FLY, "fly-1")
    m = make_monster_in_play(ref)
    assert m.card_ref is ref
    assert m.base_hp == 1
    assert m.current_hp == 1
    assert m.evade == 2
    assert m.reward_coin == 1
    assert m.has_soul is False


def test_gaper_stats():
    ref = _monster_card(GAPER, "gaper-1")
    m = make_monster_in_play(ref)
    assert m.base_hp == 2
    assert m.current_hp == 2
    assert m.evade == 4
    assert m.reward_coin == 3


def test_spider_stats():
    ref = _monster_card(SPIDER, "spider-1")
    m = make_monster_in_play(ref)
    assert m.base_hp == 1
    assert m.evade == 4
    assert m.reward_loot == 1


def test_unknown_card_id_uses_default():
    ref = CardRef(InstanceId("stub-0"), CardId("NONEXISTENT"))
    m = make_monster_in_play(ref)
    assert m.base_hp >= 1          # default is safe, not zero
    assert m.current_hp == m.base_hp


def test_no_card_id_uses_default():
    ref = CardRef(InstanceId("stub-1"))  # card_id=None
    m = make_monster_in_play(ref)
    assert m.current_hp == m.base_hp


def test_current_hp_starts_at_base_hp():
    for cid in (FLY, GAPER, SPIDER):
        ref = _monster_card(cid, f"{cid}-inst")
        m = make_monster_in_play(ref)
        assert m.current_hp == m.base_hp, f"current_hp != base_hp for {cid}"


def test_take_damage_reduces_hp():
    ref = _monster_card(GAPER, "gaper-dmg")
    m = make_monster_in_play(ref)
    m.take_damage(1)
    assert m.current_hp == m.base_hp - 1


def test_take_damage_does_not_go_below_zero():
    ref = _monster_card(FLY, "fly-overkill")
    m = make_monster_in_play(ref)
    m.take_damage(99)
    assert m.current_hp == 0


def test_is_alive_false_at_zero_hp():
    ref = _monster_card(FLY, "fly-dead")
    m = make_monster_in_play(ref)
    m.take_damage(m.base_hp)
    assert not m.is_alive()


def test_is_alive_true_above_zero():
    ref = _monster_card(GAPER, "gaper-alive")
    m = make_monster_in_play(ref)
    assert m.is_alive()


# ---------------------------------------------------------------------------
# Integration tests: setup_game creates correct monster runtime state
# ---------------------------------------------------------------------------

def test_occupied_slots_contain_monster_in_play_instances():
    g = _setup(monster_cards=_cards("monster", 10), monster_slot_count=2)
    ms = g.zones.monster_slots
    for i in ms.filled_indices():
        assert isinstance(ms.get(i), MonsterInPlay)


def test_current_hp_equals_base_hp_after_setup():
    g = _setup(monster_cards=_cards("monster", 10), monster_slot_count=2)
    ms = g.zones.monster_slots
    for i in ms.filled_indices():
        m = ms.get(i)
        assert m.current_hp == m.base_hp


def test_monster_slot_card_refs_come_from_monster_deck_input():
    monster_cards = _cards("monster", 10)
    monster_ids = {c.instance_id for c in monster_cards}
    g = _setup(monster_cards=monster_cards, monster_slot_count=2)
    ms = g.zones.monster_slots
    for i in ms.filled_indices():
        assert ms.get(i).card_ref.instance_id in monster_ids


def test_deterministic_setup_produces_same_slots():
    kwargs = dict(monster_cards=_cards("monster", 10), monster_slot_count=2)
    g1 = _setup(**kwargs, rng=RNG(seed=7))
    g2 = _setup(**kwargs, rng=RNG(seed=7))
    ms1, ms2 = g1.zones.monster_slots, g2.zones.monster_slots
    for i in range(ms1.size):
        c1, c2 = ms1.get(i), ms2.get(i)
        assert (c1 is None) == (c2 is None)
        if c1 is not None:
            assert c1.card_ref == c2.card_ref


def test_empty_slots_are_none_when_deck_has_fewer_cards_than_slots():
    g = _setup(monster_cards=_cards("monster", 1), monster_slot_count=2)
    ms = g.zones.monster_slots
    filled = ms.filled_indices()
    empty = ms.empty_indices()
    assert len(filled) == 1
    assert len(empty) == 1
    assert ms.get(empty[0]) is None


def test_all_slots_empty_when_monster_deck_is_empty():
    g = _setup(monster_cards=[], monster_slot_count=2)
    ms = g.zones.monster_slots
    assert ms.empty_indices() == [0, 1]


def test_monster_state_not_in_player_zones():
    monster_cards = _cards("monster", 10)
    monster_ids = {c.instance_id for c in monster_cards}
    g = _setup(monster_cards=monster_cards, monster_slot_count=2)
    for pid in g.state.turn_order:
        player = g.state.get_player(pid)
        hand_ids = {c.instance_id for c in player.hand}
        assert hand_ids.isdisjoint(monster_ids)
        item_ids = {i.card_ref.instance_id for i in player.items}
        assert item_ids.isdisjoint(monster_ids)


def test_monster_state_not_in_shop_slots():
    monster_cards = _cards("monster", 10)
    monster_ids = {c.instance_id for c in monster_cards}
    g = _setup(monster_cards=monster_cards, monster_slot_count=2)
    shop = g.zones.shop_slots
    shop_ids = {shop.get(i).instance_id for i in shop.filled_indices()}
    assert shop_ids.isdisjoint(monster_ids)
