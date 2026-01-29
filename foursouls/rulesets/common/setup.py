from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone
from foursouls.model.game_state import GameState
from foursouls.model.monster import MonsterState
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId


@dataclass(frozen=True, slots=True)
class DummyLootCard:
    """
    Minimal definition for Sprint 1 setup/testing.
    We keep it tiny: just enough to generate CardRefs with readable IDs.
    """

    instance_id: InstanceId
    name: str


def dummy_loot_cards() -> List[DummyLootCard]:
    """
    The small 'real-card' loot list requested.
    NOTE: These are single cards (unique instances) in this tiny test deck.
    """
    return [
        DummyLootCard(InstanceId("LOOT_COIN_1"), "1¢"),
        DummyLootCard(InstanceId("LOOT_COIN_2"), "2¢"),
        DummyLootCard(InstanceId("LOOT_COIN_3"), "3¢"),
        DummyLootCard(InstanceId("LOOT_COIN_4"), "4¢"),
        DummyLootCard(InstanceId("LOOT_COIN_5"), "5¢"),
        DummyLootCard(InstanceId("LOOT_COIN_10"), "10¢"),
        DummyLootCard(
            InstanceId("LOOT_BOMB"), "Bomb (deal 1 damage to a monster or a player)"
        ),
        DummyLootCard(InstanceId("LOOT_DICE"), "Dice (reroll a dice result)"),
    ]


def build_dummy_loot_deck_zone() -> DeckZone[CardRef]:
    """
    Build the Sprint 1 loot deck as CardRefs (instances).
    """
    cards = [CardRef(c.instance_id) for c in dummy_loot_cards()]
    return DeckZone(cards=cards)


def setup_game_state(
    players: List[PlayerState],
    *,
    seed: Optional[int] = None,
    starting_hand_size: int = 3,
    active_player_index: int = 0,
) -> GameState:
    """
    Deterministic setup for Sprint 1:
    - builds the tiny loot deck (8 real single cards)
    - shuffles with seed
    - deals starting hands
    - creates GameState with loot deck + discard

    We raise if there aren't enough cards to deal.
    """
    if starting_hand_size < 0:
        raise ValueError("starting_hand_size must be >= 0")
    if not players:
        raise ValueError("Must provide at least one player")
    if not (0 <= active_player_index < len(players)):
        raise ValueError("active_player_index out of range")

    rng = RNG(seed=seed)

    loot_deck = build_dummy_loot_deck_zone()
    loot_discard = DiscardZone[CardRef]()
    loot_deck.shuffle(rng)

    total_needed = starting_hand_size * len(players)
    if total_needed > len(loot_deck):
        raise ValueError(
            f"Not enough loot cards to deal starting hands: "
            f"need {total_needed}, have {len(loot_deck)}"
        )

    # Deal hands in player list order (turn order)
    for p in players:
        drawn = loot_deck.draw(starting_hand_size)
        p.hand.extend(drawn)

    gs = GameState.from_players(
        players,
        active_player_id=players[active_player_index].player_id,
        loot_deck=loot_deck,
        loot_discard=loot_discard,
    )

    # Setup dummy monster in slot 0 (Sprint 2)
    dingle = MonsterState(name="DINGLE", hp=2, max_hp=2)
    gs.monster_slots.set(0, dingle)

    return gs
