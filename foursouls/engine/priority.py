from __future__ import annotations

from dataclasses import dataclass, field

from foursouls.model.refs import PlayerId


@dataclass(slots=True)
class PriorityManager:
    """
    Tracks priority (who can act) and pass cycles (who has passed since last reset).

    - current player starts with priority
    - pass_priority() advances to next player in turn order
    - all_passed() becomes True once every player has passed in the same cycle
    - reset_to(player) sets current to player and clears pass tracking
    """
    player_order: list[PlayerId]
    current_index: int = 0
    passed: set[PlayerId] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.player_order:
            raise ValueError("PriorityManager requires a non-empty player_order")
        if not (0 <= self.current_index < len(self.player_order)):
            raise ValueError("current_index out of range")
        if len(set(self.player_order)) != len(self.player_order):
            raise ValueError("player_order contains duplicates")

    def current(self) -> PlayerId:
        return self.player_order[self.current_index]

    def reset_to(self, player_id: PlayerId) -> None:
        if player_id not in self.player_order:
            raise ValueError("player_id must be in player_order")
        self.current_index = self.player_order.index(player_id)
        self.passed.clear()

    def pass_priority(self) -> None:
        """Mark current player as passed and advance to next player."""
        self.passed.add(self.current())
        self.current_index = (self.current_index + 1) % len(self.player_order)

    def all_passed(self) -> bool:
        return len(self.passed) == len(self.player_order)

    def remaining_to_pass(self) -> set[PlayerId]:
        """Convenience for debugging/tests."""
        return set(self.player_order) - self.passed