from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from foursouls.model.phase import Phase
from foursouls.model.refs import CardId, CardRef, PlayerId


@dataclass(frozen=True, slots=True)
class Event:
    """
    Immutable base event.  ``name`` is set automatically to the class name via
    __post_init__, so subclasses never need to pass it.
    """
    name: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", type(self).__name__)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GameSetupCompleted(Event):
    """Fired once at the end of setup_game(), before the first step()."""
    player_ids: Tuple[PlayerId, ...]
    starting_hand_size: int
    shop_size: int
    monster_slot_count: int


# ---------------------------------------------------------------------------
# Turn flow
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class TurnStarted(Event):
    """Fired at the beginning of each player's turn (entering START phase)."""
    turn_number: int
    player_id: PlayerId


@dataclass(frozen=True, slots=True)
class TurnEnded(Event):
    player_id: PlayerId
    turn_number: int


@dataclass(frozen=True, slots=True)
class ActivePlayerChanged(Event):
    old_player_id: PlayerId
    new_player_id: PlayerId


@dataclass(frozen=True, slots=True)
class PhaseChanged(Event):
    old_phase: Phase
    new_phase: Phase


# ---------------------------------------------------------------------------
# Priority / stack
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PriorityPassed(Event):
    player_id: PlayerId


@dataclass(frozen=True, slots=True)
class AllPlayersPassed(Event):
    pass


@dataclass(frozen=True, slots=True)
class StackItemPushed(Event):
    stack_id: int
    controller_id: PlayerId
    label: str = ""


@dataclass(frozen=True, slots=True)
class StackItemResolved(Event):
    stack_id: int
    label: str = ""


@dataclass(frozen=True, slots=True)
class EffectFizzled(Event):
    stack_id: int
    reason: str = "validate_failed"
    label: str = ""


# ---------------------------------------------------------------------------
# Loot / cards
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class LootPlayed(Event):
    """Fired when a player plays a loot card from their hand onto the stack."""
    player_id: PlayerId
    card_id: Optional[CardId]
    card_name: str


@dataclass(frozen=True, slots=True)
class CardDrawn(Event):
    """Fired when a card is drawn from a deck into a player's hand."""
    player_id: PlayerId
    card_ref: CardRef
    source: str   # e.g. "loot_deck"


@dataclass(frozen=True, slots=True)
class CardDiscarded(Event):
    """Fired when a card moves to a discard zone."""
    player_id: PlayerId
    card_id: Optional[CardId]
    card_name: str
    zone: str     # e.g. "loot_discard"


# ---------------------------------------------------------------------------
# Character ability
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ItemActivated(Event):
    """Fired when a player taps their character to use its ability."""
    player_id: PlayerId
    source: str   # e.g. "character:tap_ability"


# ---------------------------------------------------------------------------
# Shop
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ShopBought(Event):
    """Fired when a player buys an item from the shop."""
    player_id: PlayerId
    card_ref: CardRef
    item_name: str
    slot_index: int
    cost: int


@dataclass(frozen=True, slots=True)
class CoinsGained(Event):
    """Fired whenever a player gains coins (reward, loot, etc.)."""
    player_id: PlayerId
    cents: int
    reason: str   # e.g. "monster_kill", "loot_card"


@dataclass(frozen=True, slots=True)
class CoinsSpent(Event):
    """Fired whenever a player spends coins."""
    player_id: PlayerId
    amount: int
    reason: str   # e.g. "shop_buy"


# ---------------------------------------------------------------------------
# Combat
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AttackDeclared(Event):
    """Fired the moment a player declares an attack (before combat state is set)."""
    player_id: PlayerId
    monster_slot: int
    monster_id: Optional[CardId]
    monster_name: str


@dataclass(frozen=True, slots=True)
class CombatEntered(Event):
    """Fired once combat state is established for an attacker/defender pair."""
    attacker_id: PlayerId
    defender_slot: int
    monster_id: Optional[CardId]
    monster_name: str
    monster_hp: int
    monster_evade: int


@dataclass(frozen=True, slots=True)
class CombatRollResult(Event):
    attacker_id: PlayerId
    defender_slot: int
    roll: int
    evade: int
    is_hit: bool
    attack_stat: int = 1    # effective ATK used for damage this roll


@dataclass(frozen=True, slots=True)
class DamageDealt(Event):
    """Fired whenever damage is applied to any game object."""
    source_player_id: Optional[PlayerId]
    source_monster_slot: Optional[int]
    target_player_id: Optional[PlayerId]
    target_monster_slot: Optional[int]
    amount: int
    reason: str             # e.g. "combat_hit", "combat_miss", "loot_bomb"
    damage_type: str = "combat"   # "combat" | "ability"


# ---------------------------------------------------------------------------
# Events (monster-deck event cards)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class EventEntered(Event):
    """Fired when an event card enters a monster slot and its trigger is pushed."""
    slot_index: int
    card_ref: CardRef
    card_name: str


# ---------------------------------------------------------------------------
# Death / rewards
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MonsterDied(Event):
    attacker_id: PlayerId
    slot_index: int
    card_ref: CardRef
    monster_name: str
    had_soul: bool
    reward_coin: int = 0
    reward_loot: int = 0
    reward_treasure: int = 0


@dataclass(frozen=True, slots=True)
class PlayerDied(Event):
    player_id: PlayerId
    slot_index: int       # monster slot the player was fighting
    monster_name: str


@dataclass(frozen=True, slots=True)
class SoulGranted(Event):
    player_id: PlayerId
    card_ref: CardRef
    card_name: str


# ---------------------------------------------------------------------------
# Death penalty
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DeathPenaltyPaid(Event):
    """
    Fired immediately after PlayerDied, once the four-step penalty is applied:
      1. Destroy one non-eternal item (item_destroyed=None if the player had none).
      2. Discard one loot card from hand (loot_discarded=None if hand was empty).
      3. Lose 1¢ (cents_lost=0 if the player was already broke).
      4. Deactivate (untap) all ↷ items (items_deactivated is the count untapped).
    """
    player_id: PlayerId
    item_destroyed: Optional[CardRef]   # None if no destroyable items available
    loot_discarded: Optional[CardRef]   # None if hand was empty
    cents_lost: int
    items_deactivated: int


# ---------------------------------------------------------------------------
# Game end
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GameWon(Event):
    """Fired when a player reaches the soul win threshold."""
    player_id: PlayerId
    soul_count: int


# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DebugEvent(Event):
    payload: object
