"""Target types for effects and abilities."""

from __future__ import annotations

from dataclasses import dataclass

from foursouls.model.refs import PlayerId


@dataclass(frozen=True)
class PlayerTarget:
    """Target a specific player."""

    player_id: PlayerId

    def __str__(self) -> str:
        return f"Player({self.player_id})"


@dataclass(frozen=True)
class MonsterTarget:
    """Target a monster in a specific slot."""

    slot_idx: int

    def __str__(self) -> str:
        return f"Monster(slot={self.slot_idx})"
