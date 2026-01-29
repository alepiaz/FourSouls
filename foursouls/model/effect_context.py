from __future__ import annotations

from dataclasses import dataclass

from foursouls.engine.rng import RNG
from .game_state import GameState


@dataclass(slots=True)
class EffectContext:
    state: GameState
    rng: RNG
