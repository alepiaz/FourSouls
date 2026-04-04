from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Iterable, List, Optional, TypeVar

from foursouls.engine.rng import RNG

T = TypeVar("T")


class ZoneEmptyError(Exception):
    pass


@dataclass(slots=True)
class DeckZone(Generic[T]):
    """
    A top-down deck. Index -1 is the top (so pop() draws from top).
    """
    cards: List[T] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cards)

    def empty(self) -> bool:
        return not self.cards

    def shuffle(self, rng: RNG) -> None:
        rng.shuffle(self.cards)

    def peek(self) -> T:
        if not self.cards:
            raise ZoneEmptyError("Deck is empty")
        return self.cards[-1]

    def draw(self, n: int = 1) -> List[T]:
        if n < 0:
            raise ValueError("n must be >= 0")
        if n == 0:
            return []
        if n > len(self.cards):
            raise ZoneEmptyError("Not enough cards to draw")
        drawn: List[T] = []
        for _ in range(n):
            drawn.append(self.cards.pop())
        return drawn

    def put_on_top(self, card: T) -> None:
        self.cards.append(card)

    def put_many_on_top(self, cards: Iterable[T]) -> None:
        self.cards.extend(cards)

    def put_on_bottom(self, card: T) -> None:
        self.cards.insert(0, card)

    def put_many_on_bottom(self, cards: Iterable[T]) -> None:
        self.cards = list(cards) + self.cards


@dataclass(slots=True)
class DiscardZone(Generic[T]):
    cards: List[T] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cards)

    def empty(self) -> bool:
        return not self.cards

    def add(self, card: T) -> None:
        self.cards.append(card)

    def extend(self, cards: Iterable[T]) -> None:
        self.cards.extend(cards)

    def top(self) -> T:
        if not self.cards:
            raise ZoneEmptyError("Discard is empty")
        return self.cards[-1]


@dataclass(slots=True)
class HandZone(Generic[T]):
    cards: List[T] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cards)

    def add(self, card: T) -> None:
        self.cards.append(card)

    def extend(self, cards: Iterable[T]) -> None:
        self.cards.extend(cards)

    def remove(self, card: T) -> None:
        self.cards.remove(card)

    def contains(self, card: T) -> bool:
        return card in self.cards


@dataclass(slots=True)
class SlotsZone(Generic[T]):
    """
    Fixed-size face-up slots (e.g., shop slots, monster slots).
    """
    size: int
    slots: List[Optional[T]] = field(init=False)

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError("SlotsZone size must be > 0")
        self.slots = [None for _ in range(self.size)]

    def __len__(self) -> int:
        return self.size

    def get(self, idx: int) -> Optional[T]:
        self._check_idx(idx)
        return self.slots[idx]

    def set(self, idx: int, card: Optional[T]) -> None:
        self._check_idx(idx)
        self.slots[idx] = card

    def clear(self, idx: int) -> None:
        self.set(idx, None)

    def empty_indices(self) -> List[int]:
        return [i for i, c in enumerate(self.slots) if c is None]

    def filled_indices(self) -> List[int]:
        return [i for i, c in enumerate(self.slots) if c is not None]

    def _check_idx(self, idx: int) -> None:
        if not (0 <= idx < self.size):
            raise IndexError(f"Slot index out of range: {idx}")