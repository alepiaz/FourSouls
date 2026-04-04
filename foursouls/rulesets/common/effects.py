from __future__ import annotations

from dataclasses import dataclass

from foursouls.engine.zones import DeckZone
from foursouls.model.game_state import GameState
from foursouls.model.refs import CardRef, PlayerId


@dataclass(slots=True)
class DrawLoot1Effect:
    """Draw 1 card from the loot deck into the target player's hand."""

    player_id: PlayerId
    loot_deck: DeckZone  # mutable reference; mutated on apply

    def validate(self, ctx: GameState) -> bool:
        return not self.loot_deck.empty()

    def apply(self, ctx: GameState) -> None:
        drawn = self.loot_deck.draw(1)
        ctx.get_player(self.player_id).hand.extend(drawn)
