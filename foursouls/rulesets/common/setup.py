from __future__ import annotations

from typing import Optional, Sequence

from foursouls.rulesets.common.combat import place_monster_card
from foursouls.engine.events import GameSetupCompleted
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.game_state import GameState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.refs import CardRef, PlayerId
from foursouls.rulesets.common.turn import enter_start_phase


def _make_deck(cards: Sequence[CardRef]) -> tuple[DeckZone[CardRef], DiscardZone[CardRef]]:
    return DeckZone(cards=list(cards)), DiscardZone()


def setup_game(
    state: GameState,
    *,
    loot_cards: Sequence[CardRef],
    treasure_cards: Sequence[CardRef],
    monster_cards: Sequence[CardRef],
    rng: RNG,
    starting_hand_size: int = 3,
    shop_size: int = 2,
    monster_slot_count: int = 2,
    starter_id: Optional[PlayerId] = None,
) -> Game:
    """
    Shuffle decks, deal starting hands, fill shop and monster slots.
    Returns a fully initialised Game (zones live on Game).
    """
    loot_deck, loot_discard = _make_deck(loot_cards)
    treasure_deck, treasure_discard = _make_deck(treasure_cards)
    monster_deck, monster_discard = _make_deck(monster_cards)

    loot_deck.shuffle(rng)
    treasure_deck.shuffle(rng)
    monster_deck.shuffle(rng)

    # Deal starting loot hands, guarded against short decks
    for player_id in state.turn_order:
        player = state.get_player(player_id)
        for _ in range(starting_hand_size):
            if loot_deck.empty():
                break
            player.hand.extend(loot_deck.draw(1))

    # Fill shop slots from treasure deck
    shop_slots: SlotsZone[CardRef] = SlotsZone(size=shop_size)
    for idx in range(shop_size):
        if not treasure_deck.empty():
            shop_slots.set(idx, treasure_deck.draw(1)[0])

    # Resolve starting player: explicit starter_id takes priority, else keep existing
    if starter_id is not None:
        state.active_player_id = starter_id

    m_slots: SlotsZone[MonsterInPlay] = SlotsZone(size=monster_slot_count)

    zones = GameZones(
        loot_deck=loot_deck,
        loot_discard=loot_discard,
        treasure_deck=treasure_deck,
        treasure_discard=treasure_discard,
        monster_deck=monster_deck,
        monster_discard=monster_discard,
        shop_slots=shop_slots,
        monster_slots=m_slots,
    )

    game = Game(state=state, zones=zones, rng=rng)

    # Fill initial monster slots before entering START phase so the board
    # exists when the first turn begins.
    for idx in range(monster_slot_count):
        if not game.zones.monster_deck.empty():
            ref = game.zones.monster_deck.draw(1)[0]
            place_monster_card(game, idx, ref)

    # Phase transition is enter_start_phase's responsibility.
    enter_start_phase(game)

    game.log.append(GameSetupCompleted(
        player_ids=tuple(state.turn_order),
        starting_hand_size=starting_hand_size,
        shop_size=shop_size,
        monster_slot_count=monster_slot_count,
    ))

    return game
