"""
Sprint 2 acceptance tests.

Named tests mirror the acceptance criteria exactly so they serve as a
living spec. The final test is the integration target from the Sprint 2 design:

  active player passes to ACTION → plays a loot → taps character for extra loot
  → plays second loot → ends turn → next player starts with character recharged.
"""
from agents.pass_bot import choose_command
from foursouls.cards.loot import LOOT_COIN_1, LOOT_COIN_2
from foursouls.engine.events import EffectFizzled
from foursouls.engine.rng import RNG
from foursouls.model.commands import (
    ActivateCharacterAbility,
    EndTurn,
    PassPriority,
    PlayLoot,
)
from foursouls.model.effects import AlwaysFizzleEffect
from foursouls.model.game_state import GameState
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.effects import PlayLootEffect
from foursouls.rulesets.common.setup import setup_game


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ref(name: str, card_id: CardId) -> CardRef:
    return CardRef(InstanceId(name), card_id)


def _make_cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _new_game(*, p1_character: bool = False):
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    if p1_character:
        p1.character = ItemInPlay(card_ref=CardRef(InstanceId("char-p1")))
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    return setup_game(
        state,
        loot_cards=_make_cards("loot", 40),
        treasure_cards=_make_cards("treasure", 10),
        monster_cards=_make_cards("monster", 10),
        rng=RNG(seed=1),
    )


def _advance_to_action(g):
    while g.state.phase != Phase.ACTION:
        g.step(choose_command(g))


# ── Acceptance tests ──────────────────────────────────────────────────────────

def test_setup_game_returns_ready_to_play_game():
    """setup_game returns a Game in START phase with Loot1 already on the stack."""
    g = _new_game()
    assert g.state.phase == Phase.START
    assert not g.stack.empty()
    assert g.stack.top().label == "Loot1"
    assert g.state.turn_number == 1
    assert all(
        len(g.state.get_player(pid).hand) == 3
        for pid in g.state.turn_order
    )


def test_play_loot_legal_in_action_phase():
    coin = _ref("coin-1", LOOT_COIN_1)
    g = _new_game()
    g.state.get_player(PlayerId("P1")).hand.append(coin)
    _advance_to_action(g)

    assert PlayLoot(card_ref=coin) in g.legal_commands()


def test_play_loot_illegal_if_no_loot_plays_remaining():
    coin = _ref("coin-2", LOOT_COIN_1)
    g = _new_game()
    g.state.get_player(PlayerId("P1")).hand.append(coin)
    _advance_to_action(g)

    g.state.turn_flags.loot_plays_used = 1  # exhaust default quota

    assert PlayLoot(card_ref=coin) not in g.legal_commands()


def test_character_ability_legal_if_not_tapped():
    g = _new_game(p1_character=True)
    _advance_to_action(g)

    assert ActivateCharacterAbility() in g.legal_commands()


def test_character_ability_illegal_if_tapped():
    g = _new_game(p1_character=True)
    _advance_to_action(g)
    g.state.get_player(PlayerId("P1")).character.tap()

    assert ActivateCharacterAbility() not in g.legal_commands()


def test_activate_character_grants_one_additional_loot_play():
    g = _new_game(p1_character=True)
    _advance_to_action(g)
    assert g.state.turn_flags.loot_plays_allowed == 1

    g.step(ActivateCharacterAbility())
    g.step(PassPriority())
    g.step(PassPriority())  # resolves

    assert g.state.turn_flags.loot_plays_allowed == 2


def test_player_can_play_two_loot_after_character_activation():
    coin1 = _ref("coin-3", LOOT_COIN_1)
    coin2 = _ref("coin-4", LOOT_COIN_2)
    g = _new_game(p1_character=True)
    p1 = g.state.get_player(PlayerId("P1"))
    p1.hand.extend([coin1, coin2])
    _advance_to_action(g)

    g.step(ActivateCharacterAbility())
    g.step(PassPriority())
    g.step(PassPriority())

    g.step(PlayLoot(card_ref=coin1))
    g.step(PassPriority())
    g.step(PassPriority())

    g.step(PlayLoot(card_ref=coin2))
    g.step(PassPriority())
    g.step(PassPriority())

    assert p1.cents == 2
    assert g.state.turn_flags.loot_plays_used == 2


def test_played_loot_goes_to_discard_after_resolution():
    coin = _ref("coin-5", LOOT_COIN_1)
    g = _new_game()
    g.state.get_player(PlayerId("P1")).hand.append(coin)
    _advance_to_action(g)

    g.step(PlayLoot(card_ref=coin))
    assert len(g.zones.loot_discard.cards) == 0  # not discarded yet

    g.step(PassPriority())
    g.step(PassPriority())  # resolves

    assert g.zones.loot_discard.top() == coin


def test_loot_effect_can_fizzle_if_target_invalid():
    """
    PlayLootEffect delegates validate() to its inner effect.
    If inner fizzles (e.g. target no longer valid), EffectFizzled fires
    and the card is NOT discarded.
    """
    coin = _ref("coin-6", LOOT_COIN_1)
    g = _new_game()
    p1 = g.state.get_player(PlayerId("P1"))
    p1.hand.append(coin)
    _advance_to_action(g)

    # Simulate a loot play with an invalid target by injecting a fizzling wrapper
    p1.hand.remove(coin)
    g.state.turn_flags.loot_plays_used += 1
    fizzling = PlayLootEffect(card_ref=coin, inner=AlwaysFizzleEffect(), loot_discard=g.zones.loot_discard)
    g.push_to_stack(controller_id=PlayerId("P1"), source=coin, effect=fizzling, label="PlayLoot:test")
    g.priority.reset_to(PlayerId("P1"))

    g.step(PassPriority())
    events = g.step(PassPriority())

    assert any(isinstance(e, EffectFizzled) for e in events)
    assert len(g.zones.loot_discard.cards) == 0  # card in limbo, not discarded


def test_priority_window_opens_before_loot_resolves():
    """
    After PlayLoot is submitted, the effect sits on the stack.
    EndTurn is blocked and a full pass cycle is required to resolve.
    """
    coin = _ref("coin-7", LOOT_COIN_1)
    g = _new_game()
    g.state.get_player(PlayerId("P1")).hand.append(coin)
    _advance_to_action(g)

    g.step(PlayLoot(card_ref=coin))

    # Stack is occupied — EndTurn blocked
    assert not g.stack.empty()
    assert not any(isinstance(c, EndTurn) for c in g.legal_commands())

    # One pass is not enough
    g.step(PassPriority())
    assert not g.stack.empty()

    # Second pass (all passed) → resolves
    g.step(PassPriority())
    assert g.stack.empty()


def test_recharge_resets_character_for_next_turn():
    """
    P1 taps their character on turn 1. After EndTurn and P2's full turn,
    P1's character is untapped at the start of their next turn.
    """
    g = _new_game(p1_character=True)
    char = g.state.get_player(PlayerId("P1")).character
    _advance_to_action(g)

    g.step(ActivateCharacterAbility())
    g.step(PassPriority())
    g.step(PassPriority())
    assert char.is_tapped

    g.step(EndTurn())

    # P2's turn — P1's character still tapped
    assert char.is_tapped
    while g.state.active_player_id == PlayerId("P2"):
        g.step(choose_command(g))

    # P1's START phase begins → enter_start_phase untaps character
    assert not char.is_tapped


# ── Integration target ────────────────────────────────────────────────────────

def test_sprint2_integration_full_flow():
    """
    Integration target:
      P1 passes through START → ACTION
      plays a loot card (coin → gains 1 cent)
      taps character to gain an extra loot play
      plays second loot card (coin → gains 1 more cent)
      ends turn
      P2 starts with their character (if any) recharged
    """
    coin1 = _ref("int-coin-1", LOOT_COIN_1)
    coin2 = _ref("int-coin-2", LOOT_COIN_2)

    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    p1.character = ItemInPlay(card_ref=CardRef(InstanceId("char-p1")))
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    p2.character = ItemInPlay(card_ref=CardRef(InstanceId("char-p2")))

    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    g = setup_game(
        state,
        loot_cards=_make_cards("loot", 40),
        treasure_cards=_make_cards("treasure", 10),
        monster_cards=_make_cards("monster", 10),
        rng=RNG(seed=42),
    )
    g.state.get_player(PlayerId("P1")).hand.extend([coin1, coin2])

    # ── START phase: Loot1 resolves ──
    assert g.state.phase == Phase.START
    _advance_to_action(g)
    assert g.state.phase == Phase.ACTION

    # ── Play first loot ──
    g.step(PlayLoot(card_ref=coin1))
    g.step(PassPriority())
    g.step(PassPriority())
    assert p1.cents == 1
    assert g.state.turn_flags.loot_plays_used == 1

    # ── Tap character for extra play ──
    g.step(ActivateCharacterAbility())
    g.step(PassPriority())
    g.step(PassPriority())
    assert g.state.turn_flags.loot_plays_allowed == 2
    assert p1.character.is_tapped

    # ── Play second loot ──
    g.step(PlayLoot(card_ref=coin2))
    g.step(PassPriority())
    g.step(PassPriority())
    assert p1.cents == 2
    assert g.state.turn_flags.loot_plays_used == 2

    # ── End turn ──
    g.step(EndTurn())
    assert g.state.active_player_id == PlayerId("P2")
    assert g.state.turn_number == 2
    assert g.state.turn_flags.loot_plays_used == 0
    assert g.state.turn_flags.loot_plays_allowed == 1

    # ── P2 starts with character recharged (P2 never tapped theirs) ──
    assert not p2.character.is_tapped

    # ── P1's character is still tapped (P2's turn, not P1's) ──
    assert p1.character.is_tapped
