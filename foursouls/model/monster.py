"""Monster state and combat models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MonsterState:
    """Represents a single monster on the board."""

    name: str
    hp: int
    max_hp: int

    def is_alive(self) -> bool:
        """Check if monster is still alive."""
        return self.hp > 0

    def take_damage(self, amount: int) -> None:
        """Apply damage to the monster."""
        self.hp = max(0, self.hp - amount)

    def heal(self, amount: int) -> None:
        """Heal the monster."""
        self.hp = min(self.max_hp, self.hp + amount)

    def __str__(self) -> str:
        return f"{self.name} [{self.hp}/{self.max_hp}]"
