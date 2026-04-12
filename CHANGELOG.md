# Changelog

---

## Sprint 11 — Treasure Card Effects + Starting Eternal Items (R11.1)

### R11.1 — TreasureDef skeleton + ActivateItem command + player.items promotion

**What's done:**
- `TreasureDef` dataclass in `foursouls/cards/treasures.py`; card-ID constants for all Sprint 11 treasure cards and starting Eternals
- `ActivateItem(instance_id: InstanceId)` command in `foursouls/model/commands.py`
- `ItemInPlay` gains `recharge_on: str = "start_of_turn"` and `counters: Dict[str, int]` fields
- `player.items` promoted from `List[CardRef]` to `List[ItemInPlay]`; `gain_treasure` wraps `CardRef` in `ItemInPlay(card_ref=..., eternal=...)`
- Death penalty (step 1) now correctly filters for non-eternal items; `DeathPenaltyPaid.item_destroyed` remains `Optional[CardRef]` (extracted from the removed `ItemInPlay`)
- All affected callsites updated: `combat.py`, `render.py`; all affected tests updated: `test_r72_death_penalty.py`, `test_shop_state.py`, `test_monster_scaffold.py`, `test_buy_shop.py`, `test_sprint3_loop.py`

**Partial / deferred:**
- `TreasureDef` hooks (`on_enters_play`, `on_roll`, etc.) are defined but no cards wire them up yet — that happens in R11.2+
- `ActivateItem` legality and resolution not yet implemented

---

## Sprint 11 — R11.2: ActivateItem infrastructure + Mama Mega + Yum Heart

**What's done:**
- `ActivateItem(instance_id, target)` — target field added; legality emits one command per valid target (none / player / player_or_monster) based on `TreasureDef.tap_target_type`
- `TreasureDef` gains `tap_target_type: Optional[str]` and `make_tap_effect: Callable[[target, game], Effect]`
- `TREASURE_REGISTRY: Dict[CardId, TreasureDef]` in `foursouls/cards/treasures.py` for engine lookup
- `AoDamageEffect(amount, monster_slots)` — deals damage to all players and all monsters
- `PreventDamageToMonsterEffect(slot_index, amount, monster_slots)` — adds shield to a monster
- `TreasureActivateEffect` — wrapper: applies inner effect, destroys item if `is_one_use`
- `on_activate_item` in `foursouls/rulesets/common/items.py` — taps item, builds effect, pushes stack
- `ActivateItem` dispatch added to `game_loop.py`
- `on_end_turn`: untaps items with `recharge_on == "end_of_turn"` for the player whose turn just ended
- `enter_start_phase`: untaps items with `recharge_on == "start_of_turn"` for the new active player
- `MAMA_MEGA_DEF` (one-use, no-target, AoDamage 3) and `YUM_HEART_DEF` (eternal, end_of_turn, player_or_monster prevent-1) defined
- 13 new acceptance tests in `tests/test_sprint11_acceptance.py`

**Partial / deferred:**
- Starting Eternal items assigned at setup (R11.3)
- Remaining card defs (Dry Baby, Eye Of Greed, Dead Cat, Tech X, Magic Mushroom, Meat!, Lucky Foot, Lil Battery, The D6, Sleight Of Hand, The Curse) — R11.3+

---

## Sprint 11 — R11.3: Starting Eternals + Dry Baby + Meat! + damage_cap

**What's done:**
- `CharacterDef.starting_eternal: Optional[CardId]`; registry maps Isaac→The D6, Magdalene→Yum Heart, Cain→Sleight Of Hand, Eve→The Curse
- `_assign_starting_eternals(game)` in `setup_game`: creates `ItemInPlay(eternal=True, recharge_on=...)` per player, copies `starting_counters`, fires `on_enters_play`
- `fire_on_enters_play(game, player_id, item)` and `fire_on_start_of_turn(game)` in `foursouls/rulesets/common/items.py`
- `on_buy_shop` fires `on_enters_play` for the newly acquired item
- `enter_start_phase` fires `fire_on_start_of_turn` (hook infrastructure for The Curse etc.)
- `damage_cap: int = 0` on `PlayerState` (0 = no cap); cap applied first in `DealDamageEffect`, `AllPlayersTakeDamageEffect`, `AoDamageEffect`
- `DRY_BABY_DEF` (`on_enters_play` sets `damage_cap=1`), `MEAT_BANG_DEF` (`on_enters_play` increments `attack_bonus`), `THE_D6_DEF` (eternal stub), `LUCKY_FOOT_DEF` (stub), `SLEIGHT_OF_HAND_DEF` (eternal stub), `THE_CURSE_DEF` (eternal stub)
- 10 new acceptance tests

**Partial / deferred:**
- Eye Of Greed `on_roll` hook, The Dead Cat counter absorption, Tech X paid effect, Magic Mushroom modal effect, Lil Battery `ItemTarget` — R11.4+
- Sleight Of Hand auto-shuffle + DeckTarget, The Curse `on_start_of_turn` auto-discard — R11.4+

---

## Sprint 10 — Loot Card Diversity + Targeting System

### 1) Sprint / commit context

**Sprint:** Sprint 10  
**What's done vs partial:**

Done:
- R10.1 — `PlayerTarget`, `MonsterTarget`, `AnyTarget` in `foursouls/model/target.py`; `PlayLoot.target: Optional[AnyTarget] = None`
- R10.2 — `BOMB` renamed to `Bomb!` (`BOMB_BANG`); `Gold Bomb!!` (`GOLD_BOMB_BANG_BANG`) added; `legal_commands()` emits one `PlayLoot` per valid target for targeted cards; `make_loot_effect` accepts `target`, `monster_slots`, `rng`, `loot_deck`, `log`
- R10.3 — `Soul Heart` card (`PreventDamageEffect`); `prevent_damage: int = 0` on `PlayerState` and `MonsterInPlay`; shield consumed by `DealDamageEffect`, `DealDamageToMonsterEffect`, and combat miss; resets at `EndTurn`
- R10.4 — `Blank Rune` card; `LootRollEffect(branches: Dict[int, Effect], rng)`; `AllPlayersGainCentsEffect`, `AllPlayersTakeDamageEffect`, `AllPlayersDrawLootEffect`; `Cursed Chest` and `We Need To Go Deeper!` event cards; `ResetAttackEffect`

Partial / skipped:
- `Gold Bomb!!` (`GOLD_BOMB_BANG_BANG`) is defined but not yet in the CLI loot deck (reserved for Sprint 11 item diversity)
- `Blank Rune` roll=6 (Guppy item search) is a stub no-op; deferred to Sprint 11
- Cursed Chest roll=6 is a stub no-op for the same reason

---

### 2) Files changed

**New files**

- `foursouls/model/target.py` — `PlayerTarget(player_id)`, `MonsterTarget(slot_index)`, `AnyTarget = Union[...]`
- `tests/test_sprint10_acceptance.py` — 16 tests covering all four releases (R10.1–R10.4)

**Modified files**

- `foursouls/cards/loot.py` — `BOMB → BOMB_BANG`; added `GOLD_BOMB_BANG_BANG`, `SOUL_HEART`, `BLANK_RUNE`; `requires_target()`, `allows_monster_target()` helpers; `make_loot_effect` extended with target/rng/loot_deck/log kwargs
- `foursouls/cards/monsters.py` — `CURSED_CHEST` and `WE_NEED_TO_GO_DEEPER` card IDs + blueprints + registry entries
- `foursouls/cli/app.py` — loot deck updated (`BOMB_BANG`, `SOUL_HEART`, `BLANK_RUNE`); monster deck gains `CURSED_CHEST`, `WE_NEED_TO_GO_DEEPER`
- `foursouls/cli/render.py` — display names for all new cards
- `foursouls/model/commands.py` — `PlayLoot.target: Optional[AnyTarget] = None`
- `foursouls/model/monster_in_play.py` — `prevent_damage: int = 0`; `take_damage` consumes shield before HP
- `foursouls/model/player_state.py` — `prevent_damage: int = 0`
- `foursouls/rulesets/common/combat.py` — combat miss consumes `prevent_damage` before HP
- `foursouls/rulesets/common/effects.py` — `DealDamageEffect` consumes shield; added `DealDamageToMonsterEffect`, `PreventDamageEffect`, `ResetAttackEffect`, `AllPlayersGainCentsEffect`, `AllPlayersTakeDamageEffect`, `AllPlayersDrawLootEffect`, `LootRollEffect`
- `foursouls/rulesets/common/legality.py` — targeted cards emit one `PlayLoot` per valid target (player or non-event monster slot)
- `foursouls/rulesets/common/loot.py` — `on_play_loot` forwards target, monster_slots, rng, loot_deck, log to `make_loot_effect`
- `tests/test_loot_play.py` — bomb tests updated: self-target → `PlayerTarget`; added monster-target test
- `tests/test_setup.py`, `tests/test_shop_state.py`, `tests/test_sprint3_loop.py`, `tests/test_windows_fizzle.py` — `BOMB → BOMB_BANG` rename
- `ROADMAP.md` — Sprint 10 releases marked ✅; Sprint 16 (priority auto-advance) added; future table renumbered

---

### 3) Public API changes

```python
# New module: foursouls.model.target
PlayerTarget(player_id: PlayerId)
MonsterTarget(slot_index: int)
AnyTarget = Union[PlayerTarget, MonsterTarget]

# Extended command:
PlayLoot(card_ref, target: Optional[AnyTarget] = None)

# New effects:
DealDamageToMonsterEffect(slot_index, amount, monster_slots, damage_type="ability")
PreventDamageEffect(player_id, amount)
ResetAttackEffect()
AllPlayersGainCentsEffect(amount)
AllPlayersTakeDamageEffect(amount, damage_type="ability")
AllPlayersDrawLootEffect(count, loot_deck, log=None)
LootRollEffect(branches: Dict[int, Effect], rng)

# New card IDs:
BOMB_BANG          # was BOMB
GOLD_BOMB_BANG_BANG
SOUL_HEART
BLANK_RUNE
CURSED_CHEST       # event card
WE_NEED_TO_GO_DEEPER  # event card

# New helpers in foursouls.cards.loot:
requires_target(card_id) -> bool
allows_monster_target(card_id) -> bool

# New fields:
PlayerState.prevent_damage: int    # damage shield; resets at EndTurn
MonsterInPlay.prevent_damage: int  # damage shield; resets at EndTurn
```

---

### 4) Behavioral rules implemented

- **Targeting:** `PlayLoot` carries an optional target. `legal_commands()` expands targeted cards into one command per valid target (both players + all non-event monster slots for bombs; players only for Soul Heart).
- **Bomb damage:** `Bomb!` deals 1 damage to the chosen `PlayerTarget` or `MonsterTarget`. `Gold Bomb!!` deals 3.
- **Damage prevention shield:** `prevent_damage` on player and monster absorbs incoming damage before HP. Consumed greedily per hit. Resets to 0 at `EndTurn` for all players and monsters.
- **Soul Heart:** adds 1 to the target player's `prevent_damage`.
- **Blank Rune:** rolls d6 and delegates to one of six branch effects (all-players cents gain, draw, or damage). Roll=6 stub is a no-op pending Sprint 11.
- **Cursed Chest (event):** rolls d6 on entry; 1–3 → 1 damage to active player; 4–5 → 2 damage; 6 → no-op stub.
- **We Need To Go Deeper! (event):** resets `turn_flags.attack_used = False`, allowing a second attack this turn.

---

### 5) Critical decisions

| Decision | Choice | Why |
|---|---|---|
| `target` optional on `PlayLoot` | `None` default | Untargeted cards (coins, Blank Rune) stay backward-compatible; callers don't supply a target |
| One `PlayLoot` per target in legality | Expand in `legal_commands()` | UI sees distinct selectable actions; engine routes by command identity |
| `prevent_damage` on both player and monster | Symmetric field | Simplifies `DealDamageToMonsterEffect` and future monster shield items |
| `LootRollEffect` holds the live `rng` | Captured at push time | Roll happens at resolution, not at play time — correct stack ordering |
| `DealDamageEffect.damage_type` | Added `"ability"` default | Separates ability damage from combat damage for future rule hooks |

---

### 6) Tests

16 tests added in `test_sprint10_acceptance.py`; 4 existing test files updated (BOMB→BOMB_BANG rename + new monster-target test). Full suite: 421 passed, 1 skipped.

---

### 7) Problems / open questions

- `Gold Bomb!!` not yet in the CLI demo deck; adding it is a one-liner once the deck composition is revisited.
- Blank Rune roll=6 and Cursed Chest roll=6 are no-ops; both need Guppy item search (Sprint 11).
- `AllPlayersDrawLootEffect` draws from a single shared loot deck — if the deck runs out mid-loop, later players get fewer cards. A reshuffle-on-empty hook is deferred.
- Death penalty item choice (destroy first item) is still deterministic; full player-chosen targeting deferred.

---

## Sprint 7 — Correct Player Death Penalty

### 1) Sprint / commit context

**Sprint:** Sprint 7  
**What's done vs partial:**

Done:
- R7.1 — `eternal: bool = False` on `ItemInPlay`; character items in `build_demo_game` created with `eternal=True`
- R7.2 — Four-step death penalty in `resolve_player_death`: destroy 1 non-eternal item, discard 1 loot, lose 1¢, untap all ↷ items; new `DeathPenaltyPaid` event
- R7.3 — Active-player death advances phase ACTION → END; `EndTurn` legal in END phase; all offensive actions remain ACTION-only; `PhaseChanged(END→START)` on EndTurn
- R7.4 — `died_this_turn: bool` on `TurnFlags`; set on death, cleared on new turn; guards against double-death trigger in same turn

Partial / skipped:
- Death penalty destroys first item (not player-chosen); full targeting deferred to Sprint 10
- Untap loop covers character only; treasure `ItemInPlay` wrappers not yet in place (Sprint 11)

---

### 2) Files changed

**New files**

- `tests/test_r71_eternal.py` — 5 tests: `eternal` default, setting True, tap orthogonality, `build_demo_game` characters eternal, freely constructed item not eternal
- `tests/test_r72_death_penalty.py` — 13 tests: event ordering, all four steps (happy path + edge cases), eternal character excluded from destroy pool, full four-step path
- `tests/test_r73_active_death_end_phase.py` — 14 tests: END phase after death, `PhaseChanged(ACTION→END)`, legality in END, EndTurn from END advances turn, full bot flow
- `tests/test_r74_died_this_turn.py` — 7 tests: default False, set on death, one-event guarantees, guard suppresses second trigger, reset on new turn, sprint-7 acceptance lifecycle

**Modified files**

- `foursouls/model/item_in_play.py` — `eternal: bool = False` added
- `foursouls/model/phase.py` — `died_this_turn: bool = False` on `TurnFlags`; cleared in `reset()`
- `foursouls/engine/events.py` — `DeathPenaltyPaid(player_id, item_destroyed, loot_discarded, cents_lost, items_deactivated)` added
- `foursouls/rulesets/common/combat.py` — `resolve_player_death`: full penalty, `died_this_turn=True`, active-player stack drain + END phase; `resolve_roll`: guard on `died_this_turn`
- `foursouls/rulesets/common/legality.py` — `EndTurn` legal in `Phase.ACTION` or `Phase.END`
- `foursouls/rulesets/common/turn.py` — capture `old_phase` before reset for accurate `PhaseChanged`
- `foursouls/cli/app.py` — character `ItemInPlay` constructed with `eternal=True`
- `tests/test_player_death.py` — phase-after-death assertion updated to `Phase.END`
- `tests/test_legality.py` — `test_end_turn_illegal_outside_action_phase` split into START (illegal) and END (legal) tests

---

### 3) Public API changes

```python
# New field on ItemInPlay:
ItemInPlay(card_ref, is_tapped=False, eternal=False)

# New field on TurnFlags:
turn_flags.died_this_turn: bool

# New event:
DeathPenaltyPaid(player_id, item_destroyed, loot_discarded, cents_lost, items_deactivated)

# Phase after active-player death:
game.state.phase == Phase.END   # EndTurn is now legal here
```

---

### 4) Behavioral rules implemented

- **Four-step death penalty** applied automatically in `resolve_player_death` (destroy item → discard loot → lose 1¢ → untap ↷ items). Each step degrades gracefully when there is nothing to consume.
- **Active-player death → END phase:** stack drained, `PhaseChanged(ACTION, END)` emitted, `phase = END`. Only `PassPriority` and `EndTurn` are legal. `EndTurn` from END advances the turn normally.
- **One death per turn:** `died_this_turn` flag prevents `resolve_player_death` from firing twice in one turn. Cleared by `TurnFlags.reset()` at turn boundary.

---

### 5) Critical decisions

| Decision | Choice | Why |
|---|---|---|
| `eternal` on `ItemInPlay` instance | Not on `CardRef` | Same card may be eternal as a starting item but not if obtained later |
| Only `player.items` in destroy pool | Never touch `player.character` | Character is always eternal; cleaner than checking the flag at destroy time |
| Explicit END phase (not auto-EndTurn) | Preserve explicit call site | Leaves room for future on-death triggers before the turn ends |
| `died_this_turn` on `TurnFlags` | Turn-scoped, not player-scoped | `TurnFlags.reset()` already handles all turn-boundary cleanup |

---

### 6) Tests

39 tests added (4 new files); 2 existing tests updated. Full suite: 392 passed.

---

### 7) Problems / open questions

- Death penalty item choice is deterministic (first in list), not player-chosen. Targeting deferred to Sprint 10.
- Untap loop covers character only; Sprint 11 adds tap-able treasure items.
- `AttackDeclared` still dead code; treasure items still inert; character HP not differentiated (all carried from Sprint 5).

---

## Sprint 6 — Win Condition & Game Termination

### 1) Sprint / commit context

**Sprint:** Sprint 6  
**What's done vs partial:**

Done:
- R6.1 — Heal timing confirmed: all players and all monsters heal to full at end of every turn
- R6.2 — `game_over: bool = False` on `Game`; `legal_commands()` → `[]`; `step()` → `ValueError`; `get_legal_actions()` → `[]`
- R6.3 — `game_over = True` triggered in `resolve_monster_death` when soul count ≥ 4; `GameWon` emitted
- R6.4 — CLI loop guard `while winner is None and not game.game_over`; `test_sprint6_acceptance.py`

Partial / skipped: nothing; all R6 releases complete.

---

### 2) Files changed

**New files**

- `tests/test_game_over.py` — 6 tests: `legal_commands/get_legal_actions == []` when `game_over`, `step()` raises `ValueError`, 4th soul kill sets flag, non-winning kill does not, non-soul kill does not
- `tests/test_sprint6_acceptance.py` — `combat_bot` pre-loaded with 3 souls kills guaranteed soul monster → `game_over=True`, `get_legal_actions()==[]`, one `GameWon` event

**Modified files**

- `foursouls/engine/game_loop.py` — `game_over: bool = False`; short-circuit in `legal_commands()`; guard in `step()`
- `foursouls/rulesets/common/combat.py` — `GameWon` + `game.game_over = True` in `resolve_monster_death`
- `foursouls/cli/app.py` — loop condition adds `and not game.game_over`

---

### 3) Public API changes

```python
game.game_over: bool           # False until win condition met
game.legal_commands()          # → [] when game_over
game.get_legal_actions()       # → [] when game_over
game.step(cmd)                 # → raises ValueError when game_over
GameWon(player_id, soul_count) # emitted on win
```

---

### 4) Behavioral rules implemented

- **Game-over lock:** `game_over=True` → no further commands. `step()` raises `ValueError`; CLI loop exits.
- **Win condition:** `resolve_monster_death` checks `len(attacker.souls) >= SOULS_TO_WIN` (4). `GameWon` emitted before `game_over` is set.

---

### 5) Tests

7 tests added (2 new files). Full suite at end of sprint: 353 passed.

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

- [Sprint 6](changelogs/sprint6.md) — Win Condition & Game Termination
- [Sprint 5](changelogs/sprint5.md) — CLI + Event Enrichment + Win Condition
- [Sprint 4](changelogs/sprint4.md) — Combat
- [Sprint 3](changelogs/sprint3.md) — Shop
- [Sprint 2](changelogs/sprint2.md) — Loot Play + Character Abilities
- [Sprint 1](changelogs/sprint1.md) — Setup + Phase Machine + EndTurn
- [Sprint 0](changelogs/sprint0.md) — Priority Kernel
