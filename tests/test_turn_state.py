from foursouls.model.game_state import GameState
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import PlayerId
from foursouls.model.turn_state import TurnPhase


def test_default_turn_state_exists_on_game_state():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)

    gs = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))

    assert gs.turn.number == 1
    assert gs.turn.phase == TurnPhase.START
    assert gs.turn.loot1_scheduled is False
    assert gs.turn.attack_used is False
    assert gs.turn.purchase_used is False
    assert gs.turn.loot_play_used is False
