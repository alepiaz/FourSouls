"""Sprint 13 end-to-end regression tests against real registered cards."""
import pytest

from foursouls.cards.monsters import (
    GAPER, BIG_SPIDER, FLY, HEADLESS_HORSEMAN, CARRION_QUEEN,
    CURSED_CHEST, make_monster_in_play,
)
from foursouls.cli.app import build_demo_game
from foursouls.engine.rng import RNG
from foursouls.model.commands import (
    AttackMonster, AttackMonsterDeck, PlaceRevealedMonster, EndTurn,
    PassPriority, RollCombat,
)
from foursouls.model.phase import Phase
from foursouls.model.refs import CardRef, InstanceId
from foursouls.rulesets.common.effects import DealDamageToMonsterEffect


def _ref(name, card_id):
    return CardRef(InstanceId(name), card_id)


def _game():
    g = build_demo_game(seed=42)
    while g.state.phase != Phase.ACTION or not g.stack.empty():
        g.step(PassPriority())
    return g


def _resolve(g):
    while not g.stack.empty():
        for _ in g.state.turn_order:
            g.step(PassPriority())


@pytest.mark.parametrize("card_id,forced,optional", [(GAPER,1,0),(BIG_SPIDER,0,1)])
def test_real_death_grants_deck_only_attack(monkeypatch, card_id, forced, optional):
    g = _game()
    monkeypatch.setattr(RNG, "roll_d6", lambda self: 6)
    killed = make_monster_in_play(_ref("kill", card_id))
    killed.current_hp = 1
    g.zones.monster_slots.set(0, killed)
    g.step(AttackMonster(0))
    g.step(RollCombat())
    _resolve(g)
    flags = g.state.turn_flags
    assert flags.attack_used
    assert flags.forced_deck_attacks == forced
    assert flags.optional_deck_attacks == optional
    commands = g.legal_commands()
    assert AttackMonsterDeck() in commands
    assert not any(isinstance(c, AttackMonster) for c in commands)
    assert (EndTurn() in commands) == (not forced)
    covered = make_monster_in_play(_ref("covered", FLY))
    g.zones.monster_slots.set(1, covered)
    revealed = _ref("revealed", FLY)
    g.zones.monster_deck.put_on_top(revealed)
    g.step(AttackMonsterDeck())
    assert g.pending_deck_attack == revealed
    assert g.legal_commands() == [PlaceRevealedMonster(0), PlaceRevealedMonster(1)]
    g.step(PlaceRevealedMonster(1))
    assert g.combat.from_deck
    assert EndTurn() not in g.legal_commands()
    assert flags.forced_deck_attacks == flags.optional_deck_attacks == 0
    g.step(RollCombat())
    assert g.zones.monster_slots.get(1) is covered
    assert g.combat is None


def test_revealed_event_uncovers_previous_monster(monkeypatch):
    g = _game()
    covered = make_monster_in_play(_ref("covered-event", FLY))
    g.zones.monster_slots.set(0, covered)
    event = _ref("event", CURSED_CHEST)
    g.zones.monster_deck.put_on_top(event)
    monkeypatch.setattr(RNG, "roll_d6", lambda self: 6)
    g.step(AttackMonsterDeck())
    g.step(PlaceRevealedMonster(0))
    assert g.combat is None
    _resolve(g)
    assert g.zones.monster_slots.get(0) is covered
    assert event in g.zones.monster_discard.cards


def test_horseman_prevents_death_outside_combat():
    g = _game()
    horseman = make_monster_in_play(_ref("horseman", HEADLESS_HORSEMAN))
    g.zones.monster_slots.set(0, horseman)
    for i in range(2):
        g.push_to_stack(controller_id=g.state.active_player_id, source="test",
                        effect=DealDamageToMonsterEffect(0, 3, g.zones.monster_slots))
        _resolve(g)
        if i == 0:
            assert g.zones.monster_slots.get(0) is horseman
            assert horseman.current_hp == 2 and horseman.prevent_death_used
            assert horseman.evade_bonus == 1 and horseman.attack_bonus == -1
        else:
            assert g.zones.monster_slots.get(0) is not horseman


@pytest.mark.parametrize("roll,damage", [(4,0),(5,0),(6,1)])
def test_carrion_queen_real_combat(monkeypatch, roll, damage):
    g = _game()
    queen = make_monster_in_play(_ref("queen", CARRION_QUEEN))
    g.zones.monster_slots.set(0, queen)
    monkeypatch.setattr(RNG, "roll_d6", lambda self: roll)
    g.step(AttackMonster(0))
    g.step(RollCombat())
    assert queen.current_hp == queen.base_hp - damage


def test_gaper_not_triggered_by_non_roll_kill_after_six(monkeypatch):
    g = _game()
    monkeypatch.setattr(RNG, "roll_d6", lambda self: 6)
    monster = make_monster_in_play(_ref("gaper", GAPER))
    g.zones.monster_slots.set(0, monster)
    g.step(AttackMonster(0))
    g.step(RollCombat())
    assert monster.current_hp == 1
    g.push_to_stack(controller_id=g.state.active_player_id, source="test",
                    effect=DealDamageToMonsterEffect(0, 1, g.zones.monster_slots))
    _resolve(g)
    assert g.state.turn_flags.forced_deck_attacks == 0


def test_cover_resets_transient_state(monkeypatch):
    g = _game()
    covered = make_monster_in_play(_ref("covered-horseman", HEADLESS_HORSEMAN))
    covered.current_hp = 1
    covered.prevent_damage = 1
    covered.prevent_death_used = True
    covered.evade_bonus = 1
    covered.attack_bonus = -1
    g.zones.monster_slots.set(0, covered)
    g.zones.monster_deck.put_on_top(_ref("covering-fly", FLY))
    monkeypatch.setattr(RNG, "roll_d6", lambda self: 6)
    g.step(AttackMonsterDeck())
    g.step(PlaceRevealedMonster(0))
    g.step(RollCombat())
    assert g.zones.monster_slots.get(0) is covered
    assert covered.current_hp == covered.base_hp
    assert covered.prevent_damage == covered.evade_bonus == covered.attack_bonus == 0
    assert not covered.prevent_death_used


def test_event_remains_until_its_own_effect_resolves(monkeypatch):
    g = _game()
    covered = make_monster_in_play(_ref("covered-aoe", FLY))
    g.zones.monster_slots.set(0, covered)
    event = _ref("event-aoe", CURSED_CHEST)
    g.zones.monster_deck.put_on_top(event)
    monkeypatch.setattr(RNG, "roll_d6", lambda self: 6)
    g.step(AttackMonsterDeck())
    g.step(PlaceRevealedMonster(0))
    from foursouls.rulesets.common.effects import AoDamageEffect
    g.push_to_stack(controller_id=g.state.active_player_id, source="test",
                    effect=AoDamageEffect(0, g.zones.monster_slots))
    for _ in g.state.turn_order:
        g.step(PassPriority())
    assert g.zones.monster_slots.get(0).card_ref == event
    _resolve(g)
    assert g.zones.monster_slots.get(0) is covered
    assert g.zones.monster_discard.cards.count(event) == 1
