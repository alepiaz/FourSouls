from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from foursouls.model.refs import PlayerId


@dataclass(frozen=True, slots=True)
class StackItem:
    """
    A single item on the stack.

    - stack_id: unique identifier for this item
    - controller_id: who controls this stack item (for later rules / ownership)
    - source: where it came from (card ref, ability ref, etc.) - opaque for now
    - effect: what will happen on resolution
    - label: human-readable label for debugging
    - targets: list of target objects (e.g., player IDs, card IDs) for this ability/effect
    - metadata: arbitrary dict for storing additional state (e.g., "x_value", "revealed_card")
    """

    stack_id: int
    controller_id: PlayerId
    source: Any
    effect: Any
    label: str = ""
    targets: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


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

    def push(
        self,
        *,
        controller_id: PlayerId,
        source: Any,
        effect: Any,
        label: str = "",
        targets: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StackItem:
        item = StackItem(
            stack_id=self._next_id,
            controller_id=controller_id,
            source=source,
            effect=effect,
            label=label,
            targets=targets or [],
            metadata=metadata or {},
        )
        self._next_id += 1
        self._items.append(item)
        return item

    def pop(self) -> StackItem:
        if not self._items:
            raise IndexError("Cannot pop from an empty stack")
        return self._items.pop()


class StackResolver:
    """
    Manages deterministic resolution of stack items with interrupt windows.

    Handles:
    - resolve_next(): pops top item and resolves it
    - push_interrupt(): allows players to push responses before a resolution
    - nested resolves: if an effect pushes new items, they resolve LIFO
    """

    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.interrupt_window_open = False

    def push_interrupt(
        self,
        controller_id: PlayerId,
        source: Any,
        effect: Any,
        label: str = "",
        targets: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StackItem:
        """
        Push a new item to the stack during an interrupt window.
        This is typically called when a player responds to a pending effect.
        """
        if not self.interrupt_window_open:
            raise RuntimeError("Cannot push interrupt: no interrupt window open")

        return self.stack.push(
            controller_id=controller_id,
            source=source,
            effect=effect,
            label=label,
            targets=targets,
            metadata=metadata,
        )

    def resolve_next(self) -> Optional[StackItem]:
        """
        Pop and return the next item to be resolved.
        The caller is responsible for calling effect.validate() and effect.apply().

        Returns None if stack is empty.
        """
        if self.stack.empty():
            return None

        return self.stack.pop()

    def open_interrupt_window(self) -> None:
        """Open the interrupt window before resolving the next stack item."""
        self.interrupt_window_open = True

    def close_interrupt_window(self) -> None:
        """Close the interrupt window after all responses have been made."""
        self.interrupt_window_open = False

    def has_pending_items(self) -> bool:
        """Check if there are items waiting to resolve."""
        return not self.stack.empty()
