"""Tests for targets and monsters (Issue 2.2)"""

import pytest

from foursouls.model.monster import MonsterState
from foursouls.model.refs import PlayerId
from foursouls.model.targets import MonsterTarget, PlayerTarget


class TestPlayerTarget:
    """Test PlayerTarget"""

    def test_player_target_creation(self):
        """Test creating a PlayerTarget"""
        target = PlayerTarget(player_id=PlayerId("P1"))

        assert target.player_id == PlayerId("P1")

    def test_player_target_string(self):
        """Test string representation"""
        target = PlayerTarget(player_id=PlayerId("P2"))
        assert str(target) == "Player(P2)"

    def test_player_target_equality(self):
        """Test PlayerTarget equality"""
        t1 = PlayerTarget(PlayerId("P1"))
        t2 = PlayerTarget(PlayerId("P1"))
        t3 = PlayerTarget(PlayerId("P2"))

        assert t1 == t2
        assert t1 != t3

    def test_player_target_hashable(self):
        """Test that PlayerTarget can be used in sets/dicts"""
        t1 = PlayerTarget(PlayerId("P1"))
        t2 = PlayerTarget(PlayerId("P1"))

        targets = {t1, t2}
        assert len(targets) == 1


class TestMonsterTarget:
    """Test MonsterTarget"""

    def test_monster_target_creation(self):
        """Test creating a MonsterTarget"""
        target = MonsterTarget(slot_idx=0)

        assert target.slot_idx == 0

    def test_monster_target_string(self):
        """Test string representation"""
        target = MonsterTarget(slot_idx=2)
        assert str(target) == "Monster(slot=2)"

    def test_monster_target_equality(self):
        """Test MonsterTarget equality"""
        t1 = MonsterTarget(0)
        t2 = MonsterTarget(0)
        t3 = MonsterTarget(1)

        assert t1 == t2
        assert t1 != t3

    def test_monster_target_hashable(self):
        """Test that MonsterTarget can be used in sets/dicts"""
        t1 = MonsterTarget(0)
        t2 = MonsterTarget(0)

        targets = {t1, t2}
        assert len(targets) == 1


class TestMonsterState:
    """Test MonsterState model"""

    def test_monster_creation(self):
        """Test creating a MonsterState"""
        monster = MonsterState(name="DINGLE", hp=2, max_hp=2)

        assert monster.name == "DINGLE"
        assert monster.hp == 2
        assert monster.max_hp == 2

    def test_monster_is_alive(self):
        """Test is_alive check"""
        monster = MonsterState(name="DINGLE", hp=2, max_hp=2)

        assert monster.is_alive()

        monster.hp = 0
        assert not monster.is_alive()

        monster.hp = -5
        assert not monster.is_alive()

    def test_monster_take_damage(self):
        """Test taking damage"""
        monster = MonsterState(name="DINGLE", hp=2, max_hp=2)

        monster.take_damage(1)
        assert monster.hp == 1
        assert monster.is_alive()

        monster.take_damage(1)
        assert monster.hp == 0
        assert not monster.is_alive()

        # Damage beyond 0 should not go negative
        monster.take_damage(5)
        assert monster.hp == 0

    def test_monster_heal(self):
        """Test healing"""
        monster = MonsterState(name="DINGLE", hp=1, max_hp=2)

        monster.heal(1)
        assert monster.hp == 2

        # Can't heal beyond max_hp
        monster.heal(5)
        assert monster.hp == 2

    def test_monster_string(self):
        """Test string representation"""
        monster = MonsterState(name="DINGLE", hp=1, max_hp=2)
        assert str(monster) == "DINGLE [1/2]"

    def test_monster_zero_damage_monster(self):
        """Test a monster that starts with 0 HP"""
        monster = MonsterState(name="DEAD", hp=0, max_hp=5)
        assert not monster.is_alive()

    def test_monster_high_hp_monster(self):
        """Test a monster with high HP"""
        monster = MonsterState(name="BOSS", hp=50, max_hp=50)
        assert monster.is_alive()

        monster.take_damage(25)
        assert monster.hp == 25
        assert monster.is_alive()

        monster.take_damage(25)
        assert monster.hp == 0
        assert not monster.is_alive()
