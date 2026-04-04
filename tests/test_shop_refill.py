"""
Release 3.4 — Shop refill tests.

Covers:
- bought slot refills from top of treasure deck
- refill is deterministic (same deck order, same result)
- empty deck leaves slot empty
- neighboring slots are unchanged
- treasure deck shrinks by exactly one on refill
- no other zone is touched by refill
"""
from __future__ import annotations

from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import BuyShop
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


def _make_zones(
    shop_cards: list[CardRef | None],
    deck_cards: list[CardRef],
    *,
    shop_size: int = 3,
) -> GameZones:
    shop: SlotsZone[CardRef] = SlotsZone(size=shop_size)
    for i, card in enumerate(shop_cards):
        if card is not None:
            shop.set(i, card)
    # DeckZone treats index -1 as top; put_on_top appends, so last card in list = top
    treasure_deck: DeckZone[CardRef] = DeckZone(cards=list(deck_cards))
    return GameZones(
        loot_deck=DeckZone(),
        loot_discard=DiscardZone(),
        treasure_deck=treasure_deck,
        treasure_discard=DiscardZone(),
        monster_deck=DeckZone(),
        monster_discard=DiscardZone(),
        shop_slots=shop,
        monster_slots=SlotsZone(size=1),
    )


def _game_in_action(
    *,
    shop_cards: list[CardRef | None] | None = None,
    deck_cards: list[CardRef] | None = None,
    cents: int = TREASURE_COST,
) -> Game:
    if shop_cards is None:
        shop_cards = [_card("s0"), _card("s1"), _card("s2")]
    if deck_cards is None:
        deck_cards = [_card("deck-bottom"), _card("deck-top")]

    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2, cents=cents)
    gs = GameState.from_players([p1])
    gs.phase = Phase.ACTION
    return Game(state=gs, zones=_make_zones(shop_cards, deck_cards))


# ---------------------------------------------------------------------------
# Refill happy path
# ---------------------------------------------------------------------------

def test_refill_occupies_bought_slot():
    g = _game_in_action(deck_cards=[_card("refill")])
    assert g.zones.shop_slots.is_occupied(0)

    g.step(BuyShop(slot_index=0))

    assert g.zones.shop_slots.is_occupied(0)


def test_refill_uses_top_of_deck():
    """The card placed in the slot is the one that was on top of the deck."""
    top = _card("deck-top")
    bottom = _card("deck-bottom")
    # DeckZone.draw() pops from the end, so top must be last in the list
    g = _game_in_action(deck_cards=[bottom, top])

    g.step(BuyShop(slot_index=1))

    assert g.zones.shop_slots.get(1) == top


def test_refill_is_deterministic():
    """Same deck contents always produce the same refill card."""
    deck = [_card("d0"), _card("d1"), _card("d2")]
    shop = [_card("s0"), _card("s1"), _card("s2")]

    def run() -> CardRef:
        g = _game_in_action(shop_cards=list(shop), deck_cards=list(deck))
        g.step(BuyShop(slot_index=0))
        return g.zones.shop_slots.get(0)

    assert run() == run()


def test_refill_removes_card_from_treasure_deck():
    deck = [_card("d0"), _card("d1")]
    g = _game_in_action(deck_cards=deck)
    deck_size_before = len(g.zones.treasure_deck)

    g.step(BuyShop(slot_index=0))

    assert len(g.zones.treasure_deck) == deck_size_before - 1


def test_refill_card_not_in_deck_after_refill():
    top = _card("top")
    g = _game_in_action(deck_cards=[_card("other"), top])

    g.step(BuyShop(slot_index=0))

    remaining_ids = {c.instance_id for c in g.zones.treasure_deck.cards}
    assert top.instance_id not in remaining_ids


# ---------------------------------------------------------------------------
# Empty deck — slot stays empty
# ---------------------------------------------------------------------------

def test_empty_deck_leaves_slot_empty():
    g = _game_in_action(deck_cards=[])

    g.step(BuyShop(slot_index=0))

    assert g.zones.shop_slots.is_empty(0)


def test_empty_deck_does_not_affect_other_slots():
    s1, s2 = _card("s1"), _card("s2")
    g = _game_in_action(shop_cards=[_card("s0"), s1, s2], deck_cards=[])

    g.step(BuyShop(slot_index=0))

    assert g.zones.shop_slots.get(1) == s1
    assert g.zones.shop_slots.get(2) == s2


# ---------------------------------------------------------------------------
# Neighboring slots unchanged on refill
# ---------------------------------------------------------------------------

def test_only_bought_slot_changes():
    s0, s1, s2 = _card("s0"), _card("s1"), _card("s2")
    g = _game_in_action(shop_cards=[s0, s1, s2], deck_cards=[_card("refill")])

    g.step(BuyShop(slot_index=1))

    assert g.zones.shop_slots.get(0) == s0
    assert g.zones.shop_slots.get(2) == s2


def test_refill_goes_to_correct_slot():
    s0, s1, s2 = _card("s0"), _card("s1"), _card("s2")
    refill = _card("refill")
    g = _game_in_action(shop_cards=[s0, s1, s2], deck_cards=[refill])

    g.step(BuyShop(slot_index=2))

    assert g.zones.shop_slots.get(2) == refill
    assert g.zones.shop_slots.get(0) == s0
    assert g.zones.shop_slots.get(1) == s1


# ---------------------------------------------------------------------------
# No other zone is touched by refill
# ---------------------------------------------------------------------------

def test_refill_does_not_touch_loot_deck():
    g = _game_in_action(deck_cards=[_card("refill")])
    loot_before = list(g.zones.loot_deck.cards)

    g.step(BuyShop(slot_index=0))

    assert g.zones.loot_deck.cards == loot_before


def test_refill_does_not_touch_treasure_discard():
    g = _game_in_action(deck_cards=[_card("refill")])

    g.step(BuyShop(slot_index=0))

    assert g.zones.treasure_discard.empty()
