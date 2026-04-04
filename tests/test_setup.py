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
    assert all(ms.get(i).instance_id.startswith("monster-") for i in range(2))

    # Phase is reset to START
    assert g.state.phase == Phase.START

    # Loot deck is smaller: 20 cards - (2 players * 3) dealt
    assert len(g.zones.loot_deck) == 20 - 2 * 3

    # Treasure deck is smaller: 10 - 3 shop fills
    assert len(g.zones.treasure_deck) == 10 - 3

    # Monster deck is smaller: 10 - 2 slot fills
    assert len(g.zones.monster_deck) == 10 - 2
