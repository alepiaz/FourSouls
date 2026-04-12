"""
Release 3.3 — Purchase resolution tests.

Covers:
- cents reduced by correct amount
- chosen treasure removed from shop slot
- treasure added to player treasure area
- purchase flag set and prevents second buy
- ShopBought event emitted
- no unrelated state mutates
"""
from __future__ import annotations

import pytest

from foursouls.engine.events import ShopBought
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import BuyShop, EndTurn
from foursouls.model.game_state import GameState
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.legality import TREASURE_COST


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _card(name: str) -> CardRef:
    return CardRef(InstanceId(name))


def _make_zones(shop_cards: list[CardRef | None], *, shop_size: int = 3) -> GameZones:
    shop: SlotsZone[CardRef] = SlotsZone(size=shop_size)
    for i, card in enumerate(shop_cards):
        if card is not None:
            shop.set(i, card)
    return GameZones(
        loot_deck=DeckZone(),
        loot_discard=DiscardZone(),
        treasure_deck=DeckZone(),
        treasure_discard=DiscardZone(),
        monster_deck=DeckZone(),
        monster_discard=DiscardZone(),
        shop_slots=shop,
        monster_slots=SlotsZone(size=1),
    )


def _game_in_action(
    *,
    cents: int = TREASURE_COST,
    shop_cards: list[CardRef | None] | None = None,
    n_players: int = 1,
) -> Game:
    """Game already in ACTION phase with a populated shop. No stack items."""
    if shop_cards is None:
        shop_cards = [_card("t0"), _card("t1"), _card("t2")]

    players = [
        PlayerState(player_id=PlayerId(f"P{i+1}"), max_hp=2, hp=2, cents=cents)
        for i in range(n_players)
    ]
    gs = GameState.from_players(players, active_player_id=PlayerId("P1"))
    gs.phase = Phase.ACTION
    return Game(state=gs, zones=_make_zones(shop_cards))


# ---------------------------------------------------------------------------
# Resolution: state mutations
# ---------------------------------------------------------------------------

def test_buy_reduces_cents_by_treasure_cost():
    g = _game_in_action(cents=TREASURE_COST * 3)
    before = g.state.get_player(PlayerId("P1")).cents

    g.step(BuyShop(slot_index=0))

    assert g.state.get_player(PlayerId("P1")).cents == before - TREASURE_COST


def test_buy_clears_chosen_shop_slot():
    g = _game_in_action()
    assert g.zones.shop_slots.is_occupied(1)

    g.step(BuyShop(slot_index=1))

    assert g.zones.shop_slots.is_empty(1)


def test_buy_adds_treasure_to_player_area():
    card = _card("special-treasure")
    g = _game_in_action(shop_cards=[card, _card("other"), _card("other2")])

    g.step(BuyShop(slot_index=0))

    p1 = g.state.get_player(PlayerId("P1"))
    assert any(i.card_ref == card for i in p1.treasures)


def test_bought_card_matches_slot_content():
    t0, t1, t2 = _card("t0"), _card("t1"), _card("t2")
    g = _game_in_action(shop_cards=[t0, t1, t2])

    g.step(BuyShop(slot_index=2))

    p1 = g.state.get_player(PlayerId("P1"))
    refs = [i.card_ref for i in p1.treasures]
    assert t2 in refs
    assert t0 not in refs
    assert t1 not in refs


def test_buy_sets_purchase_used_flag():
    g = _game_in_action()
    assert not g.state.turn_flags.purchase_used

    g.step(BuyShop(slot_index=0))

    assert g.state.turn_flags.purchase_used


# ---------------------------------------------------------------------------
# Purchase limit enforcement via step()
# ---------------------------------------------------------------------------

def test_second_buy_is_illegal_after_first():
    g = _game_in_action(cents=TREASURE_COST * 10, shop_cards=[_card("t0"), _card("t1"), _card("t2")])

    g.step(BuyShop(slot_index=0))

    with pytest.raises(ValueError, match="Illegal command"):
        g.step(BuyShop(slot_index=1))


def test_buy_illegal_command_raises_before_any_mutation():
    g = _game_in_action(cents=0)  # can't afford
    cents_before = g.state.get_player(PlayerId("P1")).cents

    with pytest.raises(ValueError, match="Illegal command"):
        g.step(BuyShop(slot_index=0))

    assert g.state.get_player(PlayerId("P1")).cents == cents_before
    assert g.zones.shop_slots.is_occupied(0)


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

def test_buy_emits_shop_bought_event():
    card = _card("t0")
    g = _game_in_action(shop_cards=[card, _card("t1"), _card("t2")])

    events = g.step(BuyShop(slot_index=0)).events

    bought = [e for e in events if isinstance(e, ShopBought)]
    assert len(bought) == 1
    assert bought[0].player_id == PlayerId("P1")
    assert bought[0].card_ref == card
    assert bought[0].slot_index == 0
    assert bought[0].cost == TREASURE_COST


# ---------------------------------------------------------------------------
# No unrelated state mutation
# ---------------------------------------------------------------------------

def test_buy_does_not_affect_other_shop_slots():
    t0, t1, t2 = _card("t0"), _card("t1"), _card("t2")
    g = _game_in_action(shop_cards=[t0, t1, t2])

    g.step(BuyShop(slot_index=1))

    assert g.zones.shop_slots.get(0) == t0
    assert g.zones.shop_slots.get(2) == t2


def test_buy_does_not_affect_other_player_state():
    g = _game_in_action(n_players=2, cents=TREASURE_COST * 5)
    p2_cents_before = g.state.get_player(PlayerId("P2")).cents
    p2_treasures_before = list(g.state.get_player(PlayerId("P2")).treasures)

    g.step(BuyShop(slot_index=0))

    assert g.state.get_player(PlayerId("P2")).cents == p2_cents_before
    assert g.state.get_player(PlayerId("P2")).treasures == p2_treasures_before


def test_buy_does_not_touch_loot_deck():
    g = _game_in_action()
    loot_before = list(g.zones.loot_deck.cards)

    g.step(BuyShop(slot_index=0))

    assert g.zones.loot_deck.cards == loot_before


# ---------------------------------------------------------------------------
# Turn-flag reset on EndTurn
# ---------------------------------------------------------------------------

def test_purchase_flag_resets_for_next_turn():
    """After EndTurn the new active player starts with purchase_used == False."""
    g = _game_in_action(n_players=2)

    g.step(BuyShop(slot_index=0))
    assert g.state.turn_flags.purchase_used

    g.step(EndTurn())

    assert g.state.active_player_id == PlayerId("P2")
    assert not g.state.turn_flags.purchase_used
