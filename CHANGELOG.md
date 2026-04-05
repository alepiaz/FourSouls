# Changelog

---

## Sprint 4 — Combat

### 1) Sprint / commit context

**Sprint:** Sprint 4  
**What's done vs partial:**

Done:
- R4.0 — `MonsterInPlay` runtime model; `MonsterDef` blueprint; `make_monster_in_play` factory; `FLY`, `GAPER`, `SPIDER` card definitions; `setup_game` creates `MonsterInPlay` for each occupied slot
- R4.1 — `AttackMonster(slot_index)` command; full legality matrix (ACTION + empty stack + slot occupied + `attack_used=False` + no active combat); `attack_used` flag integration
- R4.2 — `CombatState` model; `enter_combat` handler; `CombatEntered` event; `RollCombat` legality (combat active)
- R4.3 — `resolve_roll`: d6 roll, hit/miss logic, `CombatRollResult` event, hp clamped to 0
- R4.4 — `resolve_monster_death`: slot clear, monster discard, deck refill, `MonsterDied` event
- R4.5 — `resolve_player_death`: combat cleared, monster survives, `PlayerDied` event; `test_sprint4_loop.py` hp-floor test updated (second roll after death is now illegal)
- R4.6 — Cent reward granted on kill; soul ownership granted for soul monsters; `RewardGranted` and `SoulGranted` events; `HORF` soul monster added to registry
- R4.7 — `combat_bot` agent; Sprint 4 acceptance slice (win path + death path, attack-used resets, full integration targets)

Partial / skipped:
- No treasure or character interactions with combat (damage modifiers, rerolls, extra attacks)
- No multi-player combat targeting (always active player vs. chosen slot)
- No end-of-turn forced-combat rule
- No boss/room card type; soul system is ownership-only (no win condition check)
- Full death penalty ecosystem (item loss, re-spawn) is out of scope

---

### 2) Files changed

**New files**

- `foursouls/model/monster_in_play.py` — `MonsterInPlay(card_ref, base_hp, current_hp, evade, reward_cents, has_soul)`; `is_alive()`, `take_damage(amount)`
- `foursouls/model/combat_state.py` — `CombatState(attacker_id, defender_slot, monster_ref, is_active=True)`
- `foursouls/cards/monsters.py` — `MonsterDef` blueprint; `_REGISTRY` (FLY, GAPER, SPIDER, HORF); `_DEFAULT` fallback; `make_monster_in_play(card_ref) -> MonsterInPlay`
- `foursouls/rulesets/common/combat.py` — `enter_combat`, `resolve_roll`, `resolve_monster_death`, `resolve_player_death`
- `agents/combat_bot.py` — `choose_command()`: `RollCombat` → `AttackMonster` → `EndTurn` → `PassPriority`
- `tests/test_monster_scaffold.py` — 17 tests: `make_monster_in_play` stats per card, default fallback, hp invariants, `take_damage`, `is_alive`, setup integration
- `tests/test_attack_legality.py` — 11 tests: legality matrix for `AttackMonster` and `RollCombat`, dispatch sets `attack_used`, reset on `EndTurn`
- `tests/test_combat_entry.py` — 17 tests: `CombatState` fields, attack quota, `CombatEntered` event, priority reset, no unrelated mutation, combat cleared on `EndTurn`
- `tests/test_monster_death.py` — 21 tests: slot cleared, combat ends, `MonsterDied` event, discard, deck refill paths, neighboring slots unchanged, deterministic refill, full multi-hp kill sequence
- `tests/test_player_death.py` — 19 tests: combat cleared, monster survives, `attack_used` true, `PlayerDied` event, no double-trigger, post-death state stable, multi-miss path
- `tests/test_kill_rewards.py` — 22 tests: cent grant, zero-reward path, `RewardGranted` event fields + exactly-once, soul grant, `SoulGranted` event fields + exactly-once, no-soul path, registry-backed monsters, isolation (rewards go to attacker only)
- `tests/test_sprint4_acceptance.py` — 24 tests: win path (11), death path (8), attack-used resets (3), full integration targets (2)

**Modified files**

- `foursouls/model/commands.py` — added `AttackMonster(slot_index: int, kind="ATTACK_MONSTER")`, `RollCombat(kind="ROLL_COMBAT")`
- `foursouls/engine/events.py` — added `CombatEntered`, `CombatRollResult`, `MonsterDied`, `PlayerDied`, `RewardGranted`, `SoulGranted`
- `foursouls/engine/game_loop.py` — added `combat: Optional[CombatState]` field; `step()` dispatches `AttackMonster` → `enter_combat` and `RollCombat` → `resolve_roll`; `on_end_turn` clears `game.combat = None`
- `foursouls/rulesets/common/legality.py` — added `AttackMonster` generation block (ACTION + empty stack + `not attack_used` + `combat is None` + zones set, per occupied slot); added `RollCombat` generation (combat active)
- `tests/test_sprint4_loop.py` — `test_player_hp_never_goes_below_zero` updated: second roll after player death is now illegal; assertion changed to check `game.combat is None`

---

### 3) Public API changes

```python
# New commands:
AttackMonster(slot_index: int, kind="ATTACK_MONSTER")   # frozen dataclass
RollCombat(kind="ROLL_COMBAT")                          # frozen dataclass

# New events (engine/events.py):
CombatEntered(attacker_id: PlayerId, defender_slot: int)
CombatRollResult(attacker_id, defender_slot, roll, evade, is_hit)
MonsterDied(attacker_id: PlayerId, slot_index: int, card_ref: CardRef)
PlayerDied(player_id: PlayerId, slot_index: int)
RewardGranted(player_id: PlayerId, cents: int)
SoulGranted(player_id: PlayerId, card_ref: CardRef)

# New model types:
MonsterInPlay(card_ref, base_hp, current_hp, evade, reward_cents, has_soul)
    .is_alive() -> bool
    .take_damage(amount: int) -> None

CombatState(attacker_id, defender_slot, monster_ref, is_active=True)

# New card catalog (foursouls/cards/monsters.py):
FLY, GAPER, SPIDER, HORF: CardId
MonsterDef(card_id, base_hp, evade, reward_cents, has_soul)   # frozen dataclass
make_monster_in_play(card_ref: CardRef) -> MonsterInPlay

# Game field added:
Game.combat: Optional[CombatState]   # None when no combat is active

# New ruleset hooks (rulesets/common/combat.py):
enter_combat(game: Game, slot_index: int) -> None
resolve_roll(game: Game) -> None
resolve_monster_death(game: Game) -> None
resolve_player_death(game: Game) -> None

# New agent:
agents.combat_bot.choose_command(game: Game) -> Command
```

---

### 4) Behavioral rules implemented

- **Attack legality:** `AttackMonster(slot_index)` is legal only when: phase is ACTION, stack is empty, `game.zones` is set, slot is occupied, `turn_flags.attack_used == False`, and `game.combat is None`. One command per occupied slot.
- **Combat entry:** `enter_combat` sets `attack_used = True`, creates `CombatState`, emits `CombatEntered`, resets priority to attacker.
- **Roll legality:** `RollCombat()` is legal only when `game.combat is not None and game.combat.is_active`, in ACTION phase with empty stack.
- **Roll resolution:** d6 roll; hit (`roll >= evade`) deals 1 damage to monster; miss deals 1 damage to attacker (clamped to 0). `CombatRollResult` emitted every roll. After each roll: monster death check, then player death check, then priority reset.
- **Monster death:** slot cleared → card to monster discard → slot refilled from deck if non-empty → `MonsterDied` → cent reward granted to attacker → soul card appended to `attacker.souls` if `has_soul` → `RewardGranted` and `SoulGranted` (when applicable) → combat cleared → priority reset. `RewardGranted` is always emitted (even when `cents == 0`).
- **Player death:** combat cleared → `PlayerDied` → priority reset. Monster stays in slot with current hp. Turn continues; player must issue `EndTurn` explicitly. No reward is granted on player death.
- **HP floors:** player hp clamped to 0 in `resolve_roll`; monster hp clamped to 0 in `MonsterInPlay.take_damage`.
- **Attack-used reset:** `attack_used` is reset to `False` by `TurnFlags.reset()` inside `reset_for_new_turn()` at `EndTurn`. This applies regardless of whether combat ended by monster death, player death, or neither (e.g., `EndTurn` during active combat clears `game.combat`).
- **Combat cleared on EndTurn:** `on_end_turn` explicitly sets `game.combat = None` before entering START phase, ensuring no stale combat context carries over.

**Ambiguities picked:**
- Turn continues after player death (player still issues `EndTurn`). Forced-end-of-turn on player death is not implemented; the spec leaves this explicit and minimal.
- `RewardGranted` fires even when `cents == 0` (e.g., FLY). This keeps the event stream uniform — listeners do not need a nil-reward special case.
- Soul is an owned `CardRef` in `PlayerState.souls`. No win-condition check against soul count is implemented.

---

### 5) Critical decisions

| Decision | Choice | Why |
|---|---|---|
| `CombatState` on `Game`, not `GameState` | `game.combat: Optional[CombatState]` | Combat is engine-managed runtime context (like zones), not serialisable player state. Mirrors how `zones` is stored. |
| Roll logic is immediate (no stack) | `resolve_roll` mutates hp directly | Combat rolls have no response window in base Four Souls. Stacking them would add latency and complexity with no rules payoff at this scope. |
| Monster death and rewards in one function | `resolve_monster_death` grants cents + soul | Atomic: either both happen or neither. Prevents partial-grant states if an exception occurs mid-cleanup. |
| `RewardGranted` always emitted | Even when `cents == 0` | Uniform event stream. Observers (UI, logging) don't need a special nil-reward branch. |
| Soul is `List[CardRef]` on `PlayerState` | Not a counter | Preserves card identity for future effects that care which soul you hold (e.g., "sacrifice a soul"). |
| `_drive_p1_turn` breaks on `turn_number` change | Not on `active_player_id != P1` | Single-player games keep P1 active forever; turn_number is the universal termination signal. |
| Player death: turn continues | Explicit EndTurn required after death | Spec says "explicit and tested". Forced end-of-turn would complicate the test harness and conflict with future "die but survive" effects. |

---

### 6) Tests added/updated

**New test files:**
- `tests/test_monster_scaffold.py` — 17 tests: `make_monster_in_play` stats for FLY/GAPER/SPIDER, default/None card_id fallback, `current_hp == base_hp` invariant, `take_damage` clamp, `is_alive` at boundary, setup integration (slots populated, zone isolation, determinism)
- `tests/test_attack_legality.py` — 11 tests: positive cases (one command per slot, multiple slots), negative cases (wrong phase, non-empty stack, empty slot, `attack_used`, no zones), dispatch sets `attack_used`, second attack blocked, reset on `EndTurn`
- `tests/test_combat_entry.py` — 17 tests: `CombatState` attacker/slot/monster_ref/is_active, quota set, second attack illegal, `CombatEntered` event fields, priority reset, phase/hp/cents/monster-hp/other-flag isolation, combat cleared on `EndTurn`
- `tests/test_monster_death.py` — 21 tests: slot cleared, combat ends, `RollCombat` illegal after death, `MonsterDied` event emitted once with correct fields, no event on surviving monster, card ref in discard, slot refill paths (deck non-empty/empty/neighbor unchanged), deck shrinks by 1, determinism, full multi-hp kill sequence
- `tests/test_player_death.py` — 19 tests: combat cleared, `RollCombat` illegal after death, monster hp/slot unchanged, `attack_used` True, `PlayerDied` event once with correct fields, no event on surviving player, no double-trigger, `EndTurn` legal, phase unchanged, priority on attacker, hp == 0 before EndTurn heals, multi-miss path
- `tests/test_kill_rewards.py` — 22 tests: cents added, zero-reward unchanged, `RewardGranted` always emitted, event fields, exactly-once per kill, multi-hp kill, soul in list, soul ref matches monster, `SoulGranted` event fields, exactly-once per soul kill, no soul for non-soul monster, `SoulGranted` absent for non-soul, registry-backed FLY/GAPER/HORF assertions, isolation (other player unaffected)
- `tests/test_sprint4_acceptance.py` — 24 tests: win path (combat ends, slot refills, reward, soul, events, attack_used mid-turn, turn advances), death path (combat cleared, monster unchanged, no rewards, `PlayerDied`, `EndTurn` legal, turn advances), attack-used resets (after win, after death, on P1's second turn), two full integration targets

**Updated test files:**
- `tests/test_sprint4_loop.py` — `test_player_hp_never_goes_below_zero`: removed second roll (now illegal after player death); assertion updated to `assert g.combat is None`

**Not yet covered (known gaps):**
- Treasure/character combat interactions (damage modifiers, rerolls, extra attacks)
- Multi-player targeting (who can attack whom)
- Win condition check on soul count
- Full death penalty (item discard on death, re-spawn location)
- Boss/room card type

---

### 7) Current demo path

```
pytest -q tests/test_sprint4_acceptance.py::test_sprint4_integration_full_win_flow
pytest -q tests/test_sprint4_acceptance.py::test_sprint4_integration_full_death_flow
```

Win path walkthrough:
1. `setup_game(seed=42)` — decks shuffled, Loot1 queued for P1; slot 0 injected with hp=1, evade=1, reward_cents=7, has_soul=True
2. `pass_bot` drives START → ACTION
3. `combat_bot` picks `AttackMonster(0)` → `CombatState` created, `attack_used=True`
4. `combat_bot` picks `RollCombat()` → roll ≥ 1 always → hit → monster hp 0 → `resolve_monster_death`
5. Slot cleared; refilled from deck; P1 gains 7 cents and 1 soul; `MonsterDied` + `RewardGranted` + `SoulGranted` emitted
6. `combat_bot` picks `EndTurn` → P1 healed, P2 active, turn 2, flags reset
7. `pass_bot` drives P2's turn; P1's second turn: `attack_used=False`, monster slot occupied, `AttackMonster` legal

Death path walkthrough:
1. Same setup; slot 0 injected with hp=5, evade=7, reward_cents=10, has_soul=True; P1 max_hp=1
2. P1 attacks → `RollCombat()` → roll ≤ 6 always → miss → P1 hp 0 → `resolve_player_death`
3. `PlayerDied` emitted; `game.combat = None`; monster unchanged; no reward/soul
4. `EndTurn` legal → P2 active; P1's second turn: healed to max_hp=1, `attack_used=False`

---

### 8) Problems / open questions

- **No win condition:** `PlayerState.souls` is a list but nothing checks soul count against a win threshold. Sprint 5 or later.
- **Death penalty deferred:** Player death has no consequence beyond `hp=0` and combat ending. Item loss, re-spawn, and penalty cents are all out of scope.
- **Flat evade:** Monster evade is a minimum roll, not a modifier. No character stats (attack, luck) affect the roll yet.
- **No targeting choice for multi-monster games:** `AttackMonster` generates one command per occupied slot; the player picks the slot. No forced-target rules exist.
- **Inherited open questions from Sprint 3:** Inert treasures; flat `TREASURE_COST`; fizzled loot limbo; Bomb self-target only.

---

## Older sprints

- [Sprint 3](changelogs/sprint3.md) — Shop
- [Sprint 2](changelogs/sprint2.md) — Loot Play + Character Abilities
- [Sprint 1](changelogs/sprint1.md) — Setup + Phase Machine + EndTurn
- [Sprint 0](changelogs/sprint0.md) — Priority Kernel
