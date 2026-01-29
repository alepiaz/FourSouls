from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from foursouls.engine.events import (
    DebugEvent,
    EffectFizzled,
    Event,
    PriorityPassed,
    StackItemPushed,
    StackItemResolved,
    WindowEnded,
)
from foursouls.engine.log import EventLog
from foursouls.engine.priority import PriorityManager
from foursouls.engine.rng import RNG
from foursouls.engine.stack import Stack, StackItem
from foursouls.model.commands import Command, EndTurn, PassPriority
from foursouls.model.effect_context import EffectContext
from foursouls.model.effects import Effect
from foursouls.model.game_state import GameState
from foursouls.model.turn_state import TurnPhase
from foursouls.rulesets.base_rules import BaseRuleset
from foursouls.rulesets.common.turn import (
    LOOT1_LABEL,
    advance_turn,
    make_loot1_effect,
    mark_loot1_scheduled,
    on_loot1_resolved,
    should_schedule_loot1,
)


@dataclass(slots=True)
class Game:
    state: GameState
    ruleset: BaseRuleset = field(default_factory=BaseRuleset)

    rng: RNG = field(default_factory=RNG)

    stack: Stack = field(default_factory=Stack)
    priority: PriorityManager = field(init=False)
    log: EventLog = field(default_factory=EventLog)

    def __post_init__(self) -> None:
        self.priority = PriorityManager(self.state.turn_order)
        self.priority.reset_to(self.state.active_player_id)

    def legal_commands(self) -> list[Command]:
        return self.ruleset.legal_commands(
            self.state,
            stack_empty=self.stack.empty(),
            priority_player_id=self.priority.current(),
        )

    def push_to_stack(
        self, *, controller_id, source: Any, effect: Effect, label: str = ""
    ) -> StackItem:
        item = self.stack.push(
            controller_id=controller_id, source=source, effect=effect, label=label
        )
        self.log.append(
            StackItemPushed(
                stack_id=item.stack_id,
                controller_id=item.controller_id,
                label=item.label,
            )
        )
        return item

    def _schedule_loot1_if_needed(self) -> None:
        if should_schedule_loot1(self.state):
            mark_loot1_scheduled(self.state)
            self.push_to_stack(
                controller_id=self.state.active_player_id,
                source="TURN_START",
                effect=make_loot1_effect(self.state),
                label=LOOT1_LABEL,
            )

    def step(self, command: Command) -> list[Event]:
        self.log.clear()

        # Start-of-turn automation: ensure Loot 1 is on the stack
        self._schedule_loot1_if_needed()

        legal = self.legal_commands()
        if not any(
            type(command) is type(c)
            and getattr(command, "kind", None) == getattr(c, "kind", None)
            for c in legal
        ):
            raise ValueError(f"Illegal command: {command}")

        if isinstance(command, PassPriority):
            passing_player = self.priority.current()
            self.log.append(PriorityPassed(player_id=passing_player))
            self.priority.pass_priority()
            # Pass-cycle resolution
            if self.priority.all_passed():
                if not self.stack.empty():
                    item = self.stack.pop()
                    eff: Effect = item.effect  # type: ignore[assignment]
                    ctx = EffectContext(state=self.state, rng=self.rng)

                    if eff.validate(ctx):
                        eff.apply(ctx)
                        self.log.append(
                            StackItemResolved(stack_id=item.stack_id, label=item.label)
                        )
                    else:
                        self.log.append(
                            EffectFizzled(
                                stack_id=item.stack_id,
                                reason="validate_failed",
                                label=item.label,
                            )
                        )

                    # If Loot 1 resolved (or fizzled), enter ACTION phase
                    if item.label == LOOT1_LABEL:
                        on_loot1_resolved(self.state)

                    self.priority.reset_to(self.state.active_player_id)
                else:
                    self.log.append(WindowEnded())
                    self.priority.reset_to(self.state.active_player_id)
            # When stack is empty during ACTION and NOT all passed, snap priority back.
            # (This prevents a free-floating priority window while keeping END_TURN available.)
            # Snap back WITHOUT clearing pass tracking, so we can still reach all_passed().
            elif self.state.turn.phase == TurnPhase.ACTION and self.stack.empty():
                # Just change current index, don't clear passed set
                self.priority.current_index = self.priority.player_order.index(
                    self.state.active_player_id
                )

        elif isinstance(command, EndTurn):
            self.state.turn.phase = TurnPhase.END
            prev = self.state.active_player_id

            advance_turn(self.state)
            self.priority.reset_to(self.state.active_player_id)

            self.log.append(
                DebugEvent(
                    {
                        "action": "EndTurn",
                        "from": str(prev),
                        "to": str(self.state.active_player_id),
                    }
                )
            )

            # Immediately schedule next turn's Loot 1 onto stack
            self._schedule_loot1_if_needed()

        else:
            raise NotImplementedError(f"Unsupported command: {command}")

        return list(self.log.events)
