from __future__ import annotations

from dataclasses import dataclass

from .refs import CardRef


class Command:
    kind: str


@dataclass(frozen=True, slots=True)
class PassPriority(Command):
    kind: str = "PASS"


@dataclass(frozen=True, slots=True)
class EndTurn(Command):
    kind: str = "END_TURN"


@dataclass(frozen=True, slots=True)
class PlayLoot(Command):
    card_ref: CardRef
    kind: str = "PLAY_LOOT"


@dataclass(frozen=True, slots=True)
class ActivateCharacterAbility(Command):
    kind: str = "ACTIVATE_CHARACTER_ABILITY"


@dataclass(frozen=True, slots=True)
class BuyShop(Command):
    slot_index: int
    kind: str = "BUY_SHOP"


@dataclass(frozen=True, slots=True)
class AttackMonster(Command):
    slot_index: int
    kind: str = "ATTACK_MONSTER"


@dataclass(frozen=True, slots=True)
class RollCombat(Command):
    kind: str = "ROLL_COMBAT"