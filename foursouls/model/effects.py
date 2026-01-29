from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .effect_context import EffectContext
from .refs import PlayerId


@runtime_checkable
class Effect(Protocol):
    """
    An Effect resolves from the stack and mutates game state.

    validate(): checked at resolution time; if False -> effect fizzles.
    apply(): performs the mutation.
    """

    def validate(self, ctx: EffectContext) -> bool: ...
    def apply(self, ctx: EffectContext) -> None: ...


@dataclass(frozen=True, slots=True)
class AppendMarkerEffect:
    marker: str

    def validate(self, ctx: EffectContext) -> bool:
        return True

    def apply(self, ctx: EffectContext) -> None:
        ctx.state.debug_markers.append(self.marker)


@dataclass(frozen=True, slots=True)
class AlwaysFizzleEffect:
    reason: str = "validate_failed"

    def validate(self, ctx: EffectContext) -> bool:
        return False

    def apply(self, ctx: EffectContext) -> None:
        raise RuntimeError("AlwaysFizzleEffect.apply() should not be executed")


@dataclass(frozen=True, slots=True)
class DrawLootEffect:
    """
    Draw N loot cards into a player's hand.

    If loot deck is empty, reshuffle loot_discard into loot_deck using ctx.rng.
    """

    player_id: PlayerId
    n: int = 1

    def validate(self, ctx: EffectContext) -> bool:
        if self.n < 0:
            return False
        total_available = len(ctx.state.loot_deck) + len(ctx.state.loot_discard)
        return total_available >= self.n

    def apply(self, ctx: EffectContext) -> None:
        if self.n <= 0:
            return

        state = ctx.state

        # If deck can't satisfy draw, reshuffle discard into deck
        if len(state.loot_deck) < self.n:
            if len(state.loot_discard) > 0:
                moved = list(state.loot_discard.cards)
                state.loot_discard.cards.clear()
                state.loot_deck.put_many_on_top(moved)
                state.loot_deck.shuffle(ctx.rng)

        drawn = state.loot_deck.draw(self.n)
        state.get_player(self.player_id).hand.extend(drawn)
