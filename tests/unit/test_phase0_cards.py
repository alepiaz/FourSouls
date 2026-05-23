"""
Phase 0 card addition tests.

Verifies that all Phase 0 cards load from YAML and resolve with correct
mechanics. No new engine features are required; every effect type used here
was already supported before this batch.

Loot coins:     TWO_CENTS, THREE_CENTS, FOUR_CENTS, NICKEL
Basic monsters: DINGA, ATTACK_FLY, BOOM_FLY, CLOTTY, MULLIBOIL
"""
from __future__ import annotations

import pytest

from foursouls.cards.loot import (
    TWO_CENTS, THREE_CENTS, FOUR_CENTS, NICKEL,
    _LOOT_REGISTRY,
)
from foursouls.cards.monsters import (
    DINGA, ATTACK_FLY, BOOM_FLY, CLOTTY, MULLIBOIL,
    get_monster_def, make_monster_in_play,
)
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import PassPriority, PlayLoot
from foursouls.model.game_state import GameState
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

P1 = PlayerId("P1")
P2 = PlayerId("P2")


def _ref(name: str, card_id: CardId) -> CardRef:
    return CardRef(InstanceId(name), card_id)


def _char(name: str) -> ItemInPlay:
    return ItemInPlay(card_ref=CardRef(InstanceId(name)))


def _make_action_game() -> Game:
    """Minimal 2-player game in ACTION phase with one loot play available."""
    p1 = PlayerState(player_id=P1, max_hp=3, hp=3)
    p2 = PlayerState(player_id=P2, max_hp=3, hp=3)
    p1.character = _char("char-p1")
    p2.character = _char("char-p2")
    state = GameState.from_players([p1, p2], active_player_id=P1)
    state.phase = Phase.ACTION

    ms: SlotsZone[MonsterInPlay] = SlotsZone(size=2)
    zones = GameZones(
        loot_deck=DeckZone(), loot_discard=DiscardZone(),
        treasure_deck=DeckZone(), treasure_discard=DiscardZone(),
        monster_deck=DeckZone(), monster_discard=DiscardZone(),
        shop_slots=SlotsZone(size=2), monster_slots=ms,
    )
    g = Game(state=state, zones=zones, rng=RNG(seed=0))
    g.state.turn_flags.loot_plays_allowed = 1
    return g


def _resolve(g: Game) -> None:
    """Pass priority for both players, resolving the top stack item."""
    g.step(PassPriority())
    g.step(PassPriority())


# ---------------------------------------------------------------------------
# Loot coin cards
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("card_id,expected_cents", [
    (TWO_CENTS,   2),
    (THREE_CENTS, 3),
    (FOUR_CENTS,  4),
    (NICKEL,      5),
])
def test_coin_loot_cards_are_in_registry(card_id, expected_cents):
    assert card_id in _LOOT_REGISTRY, f"{card_id} not found in loot registry"
    defn = _LOOT_REGISTRY[card_id]
    assert defn.make_effect is not None, f"{card_id} has no effect factory"
    assert not defn.requires_target


@pytest.mark.parametrize("card_id,expected_cents", [
    (TWO_CENTS,   2),
    (THREE_CENTS, 3),
    (FOUR_CENTS,  4),
    (NICKEL,      5),
])
def test_coin_loot_resolves_correctly(card_id, expected_cents):
    g = _make_action_game()
    p1 = g.state.get_player(P1)
    card = _ref(f"coin-{card_id}", card_id)
    p1.hand.append(card)

    g.step(PlayLoot(card_ref=card))
    _resolve(g)

    assert p1.cents == expected_cents, (
        f"{card_id}: expected {expected_cents}¢, got {p1.cents}"
    )


# ---------------------------------------------------------------------------
# Basic monsters — registry and stats
# ---------------------------------------------------------------------------

BASIC_MONSTER_SPECS = [
    # (card_id, hp, evade, atk, reward_coin, reward_loot, has_soul)
    (DINGA,      1, 2, 1, 2, 0, False),
    (ATTACK_FLY, 1, 1, 1, 2, 0, False),
    (BOOM_FLY,   1, 2, 2, 3, 0, False),
    (CLOTTY,     1, 3, 1, 2, 0, False),
    (MULLIBOIL,  2, 3, 1, 2, 0, False),
]


@pytest.mark.parametrize("card_id,hp,evade,atk,coins,loot,soul", BASIC_MONSTER_SPECS)
def test_basic_monster_def_stats(card_id, hp, evade, atk, coins, loot, soul):
    defn = get_monster_def(card_id)
    assert defn.card_id == card_id
    assert defn.base_hp == hp,        f"{card_id}: hp {defn.base_hp} != {hp}"
    assert defn.evade == evade,       f"{card_id}: evade {defn.evade} != {evade}"
    assert defn.attack == atk,        f"{card_id}: atk {defn.attack} != {atk}"
    assert defn.reward_coin == coins, f"{card_id}: coins {defn.reward_coin} != {coins}"
    assert defn.reward_loot == loot,  f"{card_id}: loot_reward {defn.reward_loot} != {loot}"
    assert defn.has_soul == soul
    assert not defn.is_boss
    assert not defn.is_event
    # Phase 0 basics have no trigger hooks
    assert defn.on_death is None
    assert defn.on_miss is None
    assert defn.on_would_take_combat_damage is None
    assert defn.on_would_die is None


@pytest.mark.parametrize("card_id,hp,evade,atk,coins,loot,soul", BASIC_MONSTER_SPECS)
def test_basic_monster_instantiates(card_id, hp, evade, atk, coins, loot, soul):
    ref = CardRef(InstanceId(f"inst-{card_id}"), card_id)
    m = make_monster_in_play(ref)
    assert m.base_hp == hp
    assert m.current_hp == hp
    assert m.evade == evade
    assert m.attack == atk


