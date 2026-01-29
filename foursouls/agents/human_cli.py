from __future__ import annotations

from dataclasses import dataclass

from foursouls.engine.game_loop import Game
from foursouls.model.commands import EndTurn, PassPriority


@dataclass(slots=True)
class HumanCLI:
    """
    Minimal interactive loop to 'play' Sprint 1:
    - PASS priority
    - END TURN (when legal)
    """

    game: Game

    def render(self) -> None:
        s = self.game.state
        active = s.active_player_id
        phase = s.turn.phase.value

        top = self.game.stack.top()
        top_label = top.label if top else "-"
        stack_len = len(self.game.stack)

        print("\n" + "=" * 50)
        print(f"Turn #{s.turn.number} | Phase: {phase}")
        print(f"Active: {active} | Priority: {self.game.priority.current()}")
        print(f"Stack: {stack_len} | Top: {top_label}")
        print(f"Loot deck: {len(s.loot_deck)} | Loot discard: {len(s.loot_discard)}")

        # Monster board (Sprint 2)
        monster_status = []
        for i in range(len(s.monster_slots)):
            monster = s.monster_slots.get(i)
            if monster:
                monster_status.append(f"[{i}] {monster}")
            else:
                monster_status.append(f"[{i}] empty")
        print(f"Monsters: {' | '.join(monster_status)}")

        for pid in s.turn_order:
            p = s.get_player(pid)
            hand_ids = [c.instance_id for c in p.hand]
            print(
                f"- {pid}: HP {p.hp}/{p.max_hp} | ¢ {p.cents} | hand({len(p.hand)}): {hand_ids}"
            )

        kinds = [c.kind for c in self.game.legal_commands()]
        print(f"Legal: {kinds}")
        print("Commands: [p] pass | [e] end turn | [q] quit")

    def run(self) -> None:
        while True:
            self.render()
            cmd = input("> ").strip().lower()

            if cmd in ("q", "quit", "exit"):
                print("Bye 👋")
                return

            if cmd == "p":
                events = self.game.step(PassPriority())
                self._print_events(events)
                continue

            if cmd == "e":
                try:
                    events = self.game.step(EndTurn())
                except ValueError as e:
                    print(f"Illegal: {e}")
                    continue
                self._print_events(events)
                continue

            print("Unknown command. Use p/e/q.")

    def _print_events(self, events) -> None:
        if not events:
            print("(no events)")
            return
        print("Events:")
        for e in events:
            # most of our event dataclasses are printable enough
            print(f"  - {e.name}: {e}")
