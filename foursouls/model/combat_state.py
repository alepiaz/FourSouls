from __future__ import annotations

from dataclasses import dataclass

from .refs import CardRef, PlayerId


@dataclass(slots=True)
class CombatState:
    """
    Runtime context for an ongoing combat engagement.

    Created when a player declares an attack; cleared when combat resolves
    (monster death, player death, or turn end).
    """

    attacker_id: PlayerId
    defender_slot: int
    monster_ref: CardRef    # identity of the monster being fought
    is_active: bool = True
    last_combat_roll: int = 0   # most recent d6 result; read by monster trigger callbacks
