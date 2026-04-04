from foursouls.model.game_state import GameState
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import PlayerId


def test_create_game_state_two_players():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=1, hp=1)  # The Lost-like case

    gs = GameState.from_players([p1, p2], active_player_id=PlayerId("P2"))

    assert gs.active_player_id == PlayerId("P2")
    assert gs.turn_order == [PlayerId("P1"), PlayerId("P2")]
    assert gs.get_player(PlayerId("P1")).hp == 2
    assert gs.get_player(PlayerId("P2")).max_hp == 1
    assert gs.next_player_id(PlayerId("P1")) == PlayerId("P2")
    assert gs.next_player_id(PlayerId("P2")) == PlayerId("P1")


def test_duplicate_player_ids_rejected():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p1b = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)

    try:
        GameState.from_players([p1, p1b])
        assert False, "Expected ValueError for duplicate player IDs"
    except ValueError:
        pass


def test_invalid_active_player_rejected():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)

    try:
        GameState.from_players([p1, p2], active_player_id=PlayerId("P3"))
        assert False, "Expected ValueError for invalid active player"
    except ValueError:
        pass


def test_invalid_hp_rejected():
    try:
        PlayerState(player_id=PlayerId("P1"), max_hp=1, hp=2)
        assert False, "Expected ValueError for hp > max_hp"
    except ValueError:
        pass


def test_game_state_defaults_phase_start():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    gs = GameState.from_players([p1])

    assert gs.phase == Phase.START
    assert gs.turn_number == 1
    assert gs.turn_flags.loot_play_used is False
    assert gs.turn_flags.attack_used is False
    assert gs.turn_flags.purchase_used is False


def test_turn_flags_reset():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)
    gs = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))

    gs.turn_flags.loot_play_used = True
    gs.turn_flags.attack_used = True
    gs.turn_flags.purchase_used = True
    gs.phase = Phase.END

    gs.reset_for_new_turn(PlayerId("P2"))

    assert gs.active_player_id == PlayerId("P2")
    assert gs.phase == Phase.START
    assert gs.turn_number == 2
    assert gs.turn_flags.loot_play_used is False
    assert gs.turn_flags.attack_used is False
    assert gs.turn_flags.purchase_used is False