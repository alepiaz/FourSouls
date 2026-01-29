from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

from .events import Event


@dataclass(slots=True)
class EventLog:
    """
    Simple in-memory append-only event log.
    """

    events: List[Event] = field(default_factory=list)

    def append(self, event: Event) -> None:
        self.events.append(event)

    def extend(self, new_events: Iterable[Event]) -> None:
        self.events.extend(new_events)

    def clear(self) -> None:
        self.events.clear()

    def __len__(self) -> int:
        return len(self.events)

    def last(self) -> Event | None:
        return self.events[-1] if self.events else None
