# Changelog

---

## Sprint 2 — Loot Play + Character Abilities

### 1) Sprint / commit context

**Sprint:** Sprint 2  
**What's done vs partial:**

Done:
- S2.0 — `setup_game()` auto-enters START phase; no external bootstrap call needed
- S2.1 — `TurnFlags.loot_play_used: bool` → `loot_plays_used: int` + `loot_plays_allowed: int`
- S2.2 — `ItemInPlay` model; `character` field on `PlayerState`; recharge on turn start
- S2.3 — `PlayLoot(card_ref)` command; dynamic legality from hand + quota
- S2.4 — `ActivateCharacterAbility` command; tap cost paid at activation; `GrantExtraLootPlayEffect`
- S2.5 — `GainCentsEffect`, `DealDamageEffect`, `PlayLootEffect` wrapper; `CardRef.card_id`; card catalog; `on_play_loot` handler; discard after resolution
- S2.6 — Tests for response windows, fizzle path, tap-cost guarantees, end-to-end extra-loot flow
- Architectural fix — `legal_commands` signature changed from `(state, stack)` to `(game: Game)`
- Sprint 2 acceptance tests — `test_sprint2_loop.py` with 11 named acceptance tests + integration target

Partial / skipped:
- Bomb targets controller (self) only; no real target selector yet
- No "card in-play zone" between play and resolution; fizzled loot stays in limbo
- Shop purchase, monster combat, rewards, souls remain out of scope

---

### 2) Files changed

**New files**

- `foursouls/model/item_in_play.py` — `ItemInPlay(card_ref, is_tapped=False)` with `tap()` / `untap()`
- `foursouls/cards/__init__.py` — package marker
- `foursouls/cards/loot.py` — `LOOT_COIN_1/2/3`, `BOMB` card ID constants; `make_loot_effect(card_id, controller_id)` factory
- `foursouls/rulesets/common/loot.py` — `on_play_loot(game, card_ref)`: removes card from hand, increments quota, builds `PlayLootEffect`, pushes to stack, resets priority
- `tests/test_activated_abilities.py` — 9 tests for `ActivateCharacterAbility` legality and mechanics
- `tests/test_loot_play.py` — 9 tests for `PlayLoot` dispatch, effects, discard, and quota
- `tests/test_windows_fizzle.py` — 17 tests for response windows, fizzle path, extra-loot integration, tap-cost guarantees
- `tests/test_sprint2_loop.py` — 11 acceptance tests + integration target

**Modified files**

- `foursouls/model/commands.py` — added `PlayLoot(card_ref)`, `ActivateCharacterAbility()`; added `CardRef` import
- `foursouls/model/player_state.py` — added `character: Optional[ItemInPlay] = None`
- `foursouls/model/phase.py` — `TurnFlags`: replaced `loot_play_used: bool` with `loot_plays_used: int = 0` and `loot_plays_allowed: int = 1`; `reset()` restores both to defaults
- `foursouls/model/refs.py` — `CardRef` gains `card_id: Optional[CardId] = None`; backward-compatible
- `foursouls/rulesets/common/effects.py` — added `GainCentsEffect`, `DealDamageEffect`, `PlayLootEffect` wrapper, `GrantExtraLootPlayEffect`; added `DiscardZone` and `Effect` imports
- `foursouls/rulesets/common/legality.py` — signature changed to `legal_commands(game: Game)`; added `PlayLoot` generation (hand × quota check) and `ActivateCharacterAbility` generation (character exists + not tapped); `Game` imported under `TYPE_CHECKING` to avoid circular import
- `foursouls/rulesets/common/setup.py` — calls `enter_start_phase(game)` before returning; added `enter_start_phase` import
- `foursouls/rulesets/common/turn.py` — `enter_start_phase` now untaps the active player's character before pushing Loot1
- `foursouls/engine/game_loop.py` — `step()` handles `PlayLoot` (calls `on_play_loot`) and `ActivateCharacterAbility` (tap + push `GrantExtraLootPlayEffect` + reset priority); `legal_commands()` now passes `self`; added imports
- `foursouls/rulesets/base_rules.py` — signature changed to `legal_commands(self, game: Game)`; `Game` imported under `TYPE_CHECKING`
- `tests/test_legality.py` — `_state()` helper replaced with `_game()` returning `Game(state=gs)`; all `legal_commands(state, Stack())` calls updated to `legal_commands(game)`; added `PlayLoot` and `ActivateCharacterAbility` legality tests
- `tests/test_turn.py` — removed manual `enter_start_phase` calls (now handled by `setup_game`); added `test_character_untaps_at_start_of_own_turn`, `test_character_with_no_character_does_not_crash`
- `tests/test_sprint1_loop.py` — removed `enter_start_phase` import and two manual calls
- `tests/test_state_init.py` — updated `TurnFlags` assertions from `bool` to `int` fields; reset test now sets and verifies `loot_plays_used` and `loot_plays_allowed`

---

### 3) Public API changes

```python
# Signature changed (game replaces state + stack):
BaseRuleset.legal_commands(game: Game) -> list[Command]
legal_commands(game: Game) -> list[Command]   # module-level, rulesets/common/legality.py

# New commands:
PlayLoot(card_ref: CardRef, kind="PLAY_LOOT")          # frozen dataclass
ActivateCharacterAbility(kind="ACTIVATE_CHARACTER_ABILITY")  # frozen dataclass

# New effects (rulesets/common/effects.py):
GainCentsEffect(player_id, amount)           # validate=True always
DealDamageEffect(player_id, amount)          # validate=True always; hp clamped to 0
PlayLootEffect(card_ref, inner, loot_discard)  # delegates validate to inner; discards card in apply
GrantExtraLootPlayEffect(player_id)          # validate=True always; loot_plays_allowed += 1

# New model types:
ItemInPlay(card_ref: CardRef, is_tapped: bool = False)
    .tap() -> None
    .untap() -> None

# CardRef extended (backward-compatible):
CardRef(instance_id: InstanceId, card_id: Optional[CardId] = None)

# TurnFlags fields changed:
TurnFlags.loot_plays_used: int    # was loot_play_used: bool
TurnFlags.loot_plays_allowed: int  # new; default 1, resets to 1 each turn

# PlayerState field added:
PlayerState.character: Optional[ItemInPlay]  # default None

# Card catalog (foursouls/cards/loot.py):
LOOT_COIN_1, LOOT_COIN_2, LOOT_COIN_3, BOMB: CardId
make_loot_effect(card_id: CardId, controller_id: PlayerId) -> Effect

# New ruleset hook (rulesets/common/loot.py):
on_play_loot(game: Game, card_ref: CardRef) -> None
```

---

### 4) Behavioral rules implemented

- **Auto-bootstrap:** `setup_game()` calls `enter_start_phase` before returning. Callers never need to do this manually.
- **Loot quota:** Each turn starts with `loot_plays_used=0`, `loot_plays_allowed=1`. `PlayLoot` is legal only when `loot_plays_used < loot_plays_allowed`. Each `PlayLoot` increments `loot_plays_used` at play time (not resolution time).
- **PlayLoot flow:** card removed from hand → `loot_plays_used += 1` → `PlayLootEffect` pushed to stack → priority reset to active player (response window opens) → on full pass cycle, inner effect resolves and card is added to `loot_discard`.
- **Fizzle path:** if `PlayLootEffect.inner.validate()` returns False, `EffectFizzled` is emitted, `apply` is never called, and the card remains in limbo (not in hand, not in discard). No Sprint 2 loot card is expected to reach this path in normal play.
- **Tap cost:** `ActivateCharacterAbility` is legal only in ACTION phase with empty stack when the active player's character exists and `is_tapped=False`. The tap is paid when the command is submitted (before the effect resolves). Cost is irreversible within the turn.
- **Extra loot play:** `GrantExtraLootPlayEffect` resolves through the stack like any other effect — a full pass cycle is required. On resolution, `loot_plays_allowed += 1`.
- **Recharge timing:** At the start of a player's turn (inside `enter_start_phase`), their character is untapped before Loot1 is pushed. This means characters recharge at "start of own turn", which is consistent with the Four Souls rule.
- **Card identity:** `CardRef` now carries an optional `card_id: CardId`. Placeholder cards (all existing tests) keep `card_id=None`. Real cards in the catalog always have a `card_id`.

**Ambiguities picked:**
- Bomb targets the controller (self-damage). No target selector exists yet. This is the simplest correct behavior for Sprint 2 until targeting is introduced.
- Loot quota is consumed at play time, not resolution time. A fizzled loot burns a quota slot.
- `loot_plays_allowed` resets to `1` (not `0`) on `TurnFlags.reset()`. The default of 1 is the rule, not 0.

---

### 5) Critical decisions

| Decision | Choice | Why |
|---|---|---|
| `legal_commands` takes `Game` | Changed from `(state, stack)` to `(game: Game)` | Legality needs full runtime state: hand, tapped items, stack, phase. Passing state+stack was already limiting in S2. |
| Circular import solution | `TYPE_CHECKING` guard in `legality.py` and `base_rules.py` | `game_loop → base_rules → legality → game_loop` cycle; same pattern already used in `turn.py`. |
| Tap cost timing | Paid at activation, not resolution | Standard TCG rule. Prevents "I activate, someone removes the source, cost refunded" exploits. |
| Quota model instead of bool | `loot_plays_used / loot_plays_allowed` | Accommodates "play additional loot" from any source without hacking around a boolean. Directly extensible. |
| `PlayLootEffect` wrapper | Wraps inner effect; handles discard | Keeps `GainCentsEffect` and `DealDamageEffect` pure (no zone knowledge). The wrapper is the only place that touches `loot_discard`. |
| `on_play_loot` in `rulesets/common/loot.py` | Separate handler module | Consistent with `on_end_turn` in `turn.py`. Keeps `game_loop.step()` as a thin dispatcher. |
| `ItemInPlay` in model | Separate file, not inlined into `PlayerState` | Same structure will hold treasures in Sprint 3. One definition used everywhere. |
| Recharge in `enter_start_phase` | Not in `on_end_turn` | Recharge belongs to the start of the new player's turn, not the end of the old player's turn. Semantically cleaner and easier to add "recharge prevention" effects later. |
| Fizzled loot stays in limbo | Accepted known gap | No "card in-play zone" exists yet. Sprint 2 has no naturally-fizzling loot cards. Will be fixed when a real in-play zone is introduced. |

---

### 6) Tests added/updated

**New test files:**
- `tests/test_activated_abilities.py` — 9 tests: legality gates (no char, tapped, wrong phase), tap-on-activation, stack push, quota increment after resolution, end-to-end extra loot unlock
- `tests/test_loot_play.py` — 9 tests: coin gives 1 cent, bomb deals 1 damage, damage clamp, hand removal on play, discard timing (not before resolution), quota increment, quota exhaustion blocks second play, extra-quota allows second play
- `tests/test_windows_fizzle.py` — 17 tests across four classes: `TestResponseWindow` (stack gating, pass cycle timing, priority owner, label encoding), `TestFizzle` (event fired, card in limbo, state unchanged, quota burned), `TestExtraLootIntegration` (activate → play × 2 → 2 cents, third play blocked, quota resets on EndTurn), `TestTapCost` (cost before resolution, blocks reactivation while unresolved, blocks after resolution, recharges on own next turn)
- `tests/test_sprint2_loop.py` — 11 acceptance tests + `test_sprint2_integration_full_flow`

**Updated test files:**
- `tests/test_legality.py` — replaced `_state()`+`Stack()` pattern with `_game()` returning `Game(state=gs)`; all `legal_commands` call sites updated; added `PlayLoot` legality tests (6 cases) and `ActivateCharacterAbility` legality tests (3 cases)
- `tests/test_turn.py` — removed 3 manual `enter_start_phase` calls; updated docstring; added `test_character_untaps_at_start_of_own_turn`, `test_character_with_no_character_does_not_crash`
- `tests/test_sprint1_loop.py` — removed `enter_start_phase` import and 2 manual calls
- `tests/test_state_init.py` — `TurnFlags` assertions updated: `loot_play_used is False` → `loot_plays_used == 0` and `loot_plays_allowed == 1`; reset test verifies both fields
- `tests/test_activated_abilities.py` — 6 `legal_commands(g.state, g.stack)` calls updated to `legal_commands(g)`

**Not yet covered (known gaps):**
- Fizzled loot recovery (card currently stays in limbo)
- Bomb with a real target selector
- `DrawLoot1Effect` fizzle in a real game (deck exhausted mid-turn)
- Hand trim at exactly 10 cards (boundary)

---

### 7) Current demo path

```
pytest -q tests/test_sprint2_loop.py::test_sprint2_integration_full_flow
```

Verbal walkthrough:
1. `setup_game(seed=42)` — decks shuffled, hands dealt (3 each), shop filled (3), monsters filled (2), Loot1 queued for P1
2. PASS / PASS → Loot1 resolves (P1 draws 1 loot); PASS / PASS → START → ACTION
3. P1 plays `LOOT_COIN_1` → `PlayLootEffect` pushed; PASS / PASS → 1 cent gained, card discarded
4. P1 activates character → character tapped, `GrantExtraLootPlay` pushed; PASS / PASS → `loot_plays_allowed = 2`
5. P1 plays `LOOT_COIN_2` → PASS / PASS → 2nd cent gained, card discarded
6. P1 ends turn → healed to max, turn_number = 2, P2 becomes active, quota reset, Loot1 queued for P2
7. P2 starts with `loot_plays_used=0`, `loot_plays_allowed=1`; P1's character still tapped (P2's turn)

---

### 8) Problems / open questions

- **Limbo gap:** A fizzled `PlayLootEffect` leaves the card between zones (removed from hand, not added to discard). Requires a proper "in-play zone" to fix cleanly. No Sprint 2 card reaches this path in practice.
- **Bomb self-target:** Bomb always damages the controller. A target selector (choose player or monster) is deferred until Sprint 3+ when monster slots have real HP state.
- **Single `ActivateCharacterAbility` command:** Hardcoded to "tap for extra loot". Generalizing to arbitrary character abilities (spending cents, dealing damage, etc.) is a Sprint 3+ concern.
- **Next sprint dependencies:** Shop needs a `BuyCard` command and a cent-deduction cost path. Combat needs monster HP state, an attack declaration, and dice rolls. Souls need ownership tracking.

---

## Older sprints

- [Sprint 1](changelogs/sprint1.md) — Setup + Phase Machine + EndTurn
- [Sprint 0](changelogs/sprint0.md) — Priority Kernel
