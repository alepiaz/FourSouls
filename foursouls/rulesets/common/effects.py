from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from foursouls.engine.zones import DeckZone, DiscardZone
from foursouls.model.effects import Effect
from foursouls.model.game_state import GameState
from foursouls.model.refs import CardRef, PlayerId

if TYPE_CHECKING:
    from foursouls.engine.log import EventLog


@dataclass(slots=True)
class DrawLoot1Effect:
    """Draw 1 card from the loot deck into the target player's hand."""

    player_id: PlayerId
    loot_deck: DeckZone   # mutable reference; mutated on apply
    log: Optional[EventLog] = field(default=None)

    def validate(self, ctx: GameState) -> bool:
        return not self.loot_deck.empty()

    def apply(self, ctx: GameState) -> None:
        from foursouls.engine.events import CardDrawn
        drawn = self.loot_deck.draw(1)
        ctx.get_player(self.player_id).hand.extend(drawn)
        if self.log is not None:
            for card_ref in drawn:
                self.log.append(CardDrawn(
                    player_id=self.player_id,
                    card_ref=card_ref,
                    source="loot_deck",
                ))


@dataclass(slots=True)
class GainCentsEffect:
    """Player gains a fixed number of cents."""

    player_id: PlayerId
    amount: int

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return True

    def apply(self, ctx: GameState) -> None:
        ctx.get_player(self.player_id).cents += self.amount


@dataclass(slots=True)
class DealDamageEffect:
    """Deal damage to a player, reducing their HP (minimum 0)."""

    player_id: PlayerId
    amount: int
    damage_type: str = "ability"   # "combat" | "ability"

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return True

    def apply(self, ctx: GameState) -> None:
        player = ctx.get_player(self.player_id)
        player.hp = max(0, player.hp - self.amount)


@dataclass(slots=True)
class PlayLootEffect:
    """
    Wrapper that resolves a loot card's inner effect then discards the card.

    If inner.validate() returns False the card remains out-of-zone (limbo).
    No loot card in Sprint 2 is expected to fizzle, so this is acceptable
    until a proper 'card in-play zone' is introduced.
    """

    card_ref: CardRef
    inner: Effect
    loot_discard: DiscardZone
    player_id: Optional[PlayerId] = field(default=None)
    log: Optional[EventLog] = field(default=None)

    def validate(self, ctx: GameState) -> bool:
        return self.inner.validate(ctx)

    def apply(self, ctx: GameState) -> None:
        from foursouls.engine.events import CardDiscarded
        self.inner.apply(ctx)
        self.loot_discard.add(self.card_ref)
        if self.log is not None and self.player_id is not None:
            card_name = str(self.card_ref.card_id or "unknown")
            self.log.append(CardDiscarded(
                player_id=self.player_id,
                card_id=self.card_ref.card_id,
                card_name=card_name,
                zone="loot_discard",
            ))


@dataclass(slots=True)
class EventCardEffect:
    """
    Wrapper for an event card's triggered ability.

    On resolution: apply inner effect (if it validates), then always clear
    the event's monster slot and move the card to monster discard.
    """

    card_ref: CardRef
    slot_index: int
    inner: Effect
    monster_slots: object    # SlotsZone[MonsterInPlay]
    monster_discard: object  # DiscardZone[CardRef]

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return True  # event resolution never cancels

    def apply(self, ctx: GameState) -> None:
        if self.inner.validate(ctx):
            self.inner.apply(ctx)
        self.monster_slots.clear(self.slot_index)
        self.monster_discard.add(self.card_ref)


@dataclass(slots=True)
class GrantExtraLootPlayEffect:
    """Grant the controlling player one additional loot play this turn."""

    player_id: PlayerId

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return True  # cost already paid; cannot fizzle

    def apply(self, ctx: GameState) -> None:
        ctx.turn_flags.loot_plays_allowed += 1
