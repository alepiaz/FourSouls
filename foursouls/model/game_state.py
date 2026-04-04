from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .phase import Phase, TurnFlags
from .player_state import PlayerState
from .refs import PlayerId


@dataclass(slots=True)
class GameState:
    players: Dict[PlayerId, PlayerState]
    turn_order: List[PlayerId]
    active_player_id: PlayerId

    phase: Phase = Phase.START
    turn_number: int = 1
    turn_flags: TurnFlags = field(default_factory=TurnFlags)
    debug_markers: List[str] = field(default_factory=list)

    @classmethod
    def from_players(cls, players: List[PlayerState], *, active_player_id: Optional[PlayerId] = None) -> "GameState":
        if not players:
            raise ValueError("GameState requires at least one player")

        players_map = {p.player_id: p for p in players}
        if len(players_map) != len(players):
            raise ValueError("Duplicate player_id in players list")

        order = [p.player_id for p in players]
        active = active_player_id or order[0]
        if active not in players_map:
            raise ValueError("active_player_id must be one of the provided players")

        return cls(players=players_map, turn_order=order, active_player_id=active)

    def get_player(self, player_id: PlayerId) -> PlayerState:
        try:
            return self.players[player_id]
        except KeyError as e:
            raise KeyError(f"Unknown player_id: {player_id}") from e

    def next_player_id(self, player_id: PlayerId) -> PlayerId:
        idx = self.turn_order.index(player_id)
        return self.turn_order[(idx + 1) % len(self.turn_order)]

    def reset_for_new_turn(self, active_player_id: PlayerId) -> None:
        if active_player_id not in self.players:
            raise ValueError("active_player_id must be one of the players")
        self.active_player_id = active_player_id
        self.phase = Phase.START
        self.turn_number += 1
        self.turn_flags.reset()