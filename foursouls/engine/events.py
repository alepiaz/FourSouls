from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from foursouls.model.phase import Phase
from foursouls.model.refs import CardRef, PlayerId


@dataclass(frozen=True, slots=True)
class Event:
    """
    Base event. Keep events immutable.
    """
    name: str


@dataclass(frozen=True, slots=True)
class PriorityPassed(Event):
    player_id: PlayerId

    def __init__(self, player_id: PlayerId):
        object.__setattr__(self, "name", "PriorityPassed")
        object.__setattr__(self, "player_id", player_id)


@dataclass(frozen=True, slots=True)
class AllPlayersPassed(Event):
    def __init__(self) -> None:
        object.__setattr__(self, "name", "AllPlayersPassed")


@dataclass(frozen=True, slots=True)
class StackItemPushed(Event):
    stack_id: int
    controller_id: PlayerId
    label: str = ""

    def __init__(self, stack_id: int, controller_id: PlayerId, label: str = ""):
        object.__setattr__(self, "name", "StackItemPushed")
        object.__setattr__(self, "stack_id", stack_id)
        object.__setattr__(self, "controller_id", controller_id)
        object.__setattr__(self, "label", label)


@dataclass(frozen=True, slots=True)
class StackItemResolved(Event):
    stack_id: int
    label: str = ""

    def __init__(self, stack_id: int, label: str = ""):
        object.__setattr__(self, "name", "StackItemResolved")
        object.__setattr__(self, "stack_id", stack_id)
        object.__setattr__(self, "label", label)


@dataclass(frozen=True, slots=True)
class EffectFizzled(Event):
    stack_id: int
    reason: str = "validate_failed"
    label: str = ""

    def __init__(self, stack_id: int, reason: str = "validate_failed", label: str = ""):
        object.__setattr__(self, "name", "EffectFizzled")
        object.__setattr__(self, "stack_id", stack_id)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "label", label)


@dataclass(frozen=True, slots=True)
class PhaseChanged(Event):
    old_phase: Phase
    new_phase: Phase

    def __init__(self, old_phase: Phase, new_phase: Phase) -> None:
        object.__setattr__(self, "name", "PhaseChanged")
        object.__setattr__(self, "old_phase", old_phase)
        object.__setattr__(self, "new_phase", new_phase)


@dataclass(frozen=True, slots=True)
class TurnEnded(Event):
    player_id: PlayerId
    turn_number: int

    def __init__(self, player_id: PlayerId, turn_number: int) -> None:
        object.__setattr__(self, "name", "TurnEnded")
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "turn_number", turn_number)


@dataclass(frozen=True, slots=True)
class ActivePlayerChanged(Event):
    old_player_id: PlayerId
    new_player_id: PlayerId

    def __init__(self, old_player_id: PlayerId, new_player_id: PlayerId) -> None:
        object.__setattr__(self, "name", "ActivePlayerChanged")
        object.__setattr__(self, "old_player_id", old_player_id)
        object.__setattr__(self, "new_player_id", new_player_id)


@dataclass(frozen=True, slots=True)
class TreasureBought(Event):
    player_id: PlayerId
    card_ref: CardRef
    slot_index: int
    cost: int

    def __init__(self, player_id: PlayerId, card_ref: CardRef, slot_index: int, cost: int) -> None:
        object.__setattr__(self, "name", "TreasureBought")
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "card_ref", card_ref)
        object.__setattr__(self, "slot_index", slot_index)
        object.__setattr__(self, "cost", cost)


@dataclass(frozen=True, slots=True)
class CombatRollResult(Event):
    attacker_id: PlayerId
    defender_slot: int
    roll: int
    evade: int
    is_hit: bool

    def __init__(
        self,
        attacker_id: PlayerId,
        defender_slot: int,
        roll: int,
        evade: int,
        is_hit: bool,
    ) -> None:
        object.__setattr__(self, "name", "CombatRollResult")
        object.__setattr__(self, "attacker_id", attacker_id)
        object.__setattr__(self, "defender_slot", defender_slot)
        object.__setattr__(self, "roll", roll)
        object.__setattr__(self, "evade", evade)
        object.__setattr__(self, "is_hit", is_hit)


@dataclass(frozen=True, slots=True)
class MonsterDied(Event):
    attacker_id: PlayerId
    slot_index: int
    card_ref: CardRef

    def __init__(self, attacker_id: PlayerId, slot_index: int, card_ref: CardRef) -> None:
        object.__setattr__(self, "name", "MonsterDied")
        object.__setattr__(self, "attacker_id", attacker_id)
        object.__setattr__(self, "slot_index", slot_index)
        object.__setattr__(self, "card_ref", card_ref)


@dataclass(frozen=True, slots=True)
class CombatEntered(Event):
    attacker_id: PlayerId
    defender_slot: int

    def __init__(self, attacker_id: PlayerId, defender_slot: int) -> None:
        object.__setattr__(self, "name", "CombatEntered")
        object.__setattr__(self, "attacker_id", attacker_id)
        object.__setattr__(self, "defender_slot", defender_slot)


@dataclass(frozen=True, slots=True)
class RewardGranted(Event):
    player_id: PlayerId
    cents: int

    def __init__(self, player_id: PlayerId, cents: int) -> None:
        object.__setattr__(self, "name", "RewardGranted")
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "cents", cents)


@dataclass(frozen=True, slots=True)
class SoulGranted(Event):
    player_id: PlayerId
    card_ref: CardRef

    def __init__(self, player_id: PlayerId, card_ref: CardRef) -> None:
        object.__setattr__(self, "name", "SoulGranted")
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "card_ref", card_ref)


@dataclass(frozen=True, slots=True)
class PlayerDied(Event):
    player_id: PlayerId
    slot_index: int   # the monster slot the player was fighting

    def __init__(self, player_id: PlayerId, slot_index: int) -> None:
        object.__setattr__(self, "name", "PlayerDied")
        object.__setattr__(self, "player_id", player_id)
        object.__setattr__(self, "slot_index", slot_index)


@dataclass(frozen=True, slots=True)
class DebugEvent(Event):
    payload: Any

    def __init__(self, payload: Any):
        object.__setattr__(self, "name", "DebugEvent")
        object.__setattr__(self, "payload", payload)