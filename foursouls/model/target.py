from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .refs import CardRef, PlayerId


@dataclass(frozen=True, slots=True)
class PlayerTarget:
    player_id: PlayerId


@dataclass(frozen=True, slots=True)
class MonsterTarget:
    slot_index: int


@dataclass(frozen=True, slots=True)
class SoulTarget:
    player_id: PlayerId
    card_ref: CardRef


@dataclass(frozen=True, slots=True)
class StackItemTarget:
    stack_id: int


AnyTarget = Union[
    PlayerTarget,
    MonsterTarget,
    SoulTarget,
    StackItemTarget,
]
