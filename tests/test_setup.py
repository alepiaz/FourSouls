from foursouls.engine.rng import RNG
from foursouls.model.game_state import GameState
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.setup import setup_game


def _make_cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _two_player_state() -> GameState:
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)
    return GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))


def test_setup_deals_starting_hands_deterministic():
    loot = _make_cards("loot", 20)
    treasure = _make_cards("treasure", 10)
    monsters = _make_cards("monster", 10)

    g1 = setup_game(
        _two_player_state(),
        loot_cards=loot,
        treasure_cards=treasure,
        monster_cards=monsters,
        rng=RNG(seed=42),
    )
    g2 = setup_game(
        _two_player_state(),
        loot_cards=loot,
        treasure_cards=treasure,
        monster_cards=monsters,
        rng=RNG(seed=42),
    )

    p1_hand_1 = g1.state.get_player(PlayerId("P1")).hand
    p1_hand_2 = g2.state.get_player(PlayerId("P1")).hand
    assert len(p1_hand_1) == 3
    assert p1_hand_1 == p1_hand_2

    p2_hand_1 = g1.state.get_player(PlayerId("P2")).hand
    p2_hand_2 = g2.state.get_player(PlayerId("P2")).hand
    assert len(p2_hand_1) == 3
    assert p2_hand_1 == p2_hand_2

    # Different seeds must produce different hands
    g3 = setup_game(
        _two_player_state(),
        loot_cards=loot,
        treasure_cards=treasure,
        monster_cards=monsters,
        rng=RNG(seed=99),
    )
    assert g1.state.get_player(PlayerId("P1")).hand != g3.state.get_player(PlayerId("P1")).hand


def test_shop_cards_are_subset_of_treasure_input():
    """Every card in the shop must have come from the treasure_cards list."""
    loot = _make_cards("loot", 20)
    treasure = _make_cards("treasure", 10)
    monsters = _make_cards("monster", 10)

    g = setup_game(
        _two_player_state(),
        loot_cards=loot,
        treasure_cards=treasure,
        monster_cards=monsters,
        rng=RNG(seed=0),
    )

    treasure_ids = {c.instance_id for c in treasure}
    shop = g.zones.shop_slots
    for i in shop.filled_indices():
        assert shop.get(i).instance_id in treasure_ids


def test_shop_cards_not_in_remaining_treasure_deck():
    """Cards placed in shop slots must be removed from the treasure deck — no double-counting."""
    loot = _make_cards("loot", 20)
    treasure = _make_cards("treasure", 10)
    monsters = _make_cards("monster", 10)

    g = setup_game(
        _two_player_state(),
        loot_cards=loot,
        treasure_cards=treasure,
        monster_cards=monsters,
        rng=RNG(seed=0),
    )

    shop = g.zones.shop_slots
    shop_ids = {shop.get(i).instance_id for i in shop.filled_indices()}
    deck_ids = {c.instance_id for c in g.zones.treasure_deck.cards}
    assert shop_ids.isdisjoint(deck_ids), "Shop cards must not appear in the remaining treasure deck"


def test_shop_fill_does_not_affect_loot_or_monster_zones():
    """Shop setup draws only from the treasure deck; loot and monster decks are unaffected by it."""
    loot = _make_cards("loot", 20)
    treasure = _make_cards("treasure", 10)
    monsters = _make_cards("monster", 10)

    g = setup_game(
        _two_player_state(),
        loot_cards=loot,
        treasure_cards=treasure,
        monster_cards=monsters,
        rng=RNG(seed=0),
        starting_hand_size=0,   # disable hand dealing to isolate shop fill
        shop_size=3,
        monster_slot_count=1,
    )

    # All loot cards should still be in the loot deck (no hand dealt)
    assert len(g.zones.loot_deck) == 20

    # No treasure cards should appear in loot deck
    treasure_ids = {c.instance_id for c in treasure}
    loot_ids = {c.instance_id for c in g.zones.loot_deck.cards}
    assert loot_ids.isdisjoint(treasure_ids)

    # Monster deck and monster slots should not contain any treasure cards
    monster_ids = {c.instance_id for c in g.zones.monster_deck.cards}
    assert monster_ids.isdisjoint(treasure_ids)
    monster_slot_ids = {
        g.zones.monster_slots.get(i).card_ref.instance_id
        for i in g.zones.monster_slots.filled_indices()
    }
    assert monster_slot_ids.isdisjoint(treasure_ids)


def test_shop_fill_order_is_deterministic():
    """Same seed produces identical card in each slot — slot 0 is always the same card."""
    loot = _make_cards("loot", 20)
    treasure = _make_cards("treasure", 10)
    monsters = _make_cards("monster", 10)

    kwargs = dict(loot_cards=loot, treasure_cards=treasure, monster_cards=monsters)
    g1 = setup_game(_two_player_state(), **kwargs, rng=RNG(seed=5))
    g2 = setup_game(_two_player_state(), **kwargs, rng=RNG(seed=5))

    for i in range(3):
        assert g1.zones.shop_slots.get(i) == g2.zones.shop_slots.get(i)

    # Different seed must produce a different arrangement (statistically certain with 10 cards)
    g3 = setup_game(_two_player_state(), **kwargs, rng=RNG(seed=99))
    contents1 = [g1.zones.shop_slots.get(i) for i in range(3)]
    contents3 = [g3.zones.shop_slots.get(i) for i in range(3)]
    assert contents1 != contents3


def test_setup_fills_shop_and_monsters():
    loot = _make_cards("loot", 20)
    treasure = _make_cards("treasure", 10)
    monsters = _make_cards("monster", 10)

    g = setup_game(
        _two_player_state(),
        loot_cards=loot,
        treasure_cards=treasure,
        monster_cards=monsters,
        rng=RNG(seed=0),
    )

    assert g.zones is not None

    # Shop: 3 slots, all filled
    shop = g.zones.shop_slots
    assert len(shop) == 3
    assert all(shop.get(i) is not None for i in range(3))
    assert all(shop.get(i).instance_id.startswith("treasure-") for i in range(3))

    # Monster slots: 2 slots, all filled
    ms = g.zones.monster_slots
    assert len(ms) == 2
    assert all(ms.get(i) is not None for i in range(2))
    assert all(ms.get(i).card_ref.instance_id.startswith("monster-") for i in range(2))

    # Phase is reset to START
    assert g.state.phase == Phase.START

    # Loot deck is smaller: 20 cards - (2 players * 3) dealt
    assert len(g.zones.loot_deck) == 20 - 2 * 3

    # Treasure deck is smaller: 10 - 3 shop fills
    assert len(g.zones.treasure_deck) == 10 - 3

    # Monster deck is smaller: 10 - 2 slot fills
    assert len(g.zones.monster_deck) == 10 - 2
