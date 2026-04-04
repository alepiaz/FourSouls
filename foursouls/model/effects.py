from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .game_state import GameState


@runtime_checkable
class Effect(Protocol):
    """
    An Effect is something that can resolve from the stack and mutate game state.

    validate(): checked at resolution time; if False -> effect fizzles.
    apply(): performs the mutation.
    """
    def validate(self, ctx: GameState) -> bool: ...
    def apply(self, ctx: GameState) -> None: ...


@dataclass(frozen=True, slots=True)
class AppendMarkerEffect:
    marker: str

    def validate(self, ctx: GameState) -> bool:
        return True

    def apply(self, ctx: GameState) -> None:
        ctx.debug_markers.append(self.marker)


@dataclass(frozen=True, slots=True)
class AlwaysFizzleEffect:
    reason: str = "validate_failed"

    def validate(self, ctx: GameState) -> bool:
        return False

    def apply(self, ctx: GameState) -> None:
        raise RuntimeError("AlwaysFizzleEffect.apply() should not be executed")