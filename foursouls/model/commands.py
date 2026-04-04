from __future__ import annotations

from dataclasses import dataclass


class Command:
    kind: str


@dataclass(frozen=True, slots=True)
class PassPriority(Command):
    kind: str = "PASS"


@dataclass(frozen=True, slots=True)
class EndTurn(Command):
    kind: str = "END_TURN"