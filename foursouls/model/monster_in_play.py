from __future__ import annotations

from dataclasses import dataclass

from .refs import CardRef


@dataclass(slots=True)
class MonsterInPlay:
    """Runtime state for a monster occupying a monster slot."""

    card_ref: CardRef
    base_hp: int
    current_hp: int
    evade: int          # minimum roll value needed to hit
    reward_cents: int
    has_soul: bool

    def is_alive(self) -> bool:
        return self.current_hp > 0

    def take_damage(self, amount: int) -> None:
        self.current_hp = max(0, self.current_hp - amount)
