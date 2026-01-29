from foursouls.engine.zones import DeckZone, DiscardZone
from foursouls.model.game_state import GameState
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId


def test_game_state_has_loot_zones_and_can_be_injected():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)

    loot_cards = [CardRef(InstanceId("L1")), CardRef(InstanceId("L2"))]
    deck = DeckZone(cards=loot_cards.copy())
    discard = DiscardZone()

    gs = GameState.from_players([p1, p2], loot_deck=deck, loot_discard=discard)

    assert len(gs.loot_deck) == 2
    assert gs.loot_deck.peek().instance_id == InstanceId("L2")  # top is end
    assert len(gs.loot_discard) == 0
