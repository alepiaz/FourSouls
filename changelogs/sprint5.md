# Sprint 5 — CLI + Event Enrichment + Win Condition

---

## 1) Sprint / commit context

**Sprint:** Sprint 5  
**What's done vs partial:**

Done:
- R5.0 — Event system refactor: `Event.__post_init__` auto-sets `name` via class name; all manual `__init__` boilerplate removed from every event subclass; events reorganised into labelled sections; new events across all game phases; renamed `TreasureBought → ShopBought` and `RewardGranted → CoinsGained`
- R5.1 — Win condition: `SOULS_TO_WIN = 4` constant; `GameWon` emitted when attacker's soul count reaches threshold after a kill; `DamageDealt` event on every combat roll (hit and miss); `CoinsGained(reason=...)` and `CoinsSpent(reason=...)` replace flat reward/buy events
- R5.2 — Legal action query API: `LegalAction` dataclass (`key`, `kind`, `description`, `command`, `metadata`); `get_legal_actions(game)` top-level function; `Game.get_legal_actions()` convenience method; `StepResult(events)` wrapper replaces bare list return from `Game.step()`
- R5.3 — CLI: `foursouls/cli/` package; `render.py` pure-display functions; `controller.py` I/O layer; `app.py` game factory (`build_demo_game`) and interactive `run()` loop; `__main__.py` entry point (`python -m foursouls.cli`)
- R5.4 — Character catalog: `cards/characters.py` with `ISAAC`, `MAGDALENE`, `CAIN`, `EVE` CardId constants; `build_demo_game` assigns characters from this pool
- Phase auto-advance: after any stack resolution that empties the stack, `on_all_passed_empty_stack` is called automatically; START→ACTION now requires one pass-pair, not two
- Heal-all at EndTurn: `on_end_turn` heals all players (not just the active one) and resets all monsters in slots back to `base_hp`

Partial / skipped:
- No treasure card effects (bought items are inert; `_treasure_deck` uses placeholder `CardRef` with no `card_id`)
- No `AttackDeclared` event wired in the game loop (event class defined but never emitted — reserved for a future response window before combat entry)
- No CLI persistence (no save/load)
- Win condition checks only soul count; no "game over" lockout — steps after `GameWon` are technically still legal
- Character stats (HP pool, attack, luck) are not differentiated; all characters have the same uniform 4 HP in `build_demo_game`

---

## 2) Files changed

**New files**

- `foursouls/engine/actions.py` — `LegalAction(key, kind, description, command, metadata)`; `get_legal_actions(game) -> List[LegalAction]`; per-command builders for all seven command types; fallback for unknown commands
- `foursouls/cards/characters.py` — `ISAAC`, `MAGDALENE`, `CAIN`, `EVE` as `CardId` constants
- `foursouls/cli/__init__.py` — empty package marker
- `foursouls/cli/__main__.py` — `python -m foursouls.cli` entry point
- `foursouls/cli/app.py` — `_loot_deck()` (40 cards), `_treasure_deck()` (12 placeholders), `_monster_deck()` (16 cards: FLY×6, GAPER×4, SPIDER×4, HORF×2); `build_demo_game(player_ids, seed)`; `run(game)`; `main()` console-script entry
- `foursouls/cli/render.py` — `pretty_name(card_id_str)`; `render_header`, `render_player_row`, `render_hand`, `render_monsters`, `render_shop`, `render_combat`, `render_stack`, `render_actions`; `render_event` (narrative line per event type, covers all 20+ event types); `render_events`; `render_board` (full assembly)
- `foursouls/cli/controller.py` — `display_board`, `display_events`; `prompt_action` (accepts numeric index or stable key or `q`); `prompt_num_players`, `prompt_player_name`, `prompt_seed`
- `tests/test_legal_actions.py` — 34 tests: structure parity (command count, kind matching), PassPriority key/description, EndTurn key, PlayLoot (metadata: card_id, card_name, instance_id; one per card; unique keys), BuyShop (metadata; absent when broke), AttackMonster (metadata: name/hp/evade; one per slot), RollCombat (metadata: monster + attacker stats), ActivateCharacterAbility (metadata: card_id), `game.get_legal_actions()` delegation, all descriptions non-empty

**Modified files**

- `foursouls/engine/events.py` — `Event.name` now a `field(init=False)` set in `__post_init__`; removed all per-subclass `__init__`; added `GameSetupCompleted`, `TurnStarted`, `LootPlayed`, `CardDrawn`, `CardDiscarded`, `ItemActivated`, `ShopBought`, `CoinsGained`, `CoinsSpent`, `AttackDeclared`, `DamageDealt`, `GameWon`; enriched `CombatEntered` (`monster_id`, `monster_name`, `monster_hp`, `monster_evade`), `MonsterDied` (`monster_name`, `reward_cents`, `had_soul`), `PlayerDied` (`monster_name`), `SoulGranted` (`card_name`); renamed `TreasureBought → ShopBought`, `RewardGranted → CoinsGained`
- `foursouls/engine/game_loop.py` — `StepResult(events: List[Event])` dataclass; `Game.step()` returns `StepResult` instead of `list[Event]`; `Game.get_legal_actions()` method; post-resolution auto-advance: if stack empty after resolve, calls `on_all_passed_empty_stack`; `ItemActivated` emitted in `ActivateCharacterAbility` dispatch
- `foursouls/rulesets/common/combat.py` — `SOULS_TO_WIN = 4`; `CombatEntered` enriched with monster stats; `DamageDealt` emitted on hit and miss in `resolve_roll`; `RewardGranted` replaced by `CoinsGained(reason="monster_kill")`; `MonsterDied`/`PlayerDied`/`SoulGranted` enriched with name fields; win-condition check + `GameWon` after monster death
- `foursouls/rulesets/common/effects.py` — `DrawLoot1Effect` accepts optional `log: EventLog`; emits `CardDrawn` per drawn card when log provided; `PlayLootEffect` accepts optional `player_id` and `log`; emits `CardDiscarded` on apply when both provided
- `foursouls/rulesets/common/loot.py` — `LootPlayed` emitted at the start of `on_play_loot`; `PlayLootEffect` constructed with `player_id` and `log`
- `foursouls/rulesets/common/setup.py` — `GameSetupCompleted` emitted at the end of `setup_game()`
- `foursouls/rulesets/common/shop.py` — `TreasureBought` replaced by `CoinsSpent(reason="shop_buy")` + `ShopBought(item_name=...)`
- `foursouls/rulesets/common/turn.py` — `TurnStarted` emitted in `enter_start_phase()`; `DrawLoot1Effect` receives `log`; `on_end_turn` heals all players (loop over `state.players.values()`); monsters in all filled slots reset to `base_hp`
- `tests/test_turn.py` — `test_after_loot1_resolves_and_all_passed_phase_becomes_action`: now needs only one pass-pair (auto-advance); `test_end_turn_advances_player_and_phase_start_and_queues_loot1`: P2 also healed; `test_monsters_heal_to_full_at_end_of_turn` (new); `test_character_untaps_at_start_of_own_turn`: reduced pass steps
- `tests/test_buy_shop.py` — `TreasureBought → ShopBought`; `.events` on step result
- `tests/test_kill_rewards.py` — `RewardGranted → CoinsGained`; `.events` on step results
- `tests/test_sprint4_acceptance.py` — `RewardGranted → CoinsGained`; `.events` on step results
- All other modified test files (`test_activated_abilities.py`, `test_attack_legality.py`, `test_combat_entry.py`, `test_game_pass_window.py`, `test_legality.py`, `test_loot_play.py`, `test_monster_death.py`, `test_player_death.py`, `test_sprint1_loop.py`, `test_sprint2_loop.py`, `test_sprint4_loop.py`, `test_windows_fizzle.py`) — `.events` suffix added to `g.step(...).events` call sites; no logic changes

---

## 3) Public API changes

```python
# New return type for Game.step():
StepResult(events: List[Event])    # was: list[Event]
result = game.step(cmd)
result.events                      # access events

# New method:
Game.get_legal_actions() -> List[LegalAction]

# New module: foursouls.engine.actions
LegalAction(key, kind, description, command, metadata: dict)
get_legal_actions(game: Game) -> List[LegalAction]

# New events (engine/events.py):
GameSetupCompleted(player_ids, starting_hand_size, shop_size, monster_slot_count)
TurnStarted(turn_number, player_id)
LootPlayed(player_id, card_id, card_name)
CardDrawn(player_id, card_ref, source)
CardDiscarded(player_id, card_id, card_name, zone)
ItemActivated(player_id, source)
ShopBought(player_id, card_ref, item_name, slot_index, cost)   # was TreasureBought
CoinsGained(player_id, cents, reason)                          # was RewardGranted
CoinsSpent(player_id, amount, reason)
AttackDeclared(player_id, monster_slot, monster_id, monster_name)  # defined, not yet wired
DamageDealt(source_player_id, source_monster_slot, target_player_id, target_monster_slot, amount, reason)
GameWon(player_id, soul_count)

# Enriched existing events:
CombatEntered(attacker_id, defender_slot, monster_id, monster_name, monster_hp, monster_evade)
MonsterDied(attacker_id, slot_index, card_ref, monster_name, reward_cents, had_soul)
PlayerDied(player_id, slot_index, monster_name)
SoulGranted(player_id, card_ref, card_name)

# New card catalog:
foursouls.cards.characters: ISAAC, MAGDALENE, CAIN, EVE  (CardId constants)

# CLI entry point:
python -m foursouls.cli           # interactive game
from foursouls.cli.app import build_demo_game, run
game = build_demo_game(["Alice", "Bob"], seed=42)
run(game)
```

---

## 4) Behavioral rules implemented

- **Win condition:** after `resolve_monster_death`, if `len(attacker.souls) >= SOULS_TO_WIN` (4), `GameWon` is emitted. The game loop does not enforce a hard stop — the CLI checks for `GameWon` in `result.events` and exits the loop. The engine keeps accepting commands until the caller acts on the signal.
- **Phase auto-advance:** when `AllPlayersPassed` resolves the top stack item and the stack becomes empty, `on_all_passed_empty_stack` is called immediately in the same step. START→ACTION no longer requires a second empty-stack pass cycle.
- **Heal-all at EndTurn:** `on_end_turn` now iterates over all players and heals each to `max_hp`. Monsters in occupied slots also reset to `base_hp`. This is relevant when a player dies mid-turn and the turn ends with the monster still damaged.
- **Event auto-name:** `Event.name` is no longer a constructor argument. `__post_init__` sets it from `type(self).__name__`. Subclasses cannot accidentally name themselves differently from their class.
- **`StepResult` wrapper:** `game.step(cmd)` returns `StepResult` (not `list`). Access events via `.events`. The wrapper reserves room for future fields (warnings, illegal reason, timing).

**Ambiguities picked:**
- `GameWon` is a signal, not a lock. The caller (CLI or agent) is responsible for stopping. This keeps the engine minimal and testable without needing a "game over" state machine.
- `DamageDealt` is emitted on both hit and miss regardless of whether death follows. Downstream listeners (UI, analytics) can always compute total damage without inspecting `CombatRollResult`.
- `CoinsGained` fires even when `cents == 0` (inherited from Sprint 4 decision). `reason` field now disambiguates source (e.g., "monster_kill" vs future "loot_card").

---

## 5) Critical decisions

| Decision | Choice | Why |
|---|---|---|
| `StepResult` instead of bare list | Wrap events in a dataclass | Preserves call-site stability for future additions (warnings, illegal reasons) without a breaking change. |
| Auto-advance after stack resolves | Call `on_all_passed_empty_stack` when stack goes empty | Removes a conceptually meaningless second pass cycle from START. Every existing test that relied on the double cycle was updated. |
| Win condition in engine, not in CLI | `GameWon` event emitted by `resolve_monster_death` | Engine stays authoritative. CLIs, agents, and tests can all detect victory by checking events without external logic. |
| Heal-all (not just active player) | Loop over `state.players.values()` | All players need clean HP state at turn boundaries for multi-player correctness. Healing only the active player was an existing bug surfaced by this sprint. |
| `AttackDeclared` defined but not wired | Class exists; no emit in `game_loop.py` | Reserved for a future response window between attack declaration and `CombatState` creation. Wiring it now without a resolution path would create dangling priority state. |
| CLI is pure I/O + factory | `render.py` has no `print`; `controller.py` owns all I/O | Enables future GUI replacement without touching display logic. |
| `pretty_name` in `render.py` | Static `_CARD_NAMES` dict | Sufficient for current card set. Not generalised to a registry because no dynamic cards exist yet. |

---

## 6) Tests added/updated

**New test files:**
- `tests/test_legal_actions.py` — 34 tests: structure parity (count, kind), PassPriority (key, description), EndTurn (key), PlayLoot (7 tests: presence, key encoding, metadata fields, one-per-card, unique keys), BuyShop (6 tests: presence, absent-when-broke, key, metadata), AttackMonster (5 tests: presence, key, metadata hp/evade/name, one-per-slot), RollCombat (4 tests: presence, key, metadata), ActivateCharacterAbility (3 tests: presence, key, metadata), `game.get_legal_actions()` delegation, all descriptions non-empty

**Updated test files:**
- `tests/test_turn.py` — `test_after_loot1_resolves_and_all_passed_phase_becomes_action`: two passes now auto-advance to ACTION (removed extra pass pair); `test_end_turn_advances_player_and_phase_start_and_queues_loot1`: P2 damage asserted healed; `test_character_untaps_at_start_of_own_turn`: pass steps reduced; `test_monsters_heal_to_full_at_end_of_turn` (new): place damaged monster, run EndTurn, assert `current_hp == base_hp`
- `tests/test_buy_shop.py` — `TreasureBought → ShopBought`; `g.step(...).events`
- `tests/test_kill_rewards.py` — `RewardGranted → CoinsGained`; `.events`
- `tests/test_sprint4_acceptance.py` — `RewardGranted → CoinsGained`; `.events`
- `tests/test_combat_entry.py`, `test_monster_death.py`, `test_player_death.py`, `test_sprint4_loop.py`, `test_game_pass_window.py`, `test_sprint1_loop.py`, `test_sprint2_loop.py`, `test_windows_fizzle.py`, `test_activated_abilities.py`, `test_attack_legality.py`, `test_legality.py`, `test_loot_play.py` — `.events` suffix only; no logic changes

**Not yet covered (known gaps):**
- No CLI integration tests (render output, controller input parsing)
- No `GameWon` post-state test (engine keeps accepting commands; no lockout)
- `AttackDeclared` event has no test (not wired)
- Treasure buy effects remain inert (no test for item-in-play effects)

---

## 7) Current demo path

```
python -m foursouls.cli
```

Interactive walkthrough:
1. Enter number of players (1–4) and names; enter RNG seed (blank = 0).
2. Board displays: turn/phase/priority header, all player rows (HP, coins, souls, hand size, character), active player's hand, monster zone (HP/evade/reward/soul), shop zone (cost), combat callout if active, stack state, numbered action menu.
3. Pick action by number or stable key (e.g. `attack:0`, `roll_combat`, `pass`, `end_turn`); `q` quits.
4. Events from the step print as a short narrative (e.g. `> P1 attacks Gaper!`, `> Rolled 4 vs evade 2 -- HIT!`, `> Gaper dies!  +3c  [soul claimed!]`).
5. Loop repeats until `GameWon` is detected in `result.events`.

```
# Programmatic
from foursouls.cli.app import build_demo_game, run
game = build_demo_game(["Alice", "Bob"], seed=42)
run(game)
```

---

## 8) Problems / open questions

- **No game-over lock:** `GameWon` is a signal in the event stream. Nothing prevents further `step()` calls after it. A hard `game.is_over` flag is a natural Sprint 6 addition.
- **`AttackDeclared` is dead code:** defined in `events.py` but never emitted. Either wire it (requires a priority window before combat entry) or remove it. Deferred deliberately.
- **Treasure items are inert:** bought items are `CardRef` placeholders with no stats or effects. Item-in-play interactions (passive bonuses, active abilities) are out of scope.
- **Character HP not differentiated in CLI:** `build_demo_game` gives all players 4 HP regardless of character. MAGDALENE (6 HP), EVE (2 HP) etc. are not respected.
- **Inherited open questions from Sprint 4:** flat evade (no character attack/luck modifier), no multi-player targeting rules, full death penalty deferred, no boss/room card type.
