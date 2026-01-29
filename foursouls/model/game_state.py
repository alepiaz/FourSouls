from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.monster import MonsterState
from .player_state import PlayerState
from .refs import CardRef, PlayerId
from .turn_state import TurnState


@dataclass(slots=True)
class GameState:
    players: Dict[PlayerId, PlayerState]
    turn_order: List[PlayerId]
    active_player_id: PlayerId

    # New: minimal global zones for Sprint 1
    loot_deck: DeckZone[CardRef] = field(default_factory=DeckZone)
    loot_discard: DiscardZone[CardRef] = field(default_factory=DiscardZone)

    # Monster board (Sprint 2)
    monster_slots: SlotsZone[MonsterState] = field(
        default_factory=lambda: SlotsZone(size=1)
    )

    # Turn/phase tracking
    turn: TurnState = field(default_factory=TurnState)

    # Useful for early kernel tests/effects
    debug_markers: List[str] = field(default_factory=list)

    @classmethod
    def from_players(
        cls,
        players: List[PlayerState],
        *,
        active_player_id: Optional[PlayerId] = None,
        loot_deck: Optional[DeckZone[CardRef]] = None,
        loot_discard: Optional[DiscardZone[CardRef]] = None,
    ) -> "GameState":
        if not players:
            raise ValueError("GameState requires at least one player")

        players_map = {p.player_id: p for p in players}
        if len(players_map) != len(players):
            raise ValueError("Duplicate player_id in players list")

        order = [p.player_id for p in players]
        active = active_player_id or order[0]
        if active not in players_map:
            raise ValueError("active_player_id must be one of the provided players")

        return cls(
            players=players_map,
            turn_order=order,
            active_player_id=active,
            loot_deck=loot_deck or DeckZone(),
            loot_discard=loot_discard or DiscardZone(),
        )

    def get_player(self, player_id: PlayerId) -> PlayerState:
        try:
            return self.players[player_id]
        except KeyError as e:
            raise KeyError(f"Unknown player_id: {player_id}") from e

    def next_player_id(self, player_id: PlayerId) -> PlayerId:
        idx = self.turn_order.index(player_id)
        return self.turn_order[(idx + 1) % len(self.turn_order)]
