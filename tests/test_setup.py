from foursouls.model.player_state import PlayerState
from foursouls.model.refs import PlayerId
from foursouls.rulesets.common.setup import setup_game_state


def _players_two():
    return [
        PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2),
        PlayerState(player_id=PlayerId("P2"), max_hp=1, hp=1),
    ]


def test_setup_deterministic_same_seed_same_hands():
    players1 = _players_two()
    players2 = _players_two()

    gs1 = setup_game_state(players1, seed=123, starting_hand_size=3)
    gs2 = setup_game_state(players2, seed=123, starting_hand_size=3)

    p1a = gs1.get_player(PlayerId("P1")).hand
    p1b = gs2.get_player(PlayerId("P1")).hand
    p2a = gs1.get_player(PlayerId("P2")).hand
    p2b = gs2.get_player(PlayerId("P2")).hand

    assert [c.instance_id for c in p1a] == [c.instance_id for c in p1b]
    assert [c.instance_id for c in p2a] == [c.instance_id for c in p2b]

    # 8 total cards - 6 dealt = 2 remaining
    assert len(gs1.loot_deck) == 2
    assert len(gs2.loot_deck) == 2


def test_setup_different_seed_changes_order_probabilistically():
    players1 = _players_two()
    players2 = _players_two()

    gs1 = setup_game_state(players1, seed=1, starting_hand_size=3)
    gs2 = setup_game_state(players2, seed=2, starting_hand_size=3)

    p1a = [c.instance_id for c in gs1.get_player(PlayerId("P1")).hand]
    p1b = [c.instance_id for c in gs2.get_player(PlayerId("P1")).hand]

    # Extremely unlikely to be equal with different seeds on 8-card shuffle.
    assert p1a != p1b


def test_setup_rejects_insufficient_cards():
    players = [
        PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2),
        PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2),
        PlayerState(player_id=PlayerId("P3"), max_hp=2, hp=2),
    ]

    try:
        setup_game_state(players, seed=0, starting_hand_size=3)  # 9 needed > 8
        assert False, "Expected ValueError"
    except ValueError:
        pass
