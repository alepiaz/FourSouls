from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone
from foursouls.model.commands import PassPriority
from foursouls.engine.game_loop import Game
from foursouls.model.game_state import GameState
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId


def test_loot1_reshuffles_discard_into_deck_when_deck_empty():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)

    # Empty deck, discard has one card
    deck = DeckZone(cards=[])
    discard = DiscardZone(cards=[CardRef(InstanceId("D1"))])

    gs = GameState.from_players(
        [p1, p2], active_player_id=PlayerId("P1"), loot_deck=deck, loot_discard=discard
    )
    g = Game(gs, rng=RNG(seed=123))

    # Resolve Loot1 via pass/pass
    g.step(PassPriority())
    g.step(PassPriority())

    hand = g.state.get_player(PlayerId("P1")).hand
    assert len(hand) == 1
    assert hand[0].instance_id == InstanceId("D1")

    # Discard should be emptied into deck then drawn
    assert len(g.state.loot_discard) == 0
