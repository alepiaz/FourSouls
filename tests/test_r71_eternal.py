"""
R7.1 — eternal flag on ItemInPlay; starting items are eternal.

Rules context
-------------
The death penalty (R7.2) requires the dying player to destroy one non-eternal
item.  R7.1 adds the `eternal` flag to ItemInPlay and marks starting character
cards as eternal so R7.2 can filter them out of the destroyable-item list.

Invariants tested
-----------------
- ItemInPlay.eternal defaults to False for freely constructed items.
- Character items built by build_demo_game have eternal=True.
- Items with eternal=True can still be tapped/untapped (flag is orthogonal).
"""
from __future__ import annotations

from foursouls.cli.app import build_demo_game
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.refs import CardRef, InstanceId, PlayerId


# ---------------------------------------------------------------------------
# ItemInPlay defaults
# ---------------------------------------------------------------------------

def test_eternal_defaults_to_false():
    item = ItemInPlay(card_ref=CardRef(InstanceId("x")))
    assert item.eternal is False


def test_eternal_can_be_set_true():
    item = ItemInPlay(card_ref=CardRef(InstanceId("x")), eternal=True)
    assert item.eternal is True


def test_eternal_is_orthogonal_to_tapped():
    item = ItemInPlay(card_ref=CardRef(InstanceId("x")), eternal=True)
    assert not item.is_tapped
    item.tap()
    assert item.is_tapped
    assert item.eternal is True  # tap does not change eternal


# ---------------------------------------------------------------------------
# Starting items are eternal
# ---------------------------------------------------------------------------

def test_build_demo_game_characters_are_eternal():
    g = build_demo_game(["Alice", "Bob"], seed=0)
    for pid in g.state.turn_order:
        char = g.state.get_player(pid).character
        assert char is not None, f"{pid} has no character"
        assert char.eternal is True, f"{pid}'s character is not eternal"


def test_non_starting_item_is_not_eternal():
    """An ItemInPlay created without eternal=True is not eternal."""
    item = ItemInPlay(card_ref=CardRef(InstanceId("treasure-0")))
    assert item.eternal is False
