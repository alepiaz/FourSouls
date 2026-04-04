"""
Release 3.0 — Shop state scaffold tests.

Covers:
- shop slot can hold treasure refs
- empty vs occupied slot behavior is deterministic
- player treasure area can receive bought cards
"""
from __future__ import annotations

import pytest

from foursouls.engine.rng import RNG
from foursouls.engine.zones import SlotsZone
from foursouls.model.game_state import GameState
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.setup import setup_game


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ref(name: str) -> CardRef:
    return CardRef(InstanceId(name))


def _make_cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _two_player_state() -> GameState:
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)
    return GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))


# ---------------------------------------------------------------------------
# SlotsZone — shop slot primitives
# ---------------------------------------------------------------------------

class TestShopSlotPrimitives:
    def test_new_slot_zone_is_fully_empty(self):
        zone: SlotsZone[CardRef] = SlotsZone(size=3)
        assert zone.empty_indices() == [0, 1, 2]
        assert zone.filled_indices() == []

    def test_set_slot_makes_it_occupied(self):
        zone: SlotsZone[CardRef] = SlotsZone(size=3)
        card = _ref("treasure-A")
        zone.set(0, card)
        assert zone.get(0) == card
        assert zone.is_occupied(0)
        assert not zone.is_empty(0)

    def test_clear_slot_makes_it_empty(self):
        zone: SlotsZone[CardRef] = SlotsZone(size=3)
        zone.set(1, _ref("treasure-B"))
        zone.clear(1)
        assert zone.get(1) is None
        assert zone.is_empty(1)
        assert not zone.is_occupied(1)

    def test_empty_and_filled_indices_are_disjoint_and_complete(self):
        zone: SlotsZone[CardRef] = SlotsZone(size=4)
        zone.set(0, _ref("t0"))
        zone.set(2, _ref("t2"))
        assert zone.filled_indices() == [0, 2]
        assert zone.empty_indices() == [1, 3]
        assert sorted(zone.filled_indices() + zone.empty_indices()) == list(range(4))

    def test_get_returns_exact_ref_placed(self):
        zone: SlotsZone[CardRef] = SlotsZone(size=2)
        card = _ref("unique-treasure")
        zone.set(0, card)
        assert zone.get(0) is card

    def test_out_of_range_index_raises(self):
        zone: SlotsZone[CardRef] = SlotsZone(size=3)
        with pytest.raises(IndexError):
            zone.get(3)
        with pytest.raises(IndexError):
            zone.is_occupied(3)
        with pytest.raises(IndexError):
            zone.is_empty(-1)

    def test_deterministic_fill_order(self):
        """Same fill sequence always produces same slot contents."""
        cards = _make_cards("t", 3)
        zone: SlotsZone[CardRef] = SlotsZone(size=3)
        for i, card in enumerate(cards):
            zone.set(i, card)
        assert [zone.get(i) for i in range(3)] == cards


# ---------------------------------------------------------------------------
# setup_game — shop slots after setup
# ---------------------------------------------------------------------------

class TestShopSetupState:
    def test_shop_slots_filled_after_setup(self):
        g = setup_game(
            _two_player_state(),
            loot_cards=_make_cards("loot", 20),
            treasure_cards=_make_cards("treasure", 10),
            monster_cards=_make_cards("monster", 10),
            rng=RNG(seed=0),
        )
        shop = g.zones.shop_slots
        assert len(shop) == 3
        assert shop.filled_indices() == [0, 1, 2]
        assert shop.empty_indices() == []

    def test_shop_slots_hold_treasure_refs(self):
        g = setup_game(
            _two_player_state(),
            loot_cards=_make_cards("loot", 20),
            treasure_cards=_make_cards("treasure", 10),
            monster_cards=_make_cards("monster", 10),
            rng=RNG(seed=0),
        )
        shop = g.zones.shop_slots
        for i in range(3):
            ref = shop.get(i)
            assert ref is not None
            assert isinstance(ref, CardRef)
            assert ref.instance_id.startswith("treasure-")

    def test_shop_not_enough_treasures_leaves_slot_empty(self):
        """If treasure deck runs out during setup, remaining slots stay empty."""
        g = setup_game(
            _two_player_state(),
            loot_cards=_make_cards("loot", 20),
            treasure_cards=_make_cards("treasure", 1),  # only 1 card for 3 slots
            monster_cards=_make_cards("monster", 10),
            rng=RNG(seed=0),
            shop_size=3,
        )
        shop = g.zones.shop_slots
        assert len(shop.filled_indices()) == 1
        assert len(shop.empty_indices()) == 2

    def test_shop_state_is_deterministic_across_same_seed(self):
        kwargs = dict(
            loot_cards=_make_cards("loot", 20),
            treasure_cards=_make_cards("treasure", 10),
            monster_cards=_make_cards("monster", 10),
        )
        g1 = setup_game(_two_player_state(), **kwargs, rng=RNG(seed=7))
        g2 = setup_game(_two_player_state(), **kwargs, rng=RNG(seed=7))
        for i in range(3):
            assert g1.zones.shop_slots.get(i) == g2.zones.shop_slots.get(i)


# ---------------------------------------------------------------------------
# PlayerState — treasure area
# ---------------------------------------------------------------------------

class TestPlayerTreasureArea:
    def _player(self) -> PlayerState:
        return PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)

    def test_treasure_area_empty_at_start(self):
        p = self._player()
        assert p.treasures == []
        assert p.items == []

    def test_gain_treasure_adds_to_area(self):
        p = self._player()
        card = _ref("treasure-X")
        p.gain_treasure(card)
        assert card in p.treasures
        assert len(p.treasures) == 1

    def test_gain_multiple_treasures(self):
        p = self._player()
        cards = [_ref(f"t{i}") for i in range(3)]
        for c in cards:
            p.gain_treasure(c)
        assert p.treasures == cards

    def test_treasures_is_same_list_as_items(self):
        """treasures property is a live view of items — no copy."""
        p = self._player()
        assert p.treasures is p.items

    def test_treasure_area_independent_per_player(self):
        p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
        p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)
        card = _ref("shared-treasure")
        p1.gain_treasure(card)
        assert card in p1.treasures
        assert card not in p2.treasures
