# Sprint 1 — Setup + Phase Machine + EndTurn

### 1) Sprint / commit context

**Sprint:** Sprint 1  
**What's done vs partial:**

Done:
- AllPlayersPassed replaces WindowEnded (S1.0)
- Phase + TurnFlags on GameState (S1.1)
- GameZones + setup_game() (S1.3)
- Legality module (S1.4)
- Turn controller — enter_start_phase, on_all_passed_empty_stack, on_end_turn (S1.5)
- D5 milestone events (PhaseChanged, TurnEnded, ActivePlayerChanged)
- Pass bot + 3-turn integration test

Partial / skipped:
- END is not a stable phase; cleanup runs inline inside on_end_turn (no END phase stop)
- No real card definitions; all cards are placeholder CardRef IDs
- No combat, shop, loot-play, item activation

---

### 2) Files changed

**New files**

- `foursouls/model/phase.py` — Phase enum (START/ACTION/END) + TurnFlags dataclass
- `foursouls/engine/game_zones.py` — GameZones dataclass grouping all shared zones
- `foursouls/rulesets/common/__init__.py` — package marker
- `foursouls/rulesets/common/setup.py` — setup_game(): shuffle, deal hands, fill slots, return Game
- `foursouls/rulesets/common/legality.py` — legal_commands(state, stack) function
- `foursouls/rulesets/common/effects.py` — DrawLoot1Effect
- `foursouls/rulesets/common/turn.py` — enter_start_phase, on_all_passed_empty_stack, on_end_turn
- `agents/__init__.py` — package marker
- `agents/pass_bot.py` — choose_command(): prefers EndTurn, falls back to PassPriority
- `tests/test_setup.py` — setup determinism + slot-fill tests
- `tests/test_legality.py` — EndTurn legality matrix tests
- `tests/test_turn.py` — phase progression unit tests
- `tests/test_sprint1_loop.py` — 3-turn bot simulation (D2 + D5 acceptance)

**Modified files**

- `foursouls/model/commands.py` — added EndTurn command
- `foursouls/model/game_state.py` — added phase, turn_number, turn_flags fields; added reset_for_new_turn()
- `foursouls/engine/events.py` — added AllPlayersPassed (replaces WindowEnded), PhaseChanged, TurnEnded, ActivePlayerChanged
- `foursouls/engine/game_loop.py` — added zones field; step() handles EndTurn and calls turn hooks; legal_commands() passes stack to ruleset
- `foursouls/rulesets/base_rules.py` — delegates legal_commands to rulesets/common/legality; signature now takes stack
- `tests/test_events.py` — updated WindowEnded → AllPlayersPassed
- `tests/test_game_pass_window.py` — updated WindowEnded → AllPlayersPassed; renamed test
- `tests/test_state_init.py` — added phase default + turn flags reset tests

**Deleted files**

- (none; WindowEnded class was replaced in-place)

---

### 3) Public API changes

```python
# Unchanged signature, new behavior:
Game.step(command: Command) -> list[Event]
# Now handles EndTurn; calls on_all_passed_empty_stack after AllPlayersPassed

# Signature changed (stack added):
BaseRuleset.legal_commands(ctx: GameState, stack: Stack) -> list[Command]

# New top-level function (entry point):
setup_game(
    state: GameState,
    *,
    loot_cards: list[CardRef],
    treasure_cards: list[CardRef],
    monster_cards: list[CardRef],
    rng: RNG,
    starting_hand_size: int = 3,
    shop_size: int = 3,
    monster_slot_count: int = 2,
    starter_id: Optional[PlayerId] = None,
) -> Game

# New ruleset hooks (called from Game.step):
on_all_passed_empty_stack(game: Game) -> None
on_end_turn(game: Game) -> None

# New utility (callable directly):
enter_start_phase(game: Game) -> None

# New dataclasses/enums:
Phase(Enum): START / ACTION / END
TurnFlags: loot_play_used, attack_used, purchase_used  (all bool, default False)
GameZones: loot_deck, loot_discard, treasure_deck, treasure_discard,
           monster_deck, monster_discard, shop_slots, monster_slots
```

---

### 4) Behavioral rules implemented

- **AllPlayersPassed:** emitted when every player has passed in the same priority cycle and the stack is empty.
- **Loot1 scheduling:** happens when `enter_start_phase(game)` is called — pushes a `DrawLoot1Effect` stack item with label `"Loot1"` for the current active player.
- **START → ACTION transition:** happens when `AllPlayersPassed` fires and `state.phase == START` (i.e., after Loot1 has resolved and all passed again on an empty stack).
- **EndTurn legality:** legal only if `phase == ACTION` and `stack.empty()`.
- **EndTurn effects:** heal active player to max_hp; trim hand to ≤ 10; emit TurnEnded; advance active player to next in turn order; increment turn_number; reset TurnFlags; emit ActivePlayerChanged + PhaseChanged(ACTION→START); reset priority; push Loot1 for new active player.
- **DrawLoot1Effect:** fizzles (validate=False) if loot deck is empty; otherwise draws 1 CardRef from top of loot deck into the active player's hand.
- **Stack resolution:** unchanged from Sprint 0 — one item resolves per all-pass cycle; priority resets to active player after each resolution.

**Ambiguities picked:**
- END phase is not a stable stop — cleanup runs inline in `on_end_turn` and immediately transitions to START. No separate END phase window exists yet.
- `enter_start_phase` is idempotently called even when phase is already START (harmless redundant set).

---

### 5) Critical decisions

| Decision | Choice | Why |
|---|---|---|
| Zones stored in | `Game` (not `GameState`) | GameState is pure serialisable data; zones are mutable engine-owned structures. Keeps the model clean. |
| `setup_game` returns | `Game` | Zones and state must be created together; returning Game avoids a two-step init pattern. |
| Card placeholders | `CardRef(InstanceId(str))` | Existing type; enough for Sprint 1 zone mechanics without a card catalog. |
| WindowEnded | Replaced with `AllPlayersPassed` | "Window ended" implies terminal state; the real behavior is "signal, then ruleset decides". |
| Circular import (turn.py ↔ game_loop.py) | `TYPE_CHECKING` guard in turn.py | turn.py uses Game only in type hints; avoids import cycle without restructuring. |
| END phase | Inline in EndTurn, not a stop | Simplest correct behavior for Sprint 1; END as a stable phase is a Sprint 2+ concern. |

---

### 6) Tests added/updated

Added:
- `tests/test_setup.py::test_setup_deals_starting_hands_deterministic`
- `tests/test_setup.py::test_setup_fills_shop_and_monsters`
- `tests/test_legality.py::test_pass_always_legal`
- `tests/test_legality.py::test_end_turn_legal_in_action_phase_with_empty_stack`
- `tests/test_legality.py::test_end_turn_illegal_when_stack_not_empty`
- `tests/test_legality.py::test_end_turn_illegal_outside_action_phase`
- `tests/test_turn.py::test_start_phase_queues_loot1`
- `tests/test_turn.py::test_after_loot1_resolves_and_all_passed_phase_becomes_action`
- `tests/test_turn.py::test_end_turn_advances_player_and_phase_start_and_queues_loot1`
- `tests/test_sprint1_loop.py::test_simulate_three_turns`
- `tests/test_sprint1_loop.py::test_end_turn_step_emits_milestone_events`
- `tests/test_state_init.py::test_game_state_defaults_phase_start`
- `tests/test_state_init.py::test_turn_flags_reset`

Updated:
- `tests/test_events.py::test_event_log_keeps_order` — WindowEnded → AllPlayersPassed
- `tests/test_game_pass_window.py::test_all_players_passed_emitted_when_stack_empty` — renamed + updated

Not yet covered (known gaps):
- DrawLoot1Effect fizzle path in a real game (deck exhausted mid-turn)
- Hand trim at exactly 10 cards (boundary)
- Single-player turn order edge case

---

### 7) Current demo path

```
pytest -q tests/test_sprint1_loop.py::test_simulate_three_turns
```

Verbal walkthrough:
1. `setup_game(seed=1)` — decks shuffled, hands dealt (3 cards each), shop filled (3), monsters filled (2)
2. `enter_start_phase(game)` — Loot1 pushed for P1
3. PASS / PASS → Loot1 resolves (P1 draws 1 loot)
4. PASS / PASS → AllPlayersPassed → START → ACTION
5. END_TURN → P1 healed, P2 becomes active, Loot1 pushed for P2, turn_number = 2
6. Repeat for P2 (turn 2) and P1 again (turn 3)
7. After turn 3: turn_number == 4, P1 hand = 5 cards (3 start + 2 draws), P2 hand = 4 cards

---

### 8) Problems / open questions

- **Design uncertainty:** `enter_start_phase` is currently called externally by tests and by `on_end_turn`. When a full game controller exists, it should be called automatically after `setup_game` — right now callers must remember to call it.
- **Next sprint dependencies:** real card definitions needed before any card-text effects; combat needs monster slots to be aware of HP values; shop needs a BuyCard command and a cost system.
