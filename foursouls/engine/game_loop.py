from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from foursouls.engine.events import (
    AllPlayersPassed,
    EffectFizzled,
    Event,
    ItemActivated,
    PriorityPassed,
    StackItemPushed,
    StackItemResolved,
)
from foursouls.engine.game_zones import GameZones
from foursouls.engine.log import EventLog
from foursouls.engine.priority import PriorityManager
from foursouls.engine.rng import RNG
from foursouls.engine.stack import Stack, StackItem
from foursouls.model.combat_state import CombatState
from foursouls.model.commands import ActivateCharacterAbility, AttackMonster, BuyShop, Command, EndTurn, PassPriority, PlayLoot, RollCombat
from foursouls.model.effects import Effect
from foursouls.model.game_state import GameState
from foursouls.rulesets.base_rules import BaseRuleset
from foursouls.rulesets.common.combat import enter_combat, resolve_roll
from foursouls.rulesets.common.effects import GrantExtraLootPlayEffect
from foursouls.rulesets.common.loot import on_play_loot
from foursouls.rulesets.common.shop import on_buy_shop
from foursouls.rulesets.common.turn import on_all_passed_empty_stack, on_end_turn


@dataclass(slots=True)
class StepResult:
    """
    The value returned by Game.step().

    Carries the list of events emitted during that command.  The extra
    wrapper leaves room to add warnings, illegal-reason metadata, or
    timing info without changing the call-site signature later.
    """
    events: List[Event]


@dataclass(slots=True)
class Game:
    state: GameState
    ruleset: BaseRuleset = field(default_factory=BaseRuleset)

    zones: Optional[GameZones] = None
    combat: Optional[CombatState] = None
    game_over: bool = False
    rng: RNG = field(default_factory=RNG)
    stack: Stack = field(default_factory=Stack)
    priority: PriorityManager = field(init=False)
    log: EventLog = field(default_factory=EventLog)

    def __post_init__(self) -> None:
        self.priority = PriorityManager(self.state.turn_order)
        self.priority.reset_to(self.state.active_player_id)

    def legal_commands(self) -> list[Command]:
        return self.ruleset.legal_commands(self)

    def get_legal_actions(self) -> list:
        """Return legal actions enriched with display context. See engine.actions."""
        from foursouls.engine.actions import get_legal_actions
        return get_legal_actions(self)

    def push_to_stack(self, *, controller_id, source: Any, effect: Effect, label: str = "") -> StackItem:
        item = self.stack.push(controller_id=controller_id, source=source, effect=effect, label=label)
        self.log.append(StackItemPushed(stack_id=item.stack_id, controller_id=item.controller_id, label=item.label))
        return item

    def step(self, command: Command) -> StepResult:
        """
        Apply one command and perform any automatic resolution (on all-pass).

        - PassPriority: record the pass; if all players have now passed:
            - stack not empty → resolve ONE item, reset priority.
            - stack empty     → emit AllPlayersPassed, run phase hook, reset priority.
        - EndTurn: run end-of-turn cleanup, advance active player, enter START phase.
        """
        self.log.clear()

        legal = self.legal_commands()
        if command not in legal:
            raise ValueError(f"Illegal command: {command}")

        if isinstance(command, PassPriority):
            passing_player = self.priority.current()
            self.log.append(PriorityPassed(player_id=passing_player))
            self.priority.pass_priority()

            if self.priority.all_passed():
                if not self.stack.empty():
                    item = self.stack.pop()
                    eff: Effect = item.effect  # type: ignore[assignment]

                    if eff.validate(self.state):
                        eff.apply(self.state)
                        self.log.append(StackItemResolved(stack_id=item.stack_id, label=item.label))
                    else:
                        self.log.append(EffectFizzled(stack_id=item.stack_id, reason="validate_failed", label=item.label))

                    self.priority.reset_to(self.state.active_player_id)
                    # After resolution, if the stack is now empty auto-advance
                    # phase so START does not require a second empty-stack pass.
                    if self.stack.empty():
                        on_all_passed_empty_stack(self)
                else:
                    self.log.append(AllPlayersPassed())
                    on_all_passed_empty_stack(self)
                    self.priority.reset_to(self.state.active_player_id)

        elif isinstance(command, EndTurn):
            on_end_turn(self)

        elif isinstance(command, PlayLoot):
            on_play_loot(self, command.card_ref)

        elif isinstance(command, ActivateCharacterAbility):
            active_id = self.state.active_player_id
            self.state.get_player(active_id).character.tap()  # pay cost
            self.log.append(ItemActivated(player_id=active_id, source="character:tap_ability"))
            effect = GrantExtraLootPlayEffect(player_id=active_id)
            self.push_to_stack(
                controller_id=active_id,
                source="character:tap_ability",
                effect=effect,
                label="GrantExtraLootPlay",
            )
            self.priority.reset_to(active_id)

        elif isinstance(command, BuyShop):
            on_buy_shop(self, command.slot_index)

        elif isinstance(command, AttackMonster):
            enter_combat(self, command.slot_index)

        elif isinstance(command, RollCombat):
            resolve_roll(self)

        else:
            raise NotImplementedError(f"Unsupported command: {command}")

        return StepResult(events=list(self.log.events))