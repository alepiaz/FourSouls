# Changelog

---

## Sprint 5 — CLI + Event Enrichment + Win Condition

### 1) Sprint / commit context

**Sprint:** Sprint 5  
**What's done vs partial:**

Done:
- R5.0 — Event system refactor: `Event.__post_init__` auto-sets `name`; all manual `__init__` boilerplate removed; new events across all game phases; `TreasureBought → ShopBought`, `RewardGranted → CoinsGained`
- R5.1 — Win condition: `SOULS_TO_WIN = 4`; `GameWon` emitted when soul count reaches threshold; `DamageDealt` on every combat roll; `CoinsGained/CoinsSpent` replace flat reward/buy events
- R5.2 — Legal action query API: `LegalAction(key, kind, description, command, metadata)`; `get_legal_actions(game)`; `Game.get_legal_actions()`; `StepResult` wrapper replaces bare list return from `Game.step()`
- R5.3 — CLI: `foursouls/cli/` package with `render.py` (pure display), `controller.py` (I/O), `app.py` (factory + loop), `__main__.py`; `python -m foursouls.cli` launches interactive game
- R5.4 — Character catalog: `cards/characters.py` with `ISAAC`, `MAGDALENE`, `CAIN`, `EVE` CardId constants
- Phase auto-advance: after stack resolution empties the stack, `on_all_passed_empty_stack` fires automatically; START→ACTION needs one pass-pair, not two
- Heal-all at EndTurn: all players and all monsters in slots reset to full HP at `on_end_turn`

Partial / skipped:
- Treasure items are inert (no buy effects implemented)
- `AttackDeclared` event defined but not wired (reserved for future response window)
- No game-over lock — `GameWon` is a signal; engine keeps accepting commands
- Character HP stats not differentiated in CLI (`build_demo_game` gives everyone 4 HP)

---

### 2) Files changed

**New files**

- `foursouls/engine/actions.py` — `LegalAction` dataclass; `get_legal_actions(game)` enriches every legal command with display context; per-command builders for all seven command types
- `foursouls/cards/characters.py` — `ISAAC`, `MAGDALENE`, `CAIN`, `EVE` as `CardId` constants
- `foursouls/cli/__init__.py`, `__main__.py` — package + `python -m foursouls.cli` entry
- `foursouls/cli/app.py` — deck builders (40-card loot, 12-card treasure, 16-card monster); `build_demo_game(player_ids, seed)`; interactive `run()` loop with `GameWon` detection
- `foursouls/cli/render.py` — `pretty_name`; `render_header/player_row/hand/monsters/shop/combat/stack/actions`; `render_event` (narrative line for 20+ event types); `render_board` (full assembly)
- `foursouls/cli/controller.py` — `display_board/events`; `prompt_action` (numeric index or stable key or `q`); `prompt_num_players/player_name/seed`
- `tests/test_legal_actions.py` — 34 tests: structure parity, per-command key/kind/metadata/description coverage, `game.get_legal_actions()` delegation

**Modified files**

- `foursouls/engine/events.py` — `Event.name` via `__post_init__`; removed all `__init__` boilerplate; added `GameSetupCompleted`, `TurnStarted`, `LootPlayed`, `CardDrawn`, `CardDiscarded`, `ItemActivated`, `ShopBought`, `CoinsGained`, `CoinsSpent`, `AttackDeclared`, `DamageDealt`, `GameWon`; enriched `CombatEntered`, `MonsterDied`, `PlayerDied`, `SoulGranted`
- `foursouls/engine/game_loop.py` — `StepResult` wrapper; `Game.step()` returns `StepResult`; `Game.get_legal_actions()`; post-resolve auto-advance when stack empty; `ItemActivated` emitted on character tap
- `foursouls/rulesets/common/combat.py` — `SOULS_TO_WIN = 4`; `DamageDealt` on hit/miss; `CoinsGained` replaces `RewardGranted`; event fields enriched; `GameWon` after kill if threshold reached
- `foursouls/rulesets/common/effects.py` — `DrawLoot1Effect` emits `CardDrawn`; `PlayLootEffect` emits `CardDiscarded` (both via optional `log` param)
- `foursouls/rulesets/common/loot.py` — `LootPlayed` emitted in `on_play_loot`
- `foursouls/rulesets/common/setup.py` — `GameSetupCompleted` emitted at end of `setup_game()`
- `foursouls/rulesets/common/shop.py` — `CoinsSpent + ShopBought` replaces `TreasureBought`
- `foursouls/rulesets/common/turn.py` — `TurnStarted` emitted; all players + monsters heal at `on_end_turn`
- All test files — `.events` suffix added to `g.step(...).events` call sites; `TreasureBought → ShopBought`, `RewardGranted → CoinsGained` renames; `test_turn.py` reduced pass steps (auto-advance) and added two new assertions

---

### 3) Public API changes

```python
# Game.step() now returns StepResult:
result = game.step(cmd)
result.events                    # List[Event] (was the bare return value)

# New:
Game.get_legal_actions() -> List[LegalAction]

# New module: foursouls.engine.actions
LegalAction(key, kind, description, command, metadata: dict)
get_legal_actions(game: Game) -> List[LegalAction]

# Renamed events:
TreasureBought  →  ShopBought(player_id, card_ref, item_name, slot_index, cost)
RewardGranted   →  CoinsGained(player_id, cents, reason)

# New events:
GameSetupCompleted(player_ids, starting_hand_size, shop_size, monster_slot_count)
TurnStarted(turn_number, player_id)
LootPlayed(player_id, card_id, card_name)
CardDrawn(player_id, card_ref, source)
CardDiscarded(player_id, card_id, card_name, zone)
ItemActivated(player_id, source)
CoinsSpent(player_id, amount, reason)
DamageDealt(source_player_id, source_monster_slot, target_player_id, target_monster_slot, amount, reason)
GameWon(player_id, soul_count)

# Enriched events (new fields):
CombatEntered  +  monster_id, monster_name, monster_hp, monster_evade
MonsterDied    +  monster_name, reward_cents, had_soul
PlayerDied     +  monster_name
SoulGranted    +  card_name

# CLI:
python -m foursouls.cli
from foursouls.cli.app import build_demo_game, run
```

---

### 4) Behavioral rules implemented

- **Win condition:** `resolve_monster_death` checks `len(attacker.souls) >= SOULS_TO_WIN` and emits `GameWon`. Engine does not lock; CLI exits the loop on this event.
- **Phase auto-advance:** when a stack resolution empties the stack, `on_all_passed_empty_stack` runs in the same `step()` call. START→ACTION now costs one pass-pair (not two).
- **Heal-all at EndTurn:** `on_end_turn` heals every player to `max_hp` and every monster in a slot to `base_hp`. Fixes multi-player correctness and the player-dies-then-EndTurn scenario.
- **Event auto-name:** `Event.name == type(self).__name__` always; subclasses cannot diverge.
- **`StepResult` wrapper:** `step()` returns a dataclass, not a list. Existing call sites add `.events`; the wrapper leaves room for future fields without signature breakage.

---

### 5) Critical decisions

| Decision | Choice | Why |
|---|---|---|
| `StepResult` not bare list | Wrap in dataclass | Future-proof: can add warnings/illegal-reason without breaking call sites. |
| Auto-advance after stack resolves | Fire `on_all_passed_empty_stack` inline | Removes a meaningless second pass cycle from START; all affected tests updated. |
| `GameWon` is a signal, not a lock | Engine keeps accepting commands | Keeps the engine stateless and testable without a game-over guard. |
| Heal-all (all players + monsters) | Loop over all players | Multi-player correctness; the active-player-only heal was a latent bug. |
| `AttackDeclared` defined but not wired | Reserve for future | Wiring it requires a priority window before combat entry — scope mismatch for Sprint 5. |
| `render.py` has no `print` | Pure string returns | Decouples display from I/O; a future GUI swaps `controller.py` only. |

---

### 6) Tests added/updated

**New:**
- `tests/test_legal_actions.py` — 34 tests (see §2)

**Updated:**
- `tests/test_turn.py` — auto-advance reduces pass steps; all-player heal asserted; monster heal test added
- `tests/test_buy_shop.py` — `TreasureBought → ShopBought`
- `tests/test_kill_rewards.py` — `RewardGranted → CoinsGained`
- `tests/test_sprint4_acceptance.py` — same renames
- All other test files — `.events` suffix on `step()` results only

**Not yet covered:**
- CLI render output and controller input parsing
- `GameWon` post-state (no lockout)
- `AttackDeclared` (not wired)
- Treasure item effects

---

### 7) Current demo path

```
python -m foursouls.cli
```

Board displays turn/phase/priority, all players (HP/coins/souls/hand/character), hand with loot-plays remaining, monster zone, shop zone, active combat callout, stack state, numbered action menu. Pick by number, stable key (e.g. `attack:0`, `roll_combat`), or `q` to quit. Events print as narrative after each step. Loop exits when `GameWon` detected.

---

### 8) Problems / open questions

- **No game-over lock:** steps after `GameWon` remain legal. A `game.is_over` flag is a natural next addition.
- **`AttackDeclared` is dead code:** wiring requires a pre-combat priority window. Deferred.
- **Treasure items are inert:** `build_demo_game` uses placeholder `CardRef` with no `card_id`. Buy effects TBD.
- **Character HP not differentiated:** all characters get 4 HP in `build_demo_game`. MAGDALENE/EVE stat differentiation deferred.
- **Inherited from Sprint 4:** flat evade, no multi-player targeting, full death penalty deferred, no boss/room type.

---

## Older sprints

- [Sprint 4](changelogs/sprint4.md) — Combat
- [Sprint 3](changelogs/sprint3.md) — Shop
- [Sprint 2](changelogs/sprint2.md) — Loot Play + Character Abilities
- [Sprint 1](changelogs/sprint1.md) — Setup + Phase Machine + EndTurn
- [Sprint 0](changelogs/sprint0.md) — Priority Kernel
