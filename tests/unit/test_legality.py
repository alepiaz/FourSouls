from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import ActivateCharacterAbility, BuyShop, EndTurn, PassPriority, PlayLoot
from foursouls.model.effects import AppendMarkerEffect
from foursouls.model.game_state import GameState
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.legality import TREASURE_COST, legal_commands


def _card(name: str) -> CardRef:
    return CardRef(InstanceId(name))


def _game(phase: Phase = Phase.ACTION) -> Game:
    """Minimal single-player game for legality unit tests (no zones needed)."""
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    gs = GameState.from_players([p1])
    gs.phase = phase
    return Game(state=gs)


def test_pass_always_legal():
    cmds = legal_commands(_game(Phase.START))
    assert any(isinstance(c, PassPriority) for c in cmds)


def test_end_turn_legal_in_action_phase_with_empty_stack():
    cmds = legal_commands(_game(Phase.ACTION))
    assert any(isinstance(c, EndTurn) for c in cmds)


def test_end_turn_illegal_when_stack_not_empty():
    g = _game(Phase.ACTION)
    g.stack.push(controller_id=PlayerId("P1"), source="test", effect=AppendMarkerEffect("x"))
    cmds = legal_commands(g)
    assert not any(isinstance(c, EndTurn) for c in cmds)


def test_end_turn_illegal_in_start_phase():
    # START phase: Loot1 is resolving; EndTurn must not be legal.
    cmds = legal_commands(_game(Phase.START))
    assert not any(isinstance(c, EndTurn) for c in cmds)


def test_end_turn_legal_in_end_phase():
    # END phase: reached after active-player death (R7.3); EndTurn must be legal.
    cmds = legal_commands(_game(Phase.END))
    assert any(isinstance(c, EndTurn) for c in cmds)


# ── PlayLoot legality ──────────────────────────────────────────────────────────

def test_play_loot_legal_for_each_card_in_hand():
    g = _game(Phase.ACTION)
    card_a, card_b = _card("a"), _card("b")
    g.state.get_player(PlayerId("P1")).hand = [card_a, card_b]

    cmds = legal_commands(g)

    loot_cmds = [c for c in cmds if isinstance(c, PlayLoot)]
    assert len(loot_cmds) == 2
    assert PlayLoot(card_ref=card_a) in loot_cmds
    assert PlayLoot(card_ref=card_b) in loot_cmds


def test_play_loot_illegal_when_quota_exhausted():
    g = _game(Phase.ACTION)
    g.state.get_player(PlayerId("P1")).hand = [_card("a")]
    g.state.turn_flags.loot_plays_used = 1  # used == allowed (default 1)

    cmds = legal_commands(g)
    assert not any(isinstance(c, PlayLoot) for c in cmds)


def test_play_loot_illegal_outside_action_phase():
    g = _game(Phase.START)
    g.state.get_player(PlayerId("P1")).hand = [_card("a")]

    cmds = legal_commands(g)
    assert not any(isinstance(c, PlayLoot) for c in cmds)


def test_play_loot_legal_when_stack_not_empty():
    """Loot plays are instant-speed: legal even with items on the stack."""
    g = _game(Phase.ACTION)
    g.state.get_player(PlayerId("P1")).hand = [_card("a")]
    g.stack.push(controller_id=PlayerId("P1"), source="test", effect=AppendMarkerEffect("x"))

    cmds = legal_commands(g)
    assert any(isinstance(c, PlayLoot) for c in cmds)


def test_play_loot_illegal_when_hand_empty():
    cmds = legal_commands(_game(Phase.ACTION))
    assert not any(isinstance(c, PlayLoot) for c in cmds)


def test_play_loot_allowed_count_respects_extra_quota():
    g = _game(Phase.ACTION)
    card_a, card_b = _card("a"), _card("b")
    g.state.get_player(PlayerId("P1")).hand = [card_a, card_b]
    g.state.turn_flags.loot_plays_allowed = 2  # granted extra play
    g.state.turn_flags.loot_plays_used = 1     # used one already

    cmds = legal_commands(g)
    loot_cmds = [c for c in cmds if isinstance(c, PlayLoot)]
    assert len(loot_cmds) == 2  # still has one play left; all hand cards legal


# ── ActivateCharacterAbility legality ─────────────────────────────────────────

def test_activate_legal_when_character_untapped():
    g = _game(Phase.ACTION)
    g.state.get_player(PlayerId("P1")).character = ItemInPlay(card_ref=_card("char"))

    cmds = legal_commands(g)
    assert ActivateCharacterAbility() in cmds


def test_activate_illegal_when_no_character():
    cmds = legal_commands(_game(Phase.ACTION))
    assert ActivateCharacterAbility() not in cmds


def test_activate_illegal_when_character_tapped():
    g = _game(Phase.ACTION)
    char = ItemInPlay(card_ref=_card("char"))
    char.tap()
    g.state.get_player(PlayerId("P1")).character = char

    cmds = legal_commands(g)
    assert ActivateCharacterAbility() not in cmds


# ── BuyShop legality ──────────────────────────────────────────────────────────

def _make_zones(shop_cards: list[CardRef | None], *, shop_size: int = 3) -> GameZones:
    """Build a minimal GameZones with the given shop slot contents."""
    shop: SlotsZone[CardRef] = SlotsZone(size=shop_size)
    for i, card in enumerate(shop_cards):
        if card is not None:
            shop.set(i, card)
    return GameZones(
        loot_deck=DeckZone(),
        loot_discard=DiscardZone(),
        treasure_deck=DeckZone(),
        treasure_discard=DiscardZone(),
        monster_deck=DeckZone(),
        monster_discard=DiscardZone(),
        shop_slots=shop,
        monster_slots=SlotsZone(size=1),
    )


def _game_with_shop(
    *,
    phase: Phase = Phase.ACTION,
    cents: int = TREASURE_COST,
    shop_cards: list[CardRef | None] | None = None,
    purchase_used: bool = False,
) -> Game:
    if shop_cards is None:
        shop_cards = [_card("t0"), _card("t1"), _card("t2")]
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2, cents=cents)
    gs = GameState.from_players([p1])
    gs.phase = phase
    gs.turn_flags.purchase_used = purchase_used
    g = Game(state=gs, zones=_make_zones(shop_cards))
    return g


def test_buy_legal_in_action_with_enough_cents():
    g = _game_with_shop(cents=TREASURE_COST)
    cmds = legal_commands(g)
    buy_cmds = [c for c in cmds if isinstance(c, BuyShop)]
    assert len(buy_cmds) == 3  # one per occupied slot
    assert BuyShop(slot_index=0) in buy_cmds
    assert BuyShop(slot_index=1) in buy_cmds
    assert BuyShop(slot_index=2) in buy_cmds


def test_buy_illegal_outside_action_phase():
    for phase in (Phase.START, Phase.END):
        g = _game_with_shop(phase=phase)
        cmds = legal_commands(g)
        assert not any(isinstance(c, BuyShop) for c in cmds), \
            f"BuyShop should not be legal in {phase}"


def test_buy_illegal_when_stack_not_empty():
    g = _game_with_shop()
    g.stack.push(controller_id=PlayerId("P1"), source="test", effect=AppendMarkerEffect("x"))
    cmds = legal_commands(g)
    assert not any(isinstance(c, BuyShop) for c in cmds)


def test_buy_illegal_for_empty_slot():
    # Slot 1 is empty, slots 0 and 2 are occupied
    g = _game_with_shop(shop_cards=[_card("t0"), None, _card("t2")])
    cmds = legal_commands(g)
    buy_cmds = [c for c in cmds if isinstance(c, BuyShop)]
    assert BuyShop(slot_index=1) not in buy_cmds
    assert BuyShop(slot_index=0) in buy_cmds
    assert BuyShop(slot_index=2) in buy_cmds


def test_buy_illegal_with_insufficient_cents():
    g = _game_with_shop(cents=TREASURE_COST - 1)
    cmds = legal_commands(g)
    assert not any(isinstance(c, BuyShop) for c in cmds)


def test_buy_illegal_after_purchase_already_used():
    g = _game_with_shop(purchase_used=True)
    cmds = legal_commands(g)
    assert not any(isinstance(c, BuyShop) for c in cmds)


def test_buy_illegal_when_all_slots_empty():
    g = _game_with_shop(shop_cards=[None, None, None])
    cmds = legal_commands(g)
    assert not any(isinstance(c, BuyShop) for c in cmds)
