"""
Sprint 3 acceptance tests.

Named tests mirror the acceptance criteria so they serve as a living spec.
The final test is the integration target from the Sprint 3 design doc:

  setup_game → reach ACTION → gain enough cents (loot coin) → BuyShop
  → verify slot refill → verify treasure ownership → EndTurn
  → next player starts with fresh purchase availability
  → next player ends turn → P1 starts again with purchase available
"""
from __future__ import annotations


import agents.economy_bot as economy_bot
from agents.pass_bot import choose_command
from foursouls.cards.loot import LOOT_COIN
from foursouls.engine.rng import RNG
from foursouls.model.commands import BuyShop, EndTurn, PassPriority, PlayLoot
from foursouls.model.game_state import GameState
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.legality import TREASURE_COST
from foursouls.rulesets.common.setup import setup_game


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coin(name: str) -> CardRef:
    return CardRef(InstanceId(name), LOOT_COIN)


def _make_treasure_cards(n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"treasure-{i}")) for i in range(n)]


def _make_loot_cards(n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"loot-{i}")) for i in range(n)]


def _make_monster_cards(n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"monster-{i}")) for i in range(n)]


def _new_game(*, starting_cents: int = 0, p1_coins: int = 0):
    """
    Two-player game via setup_game. P1 optionally starts with cents and
    extra loot coins in hand (appended after the dealt starting hand).
    """
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3, cents=starting_cents)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    g = setup_game(
        state,
        loot_cards=_make_loot_cards(40),
        treasure_cards=_make_treasure_cards(15),
        monster_cards=_make_monster_cards(10),
        rng=RNG(seed=42),
    )
    for i in range(p1_coins):
        g.state.get_player(PlayerId("P1")).hand.append(_coin(f"coin-extra-{i}"))
    return g


def _advance_to_action(g) -> None:
    while g.state.phase != Phase.ACTION:
        g.step(choose_command(g))


def _resolve_stack(g) -> None:
    """Pass until stack is empty (2 passes for a 2-player game)."""
    g.step(PassPriority())
    g.step(PassPriority())


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------

def test_buy_legal_once_player_has_enough_cents():
    """BuyShop appears in legal commands only after player accumulates enough cents."""
    g = _new_game(starting_cents=TREASURE_COST - 1, p1_coins=1)
    _advance_to_action(g)

    # Not enough yet
    assert not any(isinstance(c, BuyShop) for c in g.legal_commands())

    # Play a coin to reach TREASURE_COST
    coin = next(c for c in g.state.get_player(PlayerId("P1")).hand if c.card_id == LOOT_COIN)
    g.step(PlayLoot(card_ref=coin))
    _resolve_stack(g)

    assert g.state.get_player(PlayerId("P1")).cents == TREASURE_COST
    assert any(isinstance(c, BuyShop) for c in g.legal_commands())


def test_cannot_buy_twice_same_turn():
    """After one purchase, BuyShop disappears from legal commands for the rest of the turn."""
    g = _new_game(starting_cents=TREASURE_COST * 3)
    _advance_to_action(g)

    occupied = g.zones.shop_slots.filled_indices()
    g.step(BuyShop(slot_index=occupied[0]))

    assert not any(isinstance(c, BuyShop) for c in g.legal_commands())


def test_buy_removes_treasure_from_shop():
    """The bought slot no longer holds the original card after purchase."""
    g = _new_game(starting_cents=TREASURE_COST)
    _advance_to_action(g)

    slot = g.zones.shop_slots.filled_indices()[0]
    original_card = g.zones.shop_slots.get(slot)

    g.step(BuyShop(slot_index=slot))

    assert original_card not in [g.zones.shop_slots.get(i) for i in range(g.zones.shop_slots.size)]
    p1 = g.state.get_player(PlayerId("P1"))
    assert any(i.card_ref == original_card for i in p1.treasures)


def test_buy_refills_slot_from_deck():
    """After a purchase, the emptied slot is refilled when the treasure deck is non-empty."""
    g = _new_game(starting_cents=TREASURE_COST)
    _advance_to_action(g)

    slot = g.zones.shop_slots.filled_indices()[0]
    assert len(g.zones.treasure_deck) > 0  # precondition

    g.step(BuyShop(slot_index=slot))

    assert g.zones.shop_slots.is_occupied(slot)


def test_buy_leaves_slot_empty_when_deck_exhausted():
    """When the treasure deck runs out, the bought slot stays empty."""
    # Give enough treasure for shop fill (2) but nothing left over for refill
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3, cents=TREASURE_COST)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    g = setup_game(
        state,
        loot_cards=_make_loot_cards(40),
        treasure_cards=_make_treasure_cards(2),   # exactly fills 2 slots, deck empty after
        monster_cards=_make_monster_cards(10),
        rng=RNG(seed=0),
    )
    assert g.zones.treasure_deck.empty()  # precondition: deck exhausted by setup
    _advance_to_action(g)

    slot = g.zones.shop_slots.filled_indices()[0]
    g.step(BuyShop(slot_index=slot))

    assert g.zones.shop_slots.is_empty(slot)


def test_end_turn_after_buy_resets_purchase_flag():
    """After EndTurn, purchase_used is False for the new active player."""
    g = _new_game(starting_cents=TREASURE_COST)
    _advance_to_action(g)

    g.step(BuyShop(slot_index=g.zones.shop_slots.filled_indices()[0]))
    assert g.state.turn_flags.purchase_used

    g.step(EndTurn())

    assert g.state.active_player_id == PlayerId("P2")
    assert not g.state.turn_flags.purchase_used


def test_end_turn_after_buy_still_heals_and_advances():
    """EndTurn after a purchase still performs all normal turn-end cleanup."""
    g = _new_game(starting_cents=TREASURE_COST)
    p1 = g.state.get_player(PlayerId("P1"))
    p1.hp = 1  # damage before end of turn
    _advance_to_action(g)

    g.step(BuyShop(slot_index=g.zones.shop_slots.filled_indices()[0]))
    old_turn = g.state.turn_number

    g.step(EndTurn())

    assert p1.hp == p1.max_hp                          # healed
    assert g.state.active_player_id == PlayerId("P2")  # advanced
    assert g.state.turn_number == old_turn + 1          # incremented
    assert g.state.turn_flags.loot_plays_used == 0      # flags reset


def test_p1_can_buy_again_on_second_turn():
    """P1's purchase allowance is available again when their second turn starts."""
    g = _new_game(starting_cents=TREASURE_COST * 2)
    _advance_to_action(g)

    # P1 buys on turn 1
    g.step(BuyShop(slot_index=g.zones.shop_slots.filled_indices()[0]))
    g.step(EndTurn())

    # P2's full turn (pass-bot)
    while g.state.active_player_id == PlayerId("P2"):
        g.step(choose_command(g))

    # P1's second turn
    assert g.state.active_player_id == PlayerId("P1")
    _advance_to_action(g)

    assert not g.state.turn_flags.purchase_used
    assert any(isinstance(c, BuyShop) for c in g.legal_commands())


def test_loot_and_buy_coexist_in_same_turn():
    """A player can play a loot card and buy a treasure in the same ACTION phase."""
    coin = _coin("coin-A")
    g = _new_game(starting_cents=TREASURE_COST - 1)  # 1 cent short
    g.state.get_player(PlayerId("P1")).hand.append(coin)
    _advance_to_action(g)

    # Not enough cents yet
    assert not any(isinstance(c, BuyShop) for c in g.legal_commands())

    # Play coin → now have enough
    g.step(PlayLoot(card_ref=coin))
    _resolve_stack(g)
    assert g.state.get_player(PlayerId("P1")).cents == TREASURE_COST

    # Buy is now legal and works
    slot = g.zones.shop_slots.filled_indices()[0]
    g.step(BuyShop(slot_index=slot))

    assert g.state.turn_flags.purchase_used
    assert len(g.state.get_player(PlayerId("P1")).treasures) == 1


def test_buy_does_not_interfere_with_remaining_loot_plays():
    """Buying does not consume or affect the loot play quota."""
    coin = _coin("coin-B")
    g = _new_game(starting_cents=TREASURE_COST)
    g.state.get_player(PlayerId("P1")).hand.append(coin)
    _advance_to_action(g)

    flags_before = g.state.turn_flags.loot_plays_used

    g.step(BuyShop(slot_index=g.zones.shop_slots.filled_indices()[0]))

    assert g.state.turn_flags.loot_plays_used == flags_before  # quota untouched
    # Can still play loot after buying
    assert PlayLoot(card_ref=coin) in g.legal_commands()


# ---------------------------------------------------------------------------
# Integration target
# ---------------------------------------------------------------------------

def test_sprint3_integration_full_flow():
    """
    Integration target:
      setup_game() with seeded RNG
      P1 passes through START → ACTION
      P1 has 9 starting cents; plays one loot coin → reaches 10 cents
      P1 buys from shop slot 0
        → cents deducted (0 cents remaining)
        → treasure moves to P1's area
        → slot refills from treasure deck
      P1 cannot buy again this turn
      P1 ends turn
        → purchase_used resets
        → P2 becomes active
      P2 passes through their turn (pass-bot)
      P1 starts second turn
        → can buy again (has 0 cents so BuyShop is not in legal_commands,
          but purchase_used is False — limit is financial, not mechanical)
    """
    coin = _coin("int-coin")

    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3, cents=TREASURE_COST - 1)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    g = setup_game(
        state,
        loot_cards=_make_loot_cards(40),
        treasure_cards=_make_treasure_cards(15),
        monster_cards=_make_monster_cards(10),
        rng=RNG(seed=7),
    )
    g.state.get_player(PlayerId("P1")).hand.append(coin)
    deck_size_after_setup = len(g.zones.treasure_deck)

    # ── START phase: Loot1 resolves ──
    assert g.state.phase == Phase.START
    _advance_to_action(g)
    assert g.state.phase == Phase.ACTION
    assert g.state.get_player(PlayerId("P1")).cents == TREASURE_COST - 1

    # ── Play coin: gain 1 cent → now at TREASURE_COST ──
    g.step(PlayLoot(card_ref=coin))
    _resolve_stack(g)
    assert g.state.get_player(PlayerId("P1")).cents == TREASURE_COST
    assert g.state.turn_flags.loot_plays_used == 1

    # ── Buy from slot 0 ──
    slot = 0
    shop_card_before = g.zones.shop_slots.get(slot)
    assert shop_card_before is not None

    g.step(BuyShop(slot_index=slot))

    assert g.state.get_player(PlayerId("P1")).cents == 0
    assert any(i.card_ref == shop_card_before for i in g.state.get_player(PlayerId("P1")).treasures)
    assert shop_card_before not in [g.zones.shop_slots.get(i) for i in range(2)]
    assert g.zones.shop_slots.is_occupied(slot)                        # refilled
    assert len(g.zones.treasure_deck) == deck_size_after_setup - 1     # one drawn for refill
    assert g.state.turn_flags.purchase_used

    # ── Cannot buy again ──
    assert not any(isinstance(c, BuyShop) for c in g.legal_commands())

    # ── End turn ──
    g.step(EndTurn())
    assert g.state.active_player_id == PlayerId("P2")
    assert g.state.turn_number == 2
    assert not g.state.turn_flags.purchase_used

    # ── P2's full turn (pass-bot) ──
    while g.state.active_player_id == PlayerId("P2"):
        g.step(choose_command(g))

    # ── P1's second turn ──
    assert g.state.active_player_id == PlayerId("P1")
    assert g.state.turn_number == 3
    assert not g.state.turn_flags.purchase_used  # fresh for P1's second turn


# ---------------------------------------------------------------------------
# Acceptance slice — economy_bot driven
# ---------------------------------------------------------------------------

def test_sprint3_acceptance_economy_bot():
    """
    Sprint 3 acceptance slice.

    The economy_bot drives P1 through a complete shop turn without any
    scripted step() calls. The test only asserts observable outcomes.

    Setup:
      P1: TREASURE_COST - 1 starting cents, one LOOT_COIN in hand
      P2: 0 cents, no special cards
      Treasure deck: 15 cards (shop fills 3, 12 remain for refill)

    Expected bot behaviour on P1's turn:
      passes through START (Loot1 resolves)
      advances to ACTION
      plays the coin (card_id present → bot plays it, gains 1 cent → total = TREASURE_COST)
      buys from the first available shop slot
      ends turn (nothing left to do)

    Assertions (outcomes, not steps):
      P1 owns exactly 1 treasure
      P1 has 0 cents
      bought slot is occupied (refilled)
      treasure deck shrank by 1 (one drawn for refill)
      P2 is now active with purchase_used = False
    """
    coin = _coin("bot-coin")

    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3, cents=TREASURE_COST - 1)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    g = setup_game(
        state,
        loot_cards=_make_loot_cards(40),
        treasure_cards=_make_treasure_cards(15),
        monster_cards=_make_monster_cards(10),
        rng=RNG(seed=13),
    )
    g.state.get_player(PlayerId("P1")).hand.append(coin)
    deck_size_after_setup = len(g.zones.treasure_deck)

    # Drive P1's entire turn with the economy bot
    MAX_STEPS = 50
    for _ in range(MAX_STEPS):
        if g.state.active_player_id != PlayerId("P1"):
            break
        g.step(economy_bot.choose_command(g))
    else:
        raise AssertionError("economy_bot did not finish P1's turn within step limit")

    # P1 outcome assertions
    assert len(g.state.get_player(PlayerId("P1")).treasures) == 1
    assert g.state.get_player(PlayerId("P1")).cents == 0

    # Shop integrity
    filled = g.zones.shop_slots.filled_indices()
    assert len(filled) == 2                                               # all 2 slots occupied
    assert len(g.zones.treasure_deck) == deck_size_after_setup - 1       # one refill draw

    # Turn advanced correctly
    assert g.state.active_player_id == PlayerId("P2")
    assert g.state.turn_number == 2
    assert not g.state.turn_flags.purchase_used
