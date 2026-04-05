"""
Release 4.2 — Enter combat state tests.

Covers:
- attack declaration creates CombatState with correct attacker and slot
- CombatState monster_ref matches the monster in the targeted slot
- attack_used is True after declaration
- attack cannot be declared again while combat is active
- no unrelated state mutates on combat entry (hp, hand, cents, phase, shop)
- CombatEntered event is emitted
- priority resets to attacker after combat entry
- combat is None after EndTurn
"""
from __future__ import annotations

from foursouls.cards.monsters import FLY, GAPER, make_monster_in_play
from foursouls.engine.events import CombatEntered
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import AttackMonster, EndTurn
from foursouls.model.game_state import GameState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.legality import legal_commands


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _monster(name: str, card_id=FLY) -> MonsterInPlay:
    return make_monster_in_play(CardRef(InstanceId(name), card_id))


def _make_zones(monsters: list[MonsterInPlay | None]) -> GameZones:
    ms: SlotsZone[MonsterInPlay] = SlotsZone(size=max(len(monsters), 1))
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
    monsters: list[MonsterInPlay | None] | None = None,
    *,
    n_players: int = 1,
) -> Game:
    if monsters is None:
        monsters = [_monster("m-0")]
    players = [
        PlayerState(player_id=PlayerId(f"P{i+1}"), max_hp=3, hp=3)
        for i in range(n_players)
    ]
    gs = GameState.from_players(players, active_player_id=PlayerId("P1"))
    gs.phase = Phase.ACTION
    return Game(state=gs, zones=_make_zones(monsters))


# ---------------------------------------------------------------------------
# CombatState structure
# ---------------------------------------------------------------------------

def test_attack_creates_combat_state():
    g = _game()
    assert g.combat is None
    g.step(AttackMonster(slot_index=0))
    assert g.combat is not None


def test_combat_attacker_id_is_active_player():
    g = _game()
    g.step(AttackMonster(slot_index=0))
    assert g.combat.attacker_id == PlayerId("P1")


def test_combat_defender_slot_matches_command():
    m0 = _monster("m-0")
    m1 = _monster("m-1", GAPER)
    g = _game(monsters=[m0, m1])
    g.step(AttackMonster(slot_index=1))
    assert g.combat.defender_slot == 1


def test_combat_monster_ref_matches_slot_content():
    m = _monster("m-0")
    g = _game(monsters=[m])
    g.step(AttackMonster(slot_index=0))
    assert g.combat.monster_ref == m.card_ref


def test_combat_is_active_on_entry():
    g = _game()
    g.step(AttackMonster(slot_index=0))
    assert g.combat.is_active is True


# ---------------------------------------------------------------------------
# Attack quota
# ---------------------------------------------------------------------------

def test_attack_sets_attack_used():
    g = _game()
    g.step(AttackMonster(slot_index=0))
    assert g.state.turn_flags.attack_used is True


def test_second_attack_illegal_while_combat_active():
    g = _game(monsters=[_monster("m-0"), _monster("m-1")])
    g.step(AttackMonster(slot_index=0))
    # combat is active AND attack_used — both guards block it
    assert not any(isinstance(c, AttackMonster) for c in legal_commands(g))


def test_attack_illegal_combat_active_even_if_attack_not_consumed():
    """If combat is somehow active without attack_used, still illegal."""
    from foursouls.model.combat_state import CombatState
    g = _game(monsters=[_monster("m-0"), _monster("m-1")])
    # Manually inject combat without consuming attack
    g.combat = CombatState(
        attacker_id=PlayerId("P1"),
        defender_slot=0,
        monster_ref=g.zones.monster_slots.get(0).card_ref,
    )
    assert not any(isinstance(c, AttackMonster) for c in legal_commands(g))


# ---------------------------------------------------------------------------
# Event log
# ---------------------------------------------------------------------------

def test_combat_entered_event_emitted():
    g = _game()
    events = g.step(AttackMonster(slot_index=0))
    combat_events = [e for e in events if isinstance(e, CombatEntered)]
    assert len(combat_events) == 1


def test_combat_entered_event_has_correct_fields():
    g = _game()
    events = g.step(AttackMonster(slot_index=0))
    ev = next(e for e in events if isinstance(e, CombatEntered))
    assert ev.attacker_id == PlayerId("P1")
    assert ev.defender_slot == 0


# ---------------------------------------------------------------------------
# Priority
# ---------------------------------------------------------------------------

def test_priority_resets_to_attacker_after_combat_entry():
    g = _game(n_players=2)
    g.step(AttackMonster(slot_index=0))
    assert g.priority.current() == PlayerId("P1")


# ---------------------------------------------------------------------------
# No unrelated state mutates
# ---------------------------------------------------------------------------

def test_combat_entry_does_not_change_phase():
    g = _game()
    g.step(AttackMonster(slot_index=0))
    assert g.state.phase == Phase.ACTION


def test_combat_entry_does_not_change_player_hp():
    g = _game()
    hp_before = g.state.get_player(PlayerId("P1")).hp
    g.step(AttackMonster(slot_index=0))
    assert g.state.get_player(PlayerId("P1")).hp == hp_before


def test_combat_entry_does_not_change_player_cents():
    g = _game()
    g.state.get_player(PlayerId("P1")).cents = 7
    g.step(AttackMonster(slot_index=0))
    assert g.state.get_player(PlayerId("P1")).cents == 7


def test_combat_entry_does_not_mutate_monster_hp():
    m = _monster("m-0")
    hp_before = m.current_hp
    g = _game(monsters=[m])
    g.step(AttackMonster(slot_index=0))
    assert g.zones.monster_slots.get(0).current_hp == hp_before


def test_combat_entry_does_not_mutate_other_flags():
    g = _game()
    g.state.turn_flags.purchase_used = False
    g.state.turn_flags.loot_plays_used = 0
    g.step(AttackMonster(slot_index=0))
    assert g.state.turn_flags.purchase_used is False
    assert g.state.turn_flags.loot_plays_used == 0


# ---------------------------------------------------------------------------
# Combat cleared on EndTurn
# ---------------------------------------------------------------------------

def test_combat_cleared_after_end_turn():
    from foursouls.engine.rng import RNG
    from foursouls.model.refs import CardRef, InstanceId
    from foursouls.rulesets.common.setup import setup_game

    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    gs = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))

    loot = [CardRef(InstanceId(f"loot-{i}")) for i in range(20)]
    treasure = [CardRef(InstanceId(f"treasure-{i}")) for i in range(10)]
    monsters = [CardRef(InstanceId(f"monster-{i}")) for i in range(10)]

    g = setup_game(gs, loot_cards=loot, treasure_cards=treasure,
                   monster_cards=monsters, rng=RNG(seed=0))

    # Advance to ACTION
    from agents.pass_bot import choose_command
    while g.state.phase != Phase.ACTION:
        g.step(choose_command(g))

    g.step(AttackMonster(slot_index=0))
    assert g.combat is not None

    g.step(EndTurn())
    assert g.combat is None
