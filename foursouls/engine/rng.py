from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import MutableSequence, Optional, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class RNG:
    """
    Seeded random number generator wrapper.

    Engine code should use this instead of `random` directly so tests and
    simulations are deterministic.
    """
    seed: Optional[int] = None
    _r: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self._r = random.Random(self.seed)

    def randint(self, a: int, b: int) -> int:
        return self._r.randint(a, b)

    def shuffle(self, items: MutableSequence[T]) -> None:
        self._r.shuffle(items)

    def choice(self, items: MutableSequence[T]) -> T:
        if not items:
            raise ValueError("Cannot choose from an empty sequence")
        return self._r.choice(items)

    def roll_d6(self) -> int:
        return self.randint(1, 6)