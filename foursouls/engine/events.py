from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from foursouls.model.refs import PlayerId


@dataclass(frozen=True, slots=True)
class Event:
    """
    Base event. Keep events immutable.
    """

    name: str


@dataclass(frozen=True, slots=True)
class PriorityPassed(Event):
    player_id: PlayerId

    def __init__(self, player_id: PlayerId):
        object.__setattr__(self, "name", "PriorityPassed")
        object.__setattr__(self, "player_id", player_id)


@dataclass(frozen=True, slots=True)
class WindowEnded(Event):
    reason: str = "stack_empty_and_all_passed"

    def __init__(self, reason: str = "stack_empty_and_all_passed"):
        object.__setattr__(self, "name", "WindowEnded")
        object.__setattr__(self, "reason", reason)


@dataclass(frozen=True, slots=True)
class StackItemPushed(Event):
    stack_id: int
    controller_id: PlayerId
    label: str = ""

    def __init__(self, stack_id: int, controller_id: PlayerId, label: str = ""):
        object.__setattr__(self, "name", "StackItemPushed")
        object.__setattr__(self, "stack_id", stack_id)
        object.__setattr__(self, "controller_id", controller_id)
        object.__setattr__(self, "label", label)


@dataclass(frozen=True, slots=True)
class StackItemResolved(Event):
    stack_id: int
    label: str = ""

    def __init__(self, stack_id: int, label: str = ""):
        object.__setattr__(self, "name", "StackItemResolved")
        object.__setattr__(self, "stack_id", stack_id)
        object.__setattr__(self, "label", label)


@dataclass(frozen=True, slots=True)
class EffectFizzled(Event):
    stack_id: int
    reason: str = "validate_failed"
    label: str = ""

    def __init__(self, stack_id: int, reason: str = "validate_failed", label: str = ""):
        object.__setattr__(self, "name", "EffectFizzled")
        object.__setattr__(self, "stack_id", stack_id)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "label", label)


@dataclass(frozen=True, slots=True)
class DebugEvent(Event):
    payload: Any

    def __init__(self, payload: Any):
        object.__setattr__(self, "name", "DebugEvent")
        object.__setattr__(self, "payload", payload)
