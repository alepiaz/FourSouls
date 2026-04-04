import pytest

from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, HandZone, SlotsZone, ZoneEmptyError


def test_deck_draw_order_lifo_top_is_end():
    deck = DeckZone(cards=[1, 2, 3])  # 3 is top
    assert deck.peek() == 3
    assert deck.draw(1) == [3]
    assert deck.draw(2) == [2, 1]
    assert deck.empty()


def test_deck_draw_too_many_raises():
    deck = DeckZone(cards=[1])
    with pytest.raises(ZoneEmptyError):
        deck.draw(2)


def test_deck_shuffle_deterministic():
    d1 = DeckZone(cards=list(range(10)))
    d2 = DeckZone(cards=list(range(10)))

    r1 = RNG(seed=123)
    r2 = RNG(seed=123)

    d1.shuffle(r1)
    d2.shuffle(r2)

    assert d1.cards == d2.cards


def test_discard_add_and_top():
    disc = DiscardZone()
    disc.add("A")
    disc.add("B")
    assert disc.top() == "B"
    assert len(disc) == 2


def test_discard_top_empty_raises():
    disc = DiscardZone()
    with pytest.raises(ZoneEmptyError):
        disc.top()


def test_hand_add_remove_contains():
    hand = HandZone()
    hand.add("X")
    hand.add("Y")
    assert hand.contains("X")
    hand.remove("X")
    assert not hand.contains("X")
    assert len(hand) == 1


def test_slots_zone_set_get_and_indices():
    slots = SlotsZone(size=3)
    assert slots.get(0) is None

    slots.set(1, "M1")
    assert slots.get(1) == "M1"

    assert slots.empty_indices() == [0, 2]
    assert slots.filled_indices() == [1]

    slots.clear(1)
    assert slots.empty_indices() == [0, 1, 2]


def test_slots_invalid_size_raises():
    with pytest.raises(ValueError):
        SlotsZone(size=0)


def test_slots_index_out_of_range_raises():
    slots = SlotsZone(size=2)
    with pytest.raises(IndexError):
        slots.get(2)