from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from foursouls.model.effects import Effect
from foursouls.model.refs import PlayerId


@dataclass(frozen=True, slots=True)
class StackItem:
    """
    A single item on the stack.

    - controller_id: who controls this stack item (for later rules / ownership)
    - source: where it came from (card ref, ability ref, etc.) - opaque for now
    - effect: what will happen on resolution
    """
    stack_id: int
    controller_id: PlayerId
    source: object
    effect: Effect
    label: str = ""


class Stack:
    def __init__(self) -> None:
        self._items: list[StackItem] = []
        self._next_id: int = 1

    def __len__(self) -> int:
        return len(self._items)

    def empty(self) -> bool:
        return not self._items

    def top(self) -> Optional[StackItem]:
        return self._items[-1] if self._items else None

    def push(self, *, controller_id: PlayerId, source: object, effect: Effect, label: str = "") -> StackItem:
        item = StackItem(
            stack_id=self._next_id,
            controller_id=controller_id,
            source=source,
            effect=effect,
            label=label,
        )
        self._next_id += 1
        self._items.append(item)
        return item

    def pop(self) -> StackItem:
        if not self._items:
            raise IndexError("Cannot pop from an empty stack")
        return self._items.pop()

    def contains(self, stack_id: int) -> bool:
        """Return True if an item with this stack_id is still on the stack."""
        return any(item.stack_id == stack_id for item in self._items)

    def remove(self, stack_id: int) -> Optional[StackItem]:
        """Remove and return the item with this stack_id; return None if not found."""
        for i, item in enumerate(self._items):
            if item.stack_id == stack_id:
                return self._items.pop(i)
        return None