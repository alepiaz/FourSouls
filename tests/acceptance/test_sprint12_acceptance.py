"""
Sprint 12 acceptance tests — Character stats and ability window.

R12.1 — Base HP corrected to 2 for all four characters and _DEFAULT.
R12.2 — ActivateCharacterAbility is legal for the priority holder regardless
         of phase or stack state; cost taps the priority holder's character.
R12.3 — Regression: existing ability mechanics still work correctly.
"""
from __future__ import annotations

import pytest

from foursouls.cards.characters import (
    CAIN, EVE, ISAAC, MAGDALENE,
    _DEFAULT,
    get_character_def,
)
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

from agents.pass_bot import choose_command as pass_command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _char(name: str) -> ItemInPlay:
    return ItemInPlay(card_ref=CardRef(InstanceId(name)))


def _make_cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _two_player_game_at_action(*, p1_char: bool = True, p2_char: bool = True) -> Game:
    """Two-player game driven to ACTION phase; both players optionally have characters."""
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=2, hp=2)
    if p1_char:
        p1.character = _char("char-p1")
    if p2_char:
        p2.character = _char("char-p2")
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    g = setup_game(
        state,
        loot_cards=_make_cards("loot", 40),
        treasure_cards=_make_cards("treasure", 10),
        monster_cards=_make_cards("monster", 10),
        rng=RNG(seed=0),
    )
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))
    return g


# ---------------------------------------------------------------------------
# R12.1 — Character stat correction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("card_id", [ISAAC, MAGDALENE, CAIN, EVE])
def test_all_base_characters_have_2hp(card_id):
    defn = get_character_def(card_id)
    assert defn.base_hp == 2, f"{card_id} expected base_hp=2, got {defn.base_hp}"


def test_default_character_has_2hp():
    assert _DEFAULT.base_hp == 2


@pytest.mark.parametrize("card_id", [ISAAC, MAGDALENE, CAIN, EVE])
def test_all_base_characters_have_atk_1(card_id):
    defn = get_character_def(card_id)
    assert defn.attack == 1


# ---------------------------------------------------------------------------
# R12.2 — Ability window: legal regardless of phase / stack state
# ---------------------------------------------------------------------------

def test_ability_legal_in_start_phase():
    """Priority holder's untapped character is legal even in START phase."""
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p1.character = _char("char-p1")
    state = GameState.from_players([p1])
    state.phase = Phase.START
    g = Game(state=state)
    assert ActivateCharacterAbility() in legal_commands(g)


def test_ability_legal_with_non_empty_stack():
    """Priority holder's untapped character is legal even when the stack has items."""
    from foursouls.model.effects import AppendMarkerEffect
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2)
    p1.character = _char("char-p1")
    state = GameState.from_players([p1])
    state.phase = Phase.ACTION
    g = Game(state=state)
    g.stack.push(controller_id=PlayerId("P1"), source="test", effect=AppendMarkerEffect("x"))
    assert ActivateCharacterAbility() in legal_commands(g)


def test_ability_legal_for_non_active_player_during_response():
    """P2 (non-active) can use their own character ability while holding priority."""
    g = _two_player_game_at_action(p1_char=True, p2_char=True)
    # P1 is active and holds priority; P2 doesn't yet.
    # Pass P1's priority so P2 is next.
    g.step(PassPriority())
    assert g.priority.current() == PlayerId("P2")
    assert ActivateCharacterAbility() in legal_commands(g)


def test_ability_illegal_for_player_without_character_when_non_active():
    """Non-active player without a character cannot use ActivateCharacterAbility."""
    g = _two_player_game_at_action(p1_char=True, p2_char=False)
    g.step(PassPriority())  # give priority to P2
    assert g.priority.current() == PlayerId("P2")
    assert ActivateCharacterAbility() not in legal_commands(g)


def test_ability_taps_priority_holders_character_not_active_players():
    """When P2 uses the ability, P2's character is tapped — not P1's."""
    g = _two_player_game_at_action(p1_char=True, p2_char=True)
    p1_char = g.state.get_player(PlayerId("P1")).character
    p2_char = g.state.get_player(PlayerId("P2")).character

    g.step(PassPriority())       # P2 holds priority
    assert g.priority.current() == PlayerId("P2")
    g.step(ActivateCharacterAbility())

    assert p2_char.is_tapped,  "P2's character should be tapped after P2 activates"
    assert not p1_char.is_tapped, "P1's character should be untouched"


def test_off_turn_ability_grants_extra_play_to_controller_not_active_player():
    """P2 tapping on P1's turn grants the extra play to P2, not P1."""
    g = _two_player_game_at_action(p1_char=True, p2_char=True)
    initial_allowed = g.state.turn_flags.loot_plays_allowed

    g.step(PassPriority())               # P2 holds priority
    g.step(ActivateCharacterAbility())   # P2 taps their own character

    g.step(PassPriority())  # P1
    g.step(PassPriority())  # P2 → GrantExtraLootPlay resolves

    # P1's on-turn quota is unchanged
    assert g.state.turn_flags.loot_plays_allowed == initial_allowed
    # P2 received the extra play in their off-turn bucket
    assert g.state.turn_flags.extra_loot_plays.get("P2", 0) == 1


# ---------------------------------------------------------------------------
# R12.3 — Regression: active-player self-use still works identically
# ---------------------------------------------------------------------------

def test_active_player_ability_taps_own_character():
    g = _two_player_game_at_action()
    p1_char = g.state.get_player(PlayerId("P1")).character
    g.step(ActivateCharacterAbility())
    assert p1_char.is_tapped


def test_active_player_ability_grants_extra_loot():
    g = _two_player_game_at_action()
    g.step(ActivateCharacterAbility())
    g.step(PassPriority())
    g.step(PassPriority())
    assert g.state.turn_flags.loot_plays_allowed == 2


def test_ability_cannot_be_used_twice_same_turn_by_same_player():
    """Once tapped, a character cannot activate again the same turn."""
    g = _two_player_game_at_action()
    g.step(ActivateCharacterAbility())
    g.step(PassPriority())
    g.step(PassPriority())  # resolve

    assert ActivateCharacterAbility() not in legal_commands(g)
