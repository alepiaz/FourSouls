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
    has_soul: bool
    reward_coin: int = 0
    attack: int = 1           # damage dealt to attacker on miss
    reward_loot: int = 0      # loot cards drawn by attacker on kill (e.g. Spider)
    reward_treasure: int = 0  # treasure cards drawn by attacker on kill (e.g. Headless Horseman)
    is_boss: bool = False
    is_event: bool = False

    def is_alive(self) -> bool:
        return self.current_hp > 0

    def take_damage(self, amount: int) -> None:
        self.current_hp = max(0, self.current_hp - amount)
