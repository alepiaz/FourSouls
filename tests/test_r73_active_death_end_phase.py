"""
R7.3 — Active-player death: cancel combat → drain stack → advance to END phase.

Rules context
-------------
After the four-step death penalty (R7.2), if the dying player is the active player:
  - Any remaining stack items are fizzled (stack drained).
  - Phase advances from ACTION to END.
  - EndTurn becomes legal (and is the only non-Pass action available).
  - All offensive actions (attack, loot play, buy, roll) are illegal in END phase.
  - Issuing EndTurn from END phase advances the turn normally.

Tests also verify that the PhaseChanged(ACTION → END) event is emitted and that
the PhaseChanged(END → START) is logged correctly when EndTurn is finally issued.
"""
from __future__ import annotations

import agents.combat_bot as combat_bot
from agents.pass_bot import choose_command as pass_command
from foursouls.engine.events import PhaseChanged
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import (
    AttackMonster,
    BuyShop,
    EndTurn,
    PassPriority,
    PlayLoot,
    RollCombat,
)
from foursouls.model.game_state import GameState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.legality import legal_commands
from foursouls.rulesets.common.setup import setup_game


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ref(name: str) -> CardRef:
    return CardRef(InstanceId(name))


def _monster_always_miss(hp: int = 5) -> MonsterInPlay:
    """evade=7 → every roll misses → player takes damage."""
    return MonsterInPlay(
        card_ref=_ref("m-0"),
        base_hp=hp,
        current_hp=hp,
        evade=7,
        reward_coin=0,
        has_soul=False,
    )


def _game(*, player_hp: int = 1, n_players: int = 1) -> Game:
    """
    Game in ACTION phase. evade=7, player_hp=1 → active player dies on first roll.
    """
    players = [
        PlayerState(player_id=PlayerId(f"P{i+1}"), max_hp=player_hp, hp=player_hp)
        for i in range(n_players)
    ]
    state = GameState.from_players(players, active_player_id=PlayerId("P1"))
    state.phase = Phase.ACTION

    ms: SlotsZone[MonsterInPlay] = SlotsZone(size=1)
    ms.set(0, _monster_always_miss())

    zones = GameZones(
        loot_deck=DeckZone(),
        loot_discard=DiscardZone(),
        treasure_deck=DeckZone(),
        treasure_discard=DiscardZone(),
        monster_deck=DeckZone(),
        monster_discard=DiscardZone(),
        shop_slots=SlotsZone(size=1),
        monster_slots=ms,
    )
    g = Game(state=state, zones=zones, rng=RNG(seed=0))
    g.step(AttackMonster(slot_index=0))
    return g


def _die(g: Game):
    return g.step(RollCombat())


# ---------------------------------------------------------------------------
# Phase transition
# ---------------------------------------------------------------------------

def test_phase_is_end_after_active_player_death():
    g = _game()
    _die(g)
    assert g.state.phase == Phase.END


def test_phase_changed_event_action_to_end():
    result = _die(_game())
    phase_events = [e for e in result.events if isinstance(e, PhaseChanged)]
    assert any(e.old_phase == Phase.ACTION and e.new_phase == Phase.END
               for e in phase_events)


# ---------------------------------------------------------------------------
# Legal commands in END phase
# ---------------------------------------------------------------------------

def test_end_turn_legal_in_end_phase():
    g = _game()
    _die(g)
    assert EndTurn() in legal_commands(g)


def test_pass_priority_legal_in_end_phase():
    g = _game()
    _die(g)
    assert PassPriority() in legal_commands(g)


def test_attack_illegal_in_end_phase():
    g = _game()
    _die(g)
    cmds = legal_commands(g)
    assert not any(isinstance(c, AttackMonster) for c in cmds)


def test_roll_combat_illegal_in_end_phase():
    g = _game()
    _die(g)
    assert RollCombat() not in legal_commands(g)


def test_play_loot_illegal_in_end_phase():
    g = _game()
    p1 = g.state.get_player(PlayerId("P1"))
    p1.hand.append(_ref("loot-x"))
    _die(g)
    cmds = legal_commands(g)
    assert not any(isinstance(c, PlayLoot) for c in cmds)


def test_buy_shop_illegal_in_end_phase():
    g = _game()
    p1 = g.state.get_player(PlayerId("P1"))
    p1.cents = 100
    g.zones.shop_slots.set(0, _ref("treasure-x"))
    _die(g)
    cmds = legal_commands(g)
    assert not any(isinstance(c, BuyShop) for c in cmds)


# ---------------------------------------------------------------------------
# EndTurn from END phase advances the turn
# ---------------------------------------------------------------------------

def test_end_turn_from_end_phase_advances_turn():
    g = _game(n_players=2)
    _die(g)
    assert g.state.phase == Phase.END

    g.step(EndTurn())

    assert g.state.active_player_id == PlayerId("P2")


def test_phase_changed_end_to_start_on_end_turn():
    g = _game(n_players=2)
    _die(g)

    result = g.step(EndTurn())

    phase_evts = [e for e in result.events if isinstance(e, PhaseChanged)]
    assert any(e.old_phase == Phase.END and e.new_phase == Phase.START
               for e in phase_evts)


def test_turn_number_increments_after_end_phase_end_turn():
    g = _game(n_players=2)
    turn_before = g.state.turn_number
    _die(g)
    g.step(EndTurn())

    # After EndTurn, enter_start_phase runs; pass through START → ACTION
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    assert g.state.turn_number == turn_before + 1


# ---------------------------------------------------------------------------
# Full flow: combat_bot drives active-player death → EndTurn → next turn
# ---------------------------------------------------------------------------

def test_combat_bot_drives_active_death_full_flow():
    """
    setup_game → ACTION → P1 dies (hp=1, evade=7) → END phase →
    combat_bot issues EndTurn → P2 active → P2's turn completes →
    P1's second turn: attack_used=False, hp healed to max.
    """
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=1, hp=1)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=4, hp=4)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))

    monster_cards = [_ref(f"m-{i}") for i in range(4)]
    loot_cards = [_ref(f"loot-{i}") for i in range(20)]
    treasure_cards = [_ref(f"treasure-{i}") for i in range(6)]

    g = setup_game(
        state,
        loot_cards=loot_cards,
        treasure_cards=treasure_cards,
        monster_cards=monster_cards,
        rng=RNG(seed=0),
        monster_slot_count=1,
    )

    # Replace slot 0 with a guaranteed-miss monster
    g.zones.monster_slots.set(0, _monster_always_miss())

    # Advance through START → ACTION
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    # Drive P1's full turn (attack → miss → die → EndTurn from END phase)
    turn_before = g.state.turn_number
    for _ in range(20):
        if g.state.turn_number != turn_before:
            break
        g.step(combat_bot.choose_command(g))
    else:
        raise AssertionError("P1's turn did not end")

    assert g.state.active_player_id == PlayerId("P2")

    # Drive P2's turn with pass_bot
    while g.state.active_player_id == PlayerId("P2"):
        g.step(pass_command(g))

    # P1's second turn: healed to max, attack available
    assert g.state.active_player_id == PlayerId("P1")
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    assert g.state.get_player(PlayerId("P1")).hp == 1   # healed to max_hp=1
    assert not g.state.turn_flags.attack_used
