"""R13.6/R13.7 acceptance tests using the published card definitions."""
import pytest

from foursouls.cards.monsters import BONY, MEGA_FATTY, get_monster_def, make_monster_in_play
from foursouls.cli.app import build_demo_game
from foursouls.engine.rng import RNG
from foursouls.model.commands import AttackMonster, EndTurn, PassPriority, RollCombat
from foursouls.model.phase import Phase
from foursouls.model.refs import CardRef, InstanceId
from foursouls.rulesets.common.effects import CombatMissDamageEffect


def _setup(card_id, monkeypatch, roll):
    g = build_demo_game(seed=42)
    while g.state.phase != Phase.ACTION or not g.stack.empty():
        g.step(PassPriority())
    player = g.state.get_player(g.state.active_player_id)
    player.hp = player.max_hp = 20
    m = make_monster_in_play(CardRef(InstanceId("new-monster"), card_id))
    g.zones.monster_slots.set(0, m)
    monkeypatch.setattr(RNG, "roll_d6", lambda self: roll)
    g.step(AttackMonster(0))
    return g, player, m


def _resolve_one(g):
    for _ in g.state.turn_order:
        g.step(PassPriority())


def _resolve(g):
    while not g.stack.empty():
        _resolve_one(g)


@pytest.mark.parametrize("card,hp,loot,soul", [(BONY,2,1,False),(MEGA_FATTY,3,2,True)])
def test_printed_stats(card,hp,loot,soul):
    m = get_monster_def(card)
    assert (m.base_hp,m.evade,m.attack,m.reward_loot,m.has_soul,m.is_boss) == (hp,3,1,loot,soul,soul)


def test_bony_stacks_bonuses_and_resets(monkeypatch):
    g,p,m = _setup(BONY,monkeypatch,1)
    g.step(RollCombat())
    assert m.attack_bonus == 0
    _resolve_one(g)
    assert m.attack_bonus == 2
    assert isinstance(g.stack.top().effect, CombatMissDamageEffect)
    assert g.stack.top().effect.amount == 1
    _resolve(g)
    g.step(RollCombat())
    _resolve(g)
    assert m.attack_bonus == 4
    assert p.hp == 16
    g.step(EndTurn())
    assert m.attack_bonus == 0


def test_bony_other_roll_no_bonus(monkeypatch):
    g,p,m = _setup(BONY,monkeypatch,2)
    g.step(RollCombat())
    _resolve(g)
    assert m.attack_bonus == 0 and p.hp == 19


def test_mega_fatty_heals_only_after_damage_resolves(monkeypatch):
    g,p,m = _setup(MEGA_FATTY,monkeypatch,2)
    m.current_hp = 1
    g.step(RollCombat())
    assert m.current_hp == 1
    _resolve_one(g)
    assert p.hp == 19 and m.current_hp == 1
    assert g.stack.top().label == "MonsterHeal"
    _resolve(g)
    assert m.current_hp == 2
    g.step(RollCombat())
    _resolve(g)
    g.step(RollCombat())
    _resolve(g)
    assert m.current_hp == 3


def test_mega_fatty_no_heal_if_fully_prevented(monkeypatch):
    g,p,m = _setup(MEGA_FATTY,monkeypatch,2)
    m.current_hp = 1
    p.prevent_damage = 1
    g.step(RollCombat())
    _resolve(g)
    assert p.hp == 20 and m.current_hp == 1


def test_mega_fatty_lethal_damage_still_heals(monkeypatch):
    g,p,m = _setup(MEGA_FATTY,monkeypatch,2)
    p.hp = 1
    m.current_hp = 1
    g.step(RollCombat())
    _resolve(g)
    assert p.hp == 0 and m.current_hp == 2


def test_mega_fatty_no_heal_on_player_hit(monkeypatch):
    g,p,m = _setup(MEGA_FATTY,monkeypatch,6)
    g.step(RollCombat())
    _resolve(g)
    assert m.current_hp == 2 and p.hp == 20
