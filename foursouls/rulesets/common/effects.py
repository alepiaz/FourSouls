from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, TYPE_CHECKING, Optional

from foursouls.engine.zones import DeckZone, DiscardZone
from foursouls.model.effects import Effect
from foursouls.model.game_state import GameState
from foursouls.model.refs import CardRef, InstanceId, PlayerId

if TYPE_CHECKING:
    from foursouls.engine.log import EventLog
    from foursouls.engine.stack import Stack
    from foursouls.model.combat_state import CombatState


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
        amount = self.amount
        if player.damage_cap > 0:
            amount = min(amount, player.damage_cap)
        absorbed = min(player.prevent_damage, amount)
        player.prevent_damage = max(0, player.prevent_damage - amount)
        player.hp = max(0, player.hp - (amount - absorbed))


@dataclass(slots=True)
class DealDamageToMonsterEffect:
    """Deal damage to a monster in a given slot."""

    slot_index: int
    amount: int
    monster_slots: object   # SlotsZone[MonsterInPlay]
    damage_type: str = "ability"   # "combat" | "ability"

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return self.monster_slots.get(self.slot_index) is not None  # type: ignore[union-attr]

    def apply(self, ctx: GameState) -> None:  # noqa: ARG002
        monster = self.monster_slots.get(self.slot_index)  # type: ignore[union-attr]
        if monster is not None:
            monster.take_damage(self.amount)  # take_damage handles prevent_damage absorption


@dataclass(slots=True)
class PreventDamageEffect:
    """Add a damage prevention shield to a player."""

    player_id: PlayerId
    amount: int

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return True

    def apply(self, ctx: GameState) -> None:
        ctx.get_player(self.player_id).prevent_damage += self.amount


@dataclass(slots=True)
class ResetAttackEffect:
    """Grant the active player one additional attack this turn (reset attack_used)."""

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return True

    def apply(self, ctx: GameState) -> None:
        ctx.turn_flags.attack_used = False


@dataclass(slots=True)
class AllPlayersGainCentsEffect:
    """Each player in turn order gains a fixed number of cents."""

    amount: int

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return True

    def apply(self, ctx: GameState) -> None:
        for pid in ctx.turn_order:
            ctx.get_player(pid).cents += self.amount


@dataclass(slots=True)
class AllPlayersTakeDamageEffect:
    """Each player in turn order takes damage (shield consumed per player)."""

    amount: int
    damage_type: str = "ability"

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return True

    def apply(self, ctx: GameState) -> None:
        for pid in ctx.turn_order:
            player = ctx.get_player(pid)
            amount = self.amount
            if player.damage_cap > 0:
                amount = min(amount, player.damage_cap)
            absorbed = min(player.prevent_damage, amount)
            player.prevent_damage = max(0, player.prevent_damage - amount)
            player.hp = max(0, player.hp - (amount - absorbed))


@dataclass(slots=True)
class AllPlayersDrawLootEffect:
    """Each player in turn order draws n loot cards."""

    count: int
    loot_deck: DeckZone
    log: Optional[EventLog] = field(default=None)

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return True

    def apply(self, ctx: GameState) -> None:
        from foursouls.engine.events import CardDrawn
        for pid in ctx.turn_order:
            n = min(self.count, len(self.loot_deck.cards))
            if n > 0:
                drawn = self.loot_deck.draw(n)
                ctx.get_player(pid).hand.extend(drawn)
                if self.log is not None:
                    for ref in drawn:
                        self.log.append(CardDrawn(player_id=pid, card_ref=ref, source="loot_rune"))


@dataclass(slots=True)
class CombatMissDamageEffect:
    """
    Represents pending combat-miss damage to an attacker.

    Pushed onto the stack by resolve_roll() instead of being applied
    directly, so players can respond (Soul Heart, Butter Bean, etc.).

    Fizzles automatically if combat ends before this resolves (e.g.
    the attacker's Bomb killed the monster first).
    """

    attacker_id: PlayerId
    amount: int
    combat: object  # CombatState — checked for is_active at resolve time

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return self.combat.is_active  # type: ignore[union-attr]

    def apply(self, ctx: GameState) -> None:
        player = ctx.get_player(self.attacker_id)
        absorbed = min(player.prevent_damage, self.amount)
        player.prevent_damage = max(0, player.prevent_damage - self.amount)
        player.hp = max(0, player.hp - (self.amount - absorbed))


@dataclass(slots=True)
class PreventDamageToMonsterEffect:
    """Add a damage-prevention shield to a monster in a given slot."""

    slot_index: int
    amount: int
    monster_slots: object  # SlotsZone[MonsterInPlay]

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return self.monster_slots.get(self.slot_index) is not None  # type: ignore[union-attr]

    def apply(self, ctx: GameState) -> None:  # noqa: ARG002
        monster = self.monster_slots.get(self.slot_index)  # type: ignore[union-attr]
        if monster is not None:
            monster.prevent_damage += self.amount


@dataclass(slots=True)
class CancelStackItemEffect:
    """
    Remove a specific item from the stack without resolving it.

    Used by Butter Bean (and similar cancel cards).  Fizzles if the
    target item has already resolved or been cancelled.
    """

    target_stack_id: int
    stack: object  # Stack — mutable reference captured at creation
    log: Optional[EventLog] = field(default=None)

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return self.stack.contains(self.target_stack_id)  # type: ignore[union-attr]

    def apply(self, ctx: GameState) -> None:  # noqa: ARG002
        from foursouls.engine.events import StackItemCancelled
        item = self.stack.remove(self.target_stack_id)  # type: ignore[union-attr]
        if item is not None and self.log is not None:
            self.log.append(StackItemCancelled(stack_id=item.stack_id, label=item.label))


@dataclass(slots=True)
class LootRollEffect:
    """
    Roll a d6 and delegate to the matching branch effect.

    branches: mapping from roll value (1–6) to Effect.
    Missing keys are treated as no-ops.
    """

    branches: Dict[int, Any]   # Dict[int, Effect]
    rng: Any                   # RNG

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return True

    def apply(self, ctx: GameState) -> None:
        roll = self.rng.roll_d6()
        branch = self.branches.get(roll)
        if branch is not None and branch.validate(ctx):
            branch.apply(ctx)


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
    """Grant the controlling player one additional loot play this turn.

    If the controller is the active player the quota goes into the normal
    turn counter.  If they are an off-turn player it goes into the per-player
    extra_loot_plays bucket so the active player's quota is unaffected.
    """

    player_id: PlayerId

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return True  # cost already paid; cannot fizzle

    def apply(self, ctx: GameState) -> None:
        if self.player_id == ctx.active_player_id:
            ctx.turn_flags.loot_plays_allowed += 1
        else:
            pid = str(self.player_id)
            ctx.turn_flags.extra_loot_plays[pid] = (
                ctx.turn_flags.extra_loot_plays.get(pid, 0) + 1
            )


@dataclass(slots=True)
class PreventDamageToMonsterEffect:
    """Add a damage prevention shield to a monster in a given slot."""

    slot_index: int
    amount: int
    monster_slots: object   # SlotsZone[MonsterInPlay]

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return self.monster_slots.get(self.slot_index) is not None  # type: ignore[union-attr]

    def apply(self, ctx: GameState) -> None:  # noqa: ARG002
        monster = self.monster_slots.get(self.slot_index)  # type: ignore[union-attr]
        if monster is not None:
            monster.prevent_damage += self.amount


@dataclass(slots=True)
class AoDamageEffect:
    """Deal damage to every player and every live monster in all slots.

    skip_player_id: if set, that player is excluded (used when the source is
    the controlling player e.g. Mama Mega — in Four Souls Mama Mega hits
    everyone including the controller, so skip_player_id is normally None).
    """

    amount: int
    monster_slots: object                   # SlotsZone[MonsterInPlay]
    skip_player_id: Optional[PlayerId] = None

    def validate(self, ctx: GameState) -> bool:  # noqa: ARG002
        return True

    def apply(self, ctx: GameState) -> None:
        for pid in ctx.turn_order:
            if self.skip_player_id is not None and pid == self.skip_player_id:
                continue
            player = ctx.get_player(pid)
            amount = self.amount
            if player.damage_cap > 0:
                amount = min(amount, player.damage_cap)
            absorbed = min(player.prevent_damage, amount)
            player.prevent_damage = max(0, player.prevent_damage - amount)
            player.hp = max(0, player.hp - (amount - absorbed))

        for idx in self.monster_slots.filled_indices():  # type: ignore[union-attr]
            monster = self.monster_slots.get(idx)  # type: ignore[union-attr]
            if monster is not None:
                monster.take_damage(self.amount)


@dataclass(slots=True)
class TreasureActivateEffect:
    """Wrapper that resolves a treasure item's tap effect.

    On resolution:
      1. Apply inner effect (if it validates).
      2. If is_one_use, remove the item from the owner's items list and
         add its CardRef to the treasure discard.
    """

    player_id: PlayerId
    instance_id: InstanceId
    inner: Effect
    is_one_use: bool
    treasure_discard: DiscardZone
    log: Optional[EventLog] = field(default=None)

    def validate(self, ctx: GameState) -> bool:
        return self.inner.validate(ctx)

    def apply(self, ctx: GameState) -> None:
        from foursouls.engine.events import CardDiscarded
        self.inner.apply(ctx)
        if self.is_one_use:
            player = ctx.get_player(self.player_id)
            item = next(
                (i for i in player.items if i.card_ref.instance_id == self.instance_id),
                None,
            )
            if item is not None:
                player.items.remove(item)
                self.treasure_discard.add(item.card_ref)
                if self.log is not None:
                    self.log.append(CardDiscarded(
                        player_id=self.player_id,
                        card_id=item.card_ref.card_id,
                        card_name=str(item.card_ref.card_id or "unknown"),
                        zone="treasure_discard",
                    ))
