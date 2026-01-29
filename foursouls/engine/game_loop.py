from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from foursouls.engine.events import (
    EffectFizzled,
    Event,
    PriorityPassed,
    StackItemPushed,
    StackItemResolved,
    WindowEnded,
    DebugEvent,
)
from foursouls.engine.log import EventLog
from foursouls.engine.priority import PriorityManager
from foursouls.engine.stack import Stack, StackItem
from foursouls.model.commands import Command, EndTurn, PassPriority
from foursouls.model.effects import Effect
from foursouls.model.game_state import GameState
from foursouls.model.turn_state import TurnPhase
from foursouls.rulesets.base_rules import BaseRuleset


@dataclass(slots=True)
class Game:
    state: GameState
    ruleset: BaseRuleset = field(default_factory=BaseRuleset)

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

    def step(self, command: Command) -> list[Event]:
        self.log.clear()

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

            # Pass-cycle resolution (unchanged)
            if self.priority.all_passed():
                if not self.stack.empty():
                    item = self.stack.pop()
                    eff: Effect = item.effect  # type: ignore[assignment]

                    if eff.validate(self.state):
                        eff.apply(self.state)
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

                    self.priority.reset_to(self.state.active_player_id)
                else:
                    self.log.append(WindowEnded())
                    self.priority.reset_to(self.state.active_player_id)

        elif isinstance(command, EndTurn):
            # Minimal EndTurn behavior for Sprint 1 legality testing.
            # Sprint 1.5 will expand this (Loot 1 scheduling, end-phase cleanup, etc.)
            prev = self.state.active_player_id

            # End current turn (minimal)
            self.state.turn.phase = TurnPhase.END

            nxt = self.state.next_player_id(prev)
            self.state.active_player_id = nxt
            self.state.turn.number += 1

            # Reset per-turn flags & move to START (next issues will schedule Loot 1 here)
            self.state.turn.attack_used = False
            self.state.turn.purchase_used = False
            self.state.turn.loot_play_used = False
            self.state.turn.phase = TurnPhase.START

            self.priority.reset_to(self.state.active_player_id)
            self.log.append(
                DebugEvent({"action": "EndTurn", "from": str(prev), "to": str(nxt)})
            )

        else:
            raise NotImplementedError(f"Unsupported command: {command}")

        return list(self.log.events)
