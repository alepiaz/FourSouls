from __future__ import annotations

from typing import List, Optional

from foursouls.cards.monsters import make_monster_in_play
from foursouls.engine.events import GameSetupCompleted
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.game_state import GameState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.refs import CardRef, PlayerId
from foursouls.rulesets.common.turn import enter_start_phase


def setup_game(
    state: GameState,
    *,
    loot_cards: List[CardRef],
    treasure_cards: List[CardRef],
    monster_cards: List[CardRef],
    rng: RNG,
    starting_hand_size: int = 3,
    shop_size: int = 3,
    monster_slot_count: int = 2,
    starter_id: Optional[PlayerId] = None,
) -> Game:
    """
    Shuffle decks, deal starting hands, fill shop and monster slots.
    Returns a fully initialised Game (Option A: zones live on Game).
    """
    loot_deck: DeckZone[CardRef] = DeckZone(cards=list(loot_cards))
    loot_discard: DiscardZone[CardRef] = DiscardZone()

    treasure_deck: DeckZone[CardRef] = DeckZone(cards=list(treasure_cards))
    treasure_discard: DiscardZone[CardRef] = DiscardZone()

    monster_deck: DeckZone[CardRef] = DeckZone(cards=list(monster_cards))
    monster_discard: DiscardZone[CardRef] = DiscardZone()

    loot_deck.shuffle(rng)
    treasure_deck.shuffle(rng)
    monster_deck.shuffle(rng)

    # Deal starting loot hand to each player (in turn order)
    for player_id in state.turn_order:
        player = state.get_player(player_id)
        player.hand.extend(loot_deck.draw(starting_hand_size))

    # Fill shop slots from treasure deck
    shop_slots: SlotsZone[CardRef] = SlotsZone(size=shop_size)
    for idx in range(shop_size):
        if not treasure_deck.empty():
            shop_slots.set(idx, treasure_deck.draw(1)[0])

    # Fill monster slots from monster deck
    m_slots: SlotsZone[MonsterInPlay] = SlotsZone(size=monster_slot_count)
    for idx in range(monster_slot_count):
        if not monster_deck.empty():
            m_slots.set(idx, make_monster_in_play(monster_deck.draw(1)[0]))

    # Finalise state
    state.active_player_id = starter_id or state.active_player_id
    state.phase = Phase.START

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
    enter_start_phase(game)

    game.log.append(GameSetupCompleted(
        player_ids=tuple(state.turn_order),
        starting_hand_size=starting_hand_size,
        shop_size=shop_size,
        monster_slot_count=monster_slot_count,
    ))

    return game
