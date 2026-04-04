"""
Tests for S2.4: ActivateCharacterAbility command + GrantExtraLootPlayEffect.
"""
from agents.pass_bot import choose_command
from foursouls.engine.game_loop import Game
from foursouls.engine.rng import RNG
from foursouls.model.commands import ActivateCharacterAbility, PassPriority
from foursouls.model.game_state import GameState
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.legality import legal_commands
from foursouls.rulesets.common.setup import setup_game


def _make_cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _char(name: str) -> ItemInPlay:
    return ItemInPlay(card_ref=CardRef(InstanceId(name)))


def _game_at_action(*, with_character: bool = True):
    """Return a game already in ACTION phase; P1 optionally has a character."""
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    if with_character:
        p1.character = _char("char-p1")
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    g = setup_game(
        state,
        loot_cards=_make_cards("loot", 40),
        treasure_cards=_make_cards("treasure", 10),
        monster_cards=_make_cards("monster", 10),
        rng=RNG(seed=0),
    )
    # Drive through START phase → ACTION
    while g.state.phase != Phase.ACTION:
        g.step(choose_command(g))
    return g


# ── Legality ──────────────────────────────────────────────────────────────────

def test_activate_legal_when_character_untapped():
    g = _game_at_action(with_character=True)
    assert ActivateCharacterAbility() in legal_commands(g)


def test_activate_illegal_when_no_character():
    g = _game_at_action(with_character=False)
    assert ActivateCharacterAbility() not in legal_commands(g)


def test_activate_illegal_when_character_already_tapped():
    g = _game_at_action(with_character=True)
    g.state.get_player(PlayerId("P1")).character.tap()
    assert ActivateCharacterAbility() not in legal_commands(g)


def test_activate_illegal_outside_action_phase():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    p1.character = _char("char-p1")
    state = GameState.from_players([p1])
    state.phase = Phase.START
    g = Game(state=state)
    assert ActivateCharacterAbility() not in legal_commands(g)


# ── Activation mechanics ──────────────────────────────────────────────────────

def test_activate_taps_character_immediately():
    g = _game_at_action(with_character=True)
    char = g.state.get_player(PlayerId("P1")).character
    assert not char.is_tapped

    g.step(ActivateCharacterAbility())

    assert char.is_tapped  # cost paid on activation, not resolution


def test_activate_pushes_grant_effect_to_stack():
    g = _game_at_action(with_character=True)
    g.step(ActivateCharacterAbility())

    assert not g.stack.empty()
    assert g.stack.top().label == "GrantExtraLootPlay"
    assert g.stack.top().controller_id == PlayerId("P1")


def test_activate_quota_increases_after_resolution():
    g = _game_at_action(with_character=True)
    assert g.state.turn_flags.loot_plays_allowed == 1

    g.step(ActivateCharacterAbility())

    # Resolve through the normal pass cycle
    g.step(PassPriority())  # P1
    g.step(PassPriority())  # P2 → GrantExtraLootPlay resolves

    assert g.state.turn_flags.loot_plays_allowed == 2
    assert g.stack.empty()


def test_activate_not_legal_again_after_tapping():
    """Once tapped, ActivateCharacterAbility must not appear in legal commands."""
    g = _game_at_action(with_character=True)
    g.step(ActivateCharacterAbility())

    # Resolve effect
    g.step(PassPriority())
    g.step(PassPriority())

    assert ActivateCharacterAbility() not in legal_commands(g)


def test_activate_then_extra_loot_play_becomes_legal():
    """After activation resolves, PlayLoot should be legal for a second card."""
    from foursouls.model.commands import PlayLoot
    g = _game_at_action(with_character=True)

    # Use the first loot play quota immediately (mark it used)
    g.state.turn_flags.loot_plays_used = 1
    # Now quota is exhausted: PlayLoot should be illegal
    assert not any(isinstance(c, PlayLoot) for c in legal_commands(g))

    # Activate character ability to grant +1
    g.step(ActivateCharacterAbility())
    g.step(PassPriority())
    g.step(PassPriority())  # resolves → loot_plays_allowed == 2

    assert g.state.turn_flags.loot_plays_allowed == 2
    # If P1 has cards in hand, PlayLoot should be legal again
    if g.state.get_player(PlayerId("P1")).hand:
        assert any(isinstance(c, PlayLoot) for c in legal_commands(g))
