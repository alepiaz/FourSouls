"""
Tests for S2.5: PlayLoot dispatch, GainCentsEffect, DealDamageEffect, discard.
"""
from agents.pass_bot import choose_command
from foursouls.cards.loot import BOMB, LOOT_COIN_1, LOOT_COIN_2
from foursouls.engine.rng import RNG
from foursouls.model.commands import PassPriority, PlayLoot
from foursouls.model.game_state import GameState
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.setup import setup_game


def _ref(name: str, card_id: CardId) -> CardRef:
    return CardRef(InstanceId(name), card_id)


def _make_cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _game_at_action(extra_loot: list[CardRef] = ()):
    """Two-player game at ACTION phase; extra_loot cards are added to P1's hand."""
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    g = setup_game(
        state,
        loot_cards=_make_cards("loot", 40),
        treasure_cards=_make_cards("treasure", 10),
        monster_cards=_make_cards("monster", 10),
        rng=RNG(seed=0),
    )
    while g.state.phase != Phase.ACTION:
        g.step(choose_command(g))
    for card in extra_loot:
        g.state.get_player(PlayerId("P1")).hand.append(card)
    return g


# ── GainCentsEffect ───────────────────────────────────────────────────────────

def test_play_coin_grants_one_cent():
    coin = _ref("coin-a", LOOT_COIN_1)
    g = _game_at_action(extra_loot=[coin])
    p1 = g.state.get_player(PlayerId("P1"))
    assert p1.cents == 0

    g.step(PlayLoot(card_ref=coin))
    g.step(PassPriority())  # P1
    g.step(PassPriority())  # P2 → resolves

    assert p1.cents == 1


def test_play_coin_2_and_coin_3_are_both_one_cent():
    from foursouls.cards.loot import LOOT_COIN_2, LOOT_COIN_3
    for card_id in (LOOT_COIN_2, LOOT_COIN_3):
        coin = _ref("coin-x", card_id)
        g = _game_at_action(extra_loot=[coin])
        p1 = g.state.get_player(PlayerId("P1"))
        g.step(PlayLoot(card_ref=coin))
        g.step(PassPriority())
        g.step(PassPriority())
        assert p1.cents == 1


# ── DealDamageEffect ──────────────────────────────────────────────────────────

def test_play_bomb_deals_one_damage_to_controller():
    bomb = _ref("bomb-a", BOMB)
    g = _game_at_action(extra_loot=[bomb])
    p1 = g.state.get_player(PlayerId("P1"))
    assert p1.hp == 3

    g.step(PlayLoot(card_ref=bomb))
    g.step(PassPriority())
    g.step(PassPriority())

    assert p1.hp == 2


def test_bomb_damage_clamped_at_zero():
    bomb = _ref("bomb-b", BOMB)
    g = _game_at_action(extra_loot=[bomb])
    p1 = g.state.get_player(PlayerId("P1"))
    p1.hp = 1

    g.step(PlayLoot(card_ref=bomb))
    g.step(PassPriority())
    g.step(PassPriority())

    assert p1.hp == 0


# ── Hand / discard mechanics ──────────────────────────────────────────────────

def test_card_removed_from_hand_on_play():
    coin = _ref("coin-c", LOOT_COIN_1)
    g = _game_at_action(extra_loot=[coin])
    p1 = g.state.get_player(PlayerId("P1"))
    assert coin in p1.hand

    g.step(PlayLoot(card_ref=coin))

    assert coin not in p1.hand  # removed immediately when played


def test_card_appears_in_loot_discard_after_resolution():
    coin = _ref("coin-d", LOOT_COIN_1)
    g = _game_at_action(extra_loot=[coin])
    discard_before = len(g.zones.loot_discard.cards)

    g.step(PlayLoot(card_ref=coin))
    # not yet discarded — still on stack
    assert len(g.zones.loot_discard.cards) == discard_before

    g.step(PassPriority())
    g.step(PassPriority())  # resolves → discarded

    assert len(g.zones.loot_discard.cards) == discard_before + 1
    assert g.zones.loot_discard.top() == coin


# ── Quota tracking ────────────────────────────────────────────────────────────

def test_loot_plays_used_increments_on_play():
    coin = _ref("coin-e", LOOT_COIN_1)
    g = _game_at_action(extra_loot=[coin])
    assert g.state.turn_flags.loot_plays_used == 0

    g.step(PlayLoot(card_ref=coin))

    assert g.state.turn_flags.loot_plays_used == 1


def test_second_play_illegal_after_quota_exhausted():
    coin1 = _ref("coin-f1", LOOT_COIN_1)
    coin2 = _ref("coin-f2", LOOT_COIN_2)
    g = _game_at_action(extra_loot=[coin1, coin2])

    g.step(PlayLoot(card_ref=coin1))
    g.step(PassPriority())
    g.step(PassPriority())  # resolves; loot_plays_used == 1 == allowed

    cmds = g.legal_commands()
    assert not any(isinstance(c, PlayLoot) for c in cmds)


def test_second_play_legal_after_extra_quota_granted(monkeypatch):
    """With loot_plays_allowed == 2, a second PlayLoot is legal."""
    coin1 = _ref("coin-g1", LOOT_COIN_1)
    coin2 = _ref("coin-g2", LOOT_COIN_2)
    g = _game_at_action(extra_loot=[coin1, coin2])
    g.state.turn_flags.loot_plays_allowed = 2

    g.step(PlayLoot(card_ref=coin1))
    g.step(PassPriority())
    g.step(PassPriority())  # resolves; used == 1 < allowed == 2

    cmds = g.legal_commands()
    assert PlayLoot(card_ref=coin2) in cmds
