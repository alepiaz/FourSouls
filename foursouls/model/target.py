from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .refs import PlayerId


@dataclass(frozen=True, slots=True)
class PlayerTarget:
    player_id: PlayerId


@dataclass(frozen=True, slots=True)
class MonsterTarget:
    slot_index: int


AnyTarget = Union[PlayerTarget, MonsterTarget]
