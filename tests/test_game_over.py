"""
R6.2 — game_over flag
R6.3 — game_over triggered by soul win condition

R6.2: When game.game_over is True:
- legal_commands() returns []
- get_legal_actions() returns []
- game.step() raises ValueError for any command

R6.3: When a player kills their 4th soul monster:
- GameWon event is emitted
- game.game_over is set to True
"""
from __future__ import annotations

from foursouls.engine.events import GameWon
from foursouls.engine.rng import RNG
from foursouls.model.commands import AttackMonster, PassPriority, RollCombat
from foursouls.model.game_state import GameState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.combat import SOULS_TO_WIN
from foursouls.rulesets.common.setup import setup_game


def _make_cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _game():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=4, hp=4)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=4, hp=4)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    return setup_game(
        state,
        loot_cards=_make_cards("loot", 20),
        treasure_cards=_make_cards("treasure", 10),
        monster_cards=_make_cards("monster", 10),
        rng=RNG(seed=0),
    )


def test_game_over_empties_legal_commands():
    g = _game()
    assert len(g.legal_commands()) > 0  # sanity: game has legal moves

    g.game_over = True
    assert g.legal_commands() == []


def test_game_over_empties_get_legal_actions():
    g = _game()
    g.game_over = True
    assert g.get_legal_actions() == []


def test_game_over_rejects_any_step():
    g = _game()
    g.game_over = True

    try:
        g.step(PassPriority())
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# R6.3 — win condition sets game_over
# ---------------------------------------------------------------------------

def _game_at_action():
    """Game in ACTION phase with P1 as active player."""
    g = _game()
    g.step(PassPriority())  # P1 passes
    g.step(PassPriority())  # P2 passes → Loot1 resolves → ACTION
    return g


def test_killing_4th_soul_sets_game_over():
    """Killing the 4th soul monster emits GameWon and sets game.game_over."""
    g = _game_at_action()
    p1 = g.state.get_player(PlayerId("P1"))

    # Pre-load 3 souls so the next kill wins
    for i in range(SOULS_TO_WIN - 1):
        p1.souls.append(CardRef(InstanceId(f"soul-{i}")))

    # Place a guaranteed-kill soul monster in slot 0 (hp=1, evade=1 → always hit)
    g.zones.monster_slots.set(0, MonsterInPlay(
        card_ref=CardRef(InstanceId("boss")),
        base_hp=1,
        current_hp=1,
        evade=1,
        reward_coin=0,
        has_soul=True,
    ))

    result = g.step(AttackMonster(slot_index=0))
    result = g.step(RollCombat())  # evade=1, always hits → monster dies

    assert game_won_in(result), "GameWon not emitted"
    assert g.game_over is True


def test_killing_non_winning_soul_does_not_set_game_over():
    """Killing a soul monster when below the threshold does not end the game."""
    g = _game_at_action()

    # No pre-loaded souls — first kill gives 1 soul, not enough to win
    g.zones.monster_slots.set(0, MonsterInPlay(
        card_ref=CardRef(InstanceId("boss")),
        base_hp=1,
        current_hp=1,
        evade=1,
        reward_coin=0,
        has_soul=True,
    ))

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

    assert g.game_over is False
    assert len(g.state.get_player(PlayerId("P1")).souls) == 1


def test_killing_non_soul_monster_never_sets_game_over():
    """Killing a monster without has_soul never triggers game_over."""
    g = _game_at_action()
    p1 = g.state.get_player(PlayerId("P1"))
    for i in range(SOULS_TO_WIN - 1):
        p1.souls.append(CardRef(InstanceId(f"soul-{i}")))

    # Non-soul monster — killing it should not win even with 3 existing souls
    g.zones.monster_slots.set(0, MonsterInPlay(
        card_ref=CardRef(InstanceId("fly")),
        base_hp=1,
        current_hp=1,
        evade=1,
        reward_coin=0,
        has_soul=False,
    ))

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())

    assert g.game_over is False


def game_won_in(result) -> bool:
    return any(isinstance(e, GameWon) for e in result.events)
