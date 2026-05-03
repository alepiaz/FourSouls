"""
Release 4.1 — AttackMonster legality tests.

Legality matrix:
- legal in ACTION, stack empty, slot occupied, attack_used=False
- one AttackMonster per occupied slot (multiple slots → multiple commands)
- illegal outside ACTION phase
- illegal when stack is not empty
- illegal for an empty monster slot
- illegal when attack_used is True
- attack_used becomes True after dispatching AttackMonster
- attack_used resets to False on EndTurn
"""
from __future__ import annotations


from foursouls.cards.monsters import make_monster_in_play
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import AttackMonster, EndTurn
from foursouls.model.effects import AppendMarkerEffect
from foursouls.model.game_state import GameState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.legality import legal_commands


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _monster(name: str) -> MonsterInPlay:
    return make_monster_in_play(CardRef(InstanceId(name)))


def _make_zones(monsters: list[MonsterInPlay | None]) -> GameZones:
    ms: SlotsZone[MonsterInPlay] = SlotsZone(size=len(monsters))
    for i, m in enumerate(monsters):
        if m is not None:
            ms.set(i, m)
    return GameZones(
        loot_deck=DeckZone(),
        loot_discard=DiscardZone(),
        treasure_deck=DeckZone(),
        treasure_discard=DiscardZone(),
        monster_deck=DeckZone(),
        monster_discard=DiscardZone(),
        shop_slots=SlotsZone(size=1),
        monster_slots=ms,
    )


def _game(
    phase: Phase = Phase.ACTION,
    *,
    monsters: list[MonsterInPlay | None] | None = None,
    attack_used: bool = False,
) -> Game:
    if monsters is None:
        monsters = [_monster("m-0")]
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    gs = GameState.from_players([p1])
    gs.phase = phase
    gs.turn_flags.attack_used = attack_used
    g = Game(state=gs, zones=_make_zones(monsters))
    return g


# ---------------------------------------------------------------------------
# Positive cases
# ---------------------------------------------------------------------------

def test_attack_legal_in_action_occupied_slot():
    g = _game()
    cmds = legal_commands(g)
    assert AttackMonster(slot_index=0) in cmds


def test_one_attack_command_per_occupied_slot():
    g = _game(monsters=[_monster("m-0"), _monster("m-1")])
    attack_cmds = [c for c in legal_commands(g) if isinstance(c, AttackMonster)]
    assert len(attack_cmds) == 2
    assert AttackMonster(slot_index=0) in attack_cmds
    assert AttackMonster(slot_index=1) in attack_cmds


def test_only_occupied_slots_produce_attack_commands():
    # slot 0 occupied, slot 1 empty
    g = _game(monsters=[_monster("m-0"), None])
    attack_cmds = [c for c in legal_commands(g) if isinstance(c, AttackMonster)]
    assert len(attack_cmds) == 1
    assert AttackMonster(slot_index=0) in attack_cmds
    assert AttackMonster(slot_index=1) not in attack_cmds


# ---------------------------------------------------------------------------
# Negative cases
# ---------------------------------------------------------------------------

def test_attack_illegal_in_start_phase():
    g = _game(phase=Phase.START)
    assert not any(isinstance(c, AttackMonster) for c in legal_commands(g))


def test_attack_illegal_in_end_phase():
    g = _game(phase=Phase.END)
    assert not any(isinstance(c, AttackMonster) for c in legal_commands(g))


def test_attack_illegal_when_stack_not_empty():
    g = _game()
    g.stack.push(controller_id=PlayerId("P1"), source="test", effect=AppendMarkerEffect("x"))
    assert not any(isinstance(c, AttackMonster) for c in legal_commands(g))


def test_attack_illegal_for_empty_slot():
    g = _game(monsters=[None])
    assert not any(isinstance(c, AttackMonster) for c in legal_commands(g))


def test_attack_illegal_when_attack_used():
    g = _game(attack_used=True)
    assert not any(isinstance(c, AttackMonster) for c in legal_commands(g))


def test_attack_illegal_when_no_zones():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    gs = GameState.from_players([p1])
    gs.phase = Phase.ACTION
    g = Game(state=gs)  # zones=None
    assert not any(isinstance(c, AttackMonster) for c in legal_commands(g))


# ---------------------------------------------------------------------------
# Dispatch: attack_used flag
# ---------------------------------------------------------------------------

def test_dispatching_attack_sets_attack_used():
    g = _game()
    g.step(AttackMonster(slot_index=0))
    assert g.state.turn_flags.attack_used is True


def test_cannot_attack_twice_same_turn():
    g = _game()
    g.step(AttackMonster(slot_index=0))
    assert not any(isinstance(c, AttackMonster) for c in legal_commands(g))


def test_attack_used_resets_on_end_turn():
    g = _game()
    g.step(AttackMonster(slot_index=0))
    assert g.state.turn_flags.attack_used

    g.step(EndTurn())

    assert not g.state.turn_flags.attack_used
