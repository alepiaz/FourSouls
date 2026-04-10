"""
Sprint 6 acceptance test — win condition & game termination.

Scenario
--------
  P1 starts with 3 souls already collected (one kill away from winning).
  A guaranteed-kill soul monster (hp=1, evade=1) is placed in slot 0.
  combat_bot drives the game from ACTION phase until game_over is set.

Assertions
----------
  - game.game_over is True after the winning kill
  - get_legal_actions() returns [] (no moves in a finished game)
  - GameWon event was emitted with P1 as the winner
  - The winning player's soul count equals SOULS_TO_WIN
"""
from __future__ import annotations

import agents.combat_bot as combat_bot
from agents.pass_bot import choose_command as pass_command
from foursouls.cli.app import build_demo_game
from foursouls.engine.events import GameWon
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.combat import SOULS_TO_WIN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _advance_to_action(g) -> None:
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))


# ---------------------------------------------------------------------------
# Acceptance test
# ---------------------------------------------------------------------------

def test_sprint6_combat_bot_wins_at_four_souls():
    """combat_bot reaches 4 souls → game_over, no legal actions, GameWon emitted."""
    g = build_demo_game(["P1", "P2"], seed=0)

    p1 = g.state.get_player(PlayerId("P1"))

    # Pre-load 3 souls so the next soul kill ends the game
    for i in range(SOULS_TO_WIN - 1):
        p1.souls.append(CardRef(InstanceId(f"pre-soul-{i}")))

    # Plant a guaranteed-kill soul monster in slot 0
    g.zones.monster_slots.set(0, MonsterInPlay(
        card_ref=CardRef(InstanceId("boss")),
        base_hp=1,
        current_hp=1,
        evade=1,
        reward_coin=0,
        has_soul=True,
    ))

    _advance_to_action(g)

    all_events = []
    for _ in range(50):
        if g.game_over:
            break
        result = g.step(combat_bot.choose_command(g))
        all_events.extend(result.events)
    else:
        raise AssertionError("Game did not end within the step limit")

    assert g.game_over is True
    assert g.get_legal_actions() == []
    assert any(isinstance(e, GameWon) for e in all_events), "GameWon event not emitted"

    won_events = [e for e in all_events if isinstance(e, GameWon)]
    assert len(won_events) == 1
    assert won_events[0].player_id == PlayerId("P1")
    assert won_events[0].soul_count == SOULS_TO_WIN
    assert len(p1.souls) == SOULS_TO_WIN
