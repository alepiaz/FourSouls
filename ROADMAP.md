## Status at a glance

| Sprint | Name | Status |
|--------|------|--------|
| 0 | Priority kernel | ✅ done |
| 1 | Setup + phases + EndTurn | ✅ done |
| 2 | Loot play + character abilities | ✅ done |
| 3 | Shop | ✅ done |
| 4 | Combat — attack, roll, death, rewards, souls | ✅ done |
| 5 | CLI + legal actions API + event enrichment | ✅ done |
| 6 | Win condition & game termination | ✅ done |
| 7 | Correct player death penalty | ✅ done |
| 8 | ATK stat & correct combat damage | ✅ done |
| 9 | Event cards in monster deck | ✅ done |
| 10 | Loot card diversity + targeting system | ✅ done |
| 11 | Treasure card effects + starting eternal items | ✅ done |
| 12 | Character stats and ability window | ✅ done |
| 13 | Monster abilities + expansion pack | ✅ R13.1–R13.7 merged via PR #4 |
| 13.5 | Ability architecture refactoring | 🔄 in progress — R13.5.1 complete |
| 14 | Combat miss on stack + cancel | 🔄 R14.1–R14.3 implemented; remaining scope open |
| 14.5 | Stabilization & integration | ✅ done — merged PR #3; CI passed |
| 15 | Dice on stack + roll control | 📋 planned |
| 16 | Cancel / response stack interaction | 📋 planned |
| 17 | Priority auto-advance | 📋 planned |
| 18 | Statistics pipeline | 📋 planned |
| 19 | Heuristic bot | 📋 planned |
| 20 | Trinkets + pile targeting | 🔮 future |
| 21 | Player interaction | 🔮 future |
| 22 | Curses + rooms | 🔮 future |
| 23 | Trigger queue | 🔮 future |
| 24 | Replacement effects | 🔮 future |
| 25 | Continuous effects + static ability layer | 🔮 future |

---

## Sprint 12 — Character stats and ability window
**Goal:** Correct character HP to 2 for all four characters and fix the legality window for the character tap ability.

All four base characters share the same stats and the same ↷ ability:

| Character | HP | ATK | Tap ability |
|---|---|---|---|
| ISAAC | 2 | 1 | Play an additional loot card this turn |
| MAGDALENE | 2 | 1 | Play an additional loot card this turn |
| CAIN | 2 | 1 | Play an additional loot card this turn |
| EVE | 2 | 1 | Play an additional loot card this turn |

The card text reads: *"This can be done on any player's turn in response to any action."* The `GrantExtraLootPlayEffect` resolution is already correct (implemented Sprint 2); what changes here is the legality gate and the HP values.

**Changes:**
- `CharacterDef.base_hp` corrected to 2 for ISAAC, MAGDALENE, CAIN (EVE was already 2); `_DEFAULT.base_hp` updated to 2.
- `legal_commands()` emits `ActivateCharacterAbility` for every player whose character is untapped, regardless of whose turn it is and whether the stack is empty (i.e. removed the `phase == ACTION and stack.empty()` guard for this specific command).

**Releases:**
- R12.1 — Character stat correction
- R12.2 — Character ability legality window
- R12.3 — Regression + acceptance

**Key files:** `foursouls/cards/characters.py`, `foursouls/rulesets/common/legality.py`

---

## Sprint 13 — Monster abilities + expansion pack
**Goal:** Add reusable monster trigger infrastructure, then implement the first wave of printed monster-text abilities.

| Monster | Trigger | Condition | Effect |
|---|---|---|---|
| GAPER | on_death | roll == 6 | Active player must make one additional attack on the monster deck |
| HORF | on_miss | roll == 2 | Combat damage dealt to attacker is increased by 1 |
| BIG_SPIDER | on_death | always | Active player may attack the monster deck an additional time |
| CARRION_QUEEN | on_would_take_combat_damage | roll == 4 or 5 | Prevent that combat damage |
| HEADLESS_HORSEMAN | on_would_die | first time per turn | Prevent death; heal 2 HP; gain +1 DC and −1 ATK until end of turn |
| BONY | on_attack_roll | roll == 1 | Gain +2 ATK until end of turn while in play |
| MEGA_FATTY | on_combat_damage_dealt | positive damage dealt | Heal 1 HP |

**New monster cards this sprint:**

| Card | Type | HP | DC | ATK | Potential Rewards | Effect |
|---|---|---:|---:|---:|---|---|
| BIG_SPIDER | Basic | 3 | 4 | 1 | 1 Loot | When this dies, the active player may attack the monster deck an additional time |
| CARRION_QUEEN | Boss | 3 | 4 | 1 | 1 Soul, 1 Treasure | This takes no combat damage on attack rolls of 4 or 5 |
| BONY | Basic | 2 | 3 | 1 | 1 Loot | Gain +2 ATK on each attack roll of 1 |
| MEGA_FATTY | Boss | 3 | 3 | 1 | 1 Soul, 2 Loot | Heal 1 HP whenever it deals combat damage |

**Infrastructure:**
- Store `last_combat_roll: int` on `CombatState` so ability checks can read the triggering roll value.
- `on_death: Optional[Callable[[Game, int], None]]` on `MonsterDef` (second arg = the roll); called from `resolve_monster_death` when set.
- `on_miss: Optional[Callable[[Game, int], int]]` on `MonsterDef` — returns modified damage amount; called in `resolve_roll` before applying miss damage.
- `on_would_take_combat_damage: Optional[Callable[[Game, int, int], int]]` on `MonsterDef` — called before combat damage is applied to the monster; returns the final damage amount.
- `on_would_die: Optional[Callable[[Game], bool]]` on `MonsterDef` — called before death resolves; returns `True` if death is prevented.
- `prevent_death_used: bool = False` on `MonsterInPlay`; set to `True` when triggered; reset at `EndTurn` for all monsters in play.
- `evade_bonus: int = 0` and `attack_bonus: int = 0` on `MonsterInPlay` for temporary modifiers; reset at `EndTurn`.
- GAPER `on_death`: if roll == 6, push a forced attack on the monster deck (no cost to attacker's `attack_used`).
- HORF `on_miss`: if roll == 2, return `monster.attack + 1`.
- BIG_SPIDER `on_death`: active player may attack the monster deck an additional time.
- CARRION_QUEEN `on_would_take_combat_damage`: if roll is 4 or 5, return 0 damage.
- HEADLESS_HORSEMAN `on_would_die`: if not `prevent_death_used`, heal +2 HP (capped at `base_hp`), apply `evade_bonus += 1` and `attack_bonus -= 1`, set flag; return `True` (prevent death). Combat continues.
- `MonsterTriggerFired` event with fields `card_id`, `trigger`, `roll`.

**Releases:**
- ✅ R13.1 — Monster trigger substrate
- ✅ R13.2 — Combat integration
- ✅ R13.3 — Printed monster abilities pack A (`GAPER`, `HORF`)
- ✅ R13.4 — Printed monster abilities pack B (`BIG_SPIDER`, `CARRION_QUEEN`)
- ✅ R13.5 — Boss trigger pattern (`HEADLESS_HORSEMAN`)
- ✅ R13.6 — Bony (Four Souls+ V2; attack-roll trigger)
- ✅ R13.7 — Mega Fatty (Base Game V2; combat-damage trigger)

**Completion note:** Separate forced and optional deck-attack allowances, reveal then select a slot, covered monster restoration and out-of-combat death prevention are implemented. The full declaration/priority timing, generalized triggers and zone identity rules remain separate roadmap work.

**Key files:** `foursouls/cards/monsters.py`, `foursouls/model/combat_state.py`, `foursouls/model/monster_in_play.py`, `foursouls/rulesets/common/combat.py`, `foursouls/engine/events.py`

---

## Sprint 13.5 — Ability architecture refactoring

**Goal:** Make common card abilities composable, data-driven and event-driven without replacing the existing command/priority/stack kernel. Introduce a shared ability foundation before completing Sprint 14 or starting Sprint 15. This sprint is distinct from release R13.5 (Headless Horseman).

**Depends on:** Sprint 13 merged and regression suite green; Sprint 14.5 already merged.

**Architecture:**
- Shared typed, immutable `AbilityDefinition` and runtime `AbilityInstance` / `AbilityContext` (source identity, controller, triggering event, selected targets, per-instance usage).
- Separate trigger, condition, cost, target selector, atomic effect and duration definitions. Use Pydantic discriminated schemas; no executable strings or arbitrary attribute traversal in YAML.
- Distinguish triggered, activated, static and replacement/prevention abilities; loot resolution may reuse effect primitives without being treated as a permanent ability.
- Typed domain events and an `EventDispatcher` / subscription registry keyed by event type. Keep the existing `EventLog` as an observation/replay surface, not the trigger mechanism. Emit events once from rule/effect resolution; record actual damage after prevention, resolved rolls and source/target identity.
- Zone-aware registration and removal of subscriptions; capture source/controller context when an ability triggers, including leave-play/death events. Use a stable per-zone-entry identity for target validity where required by migrated abilities.
- Generic condition, selector and effect registries; compose sequences of existing effects, with explicit duration and usage limits. Preserve custom Python handlers for genuinely exceptional behavior, not card-specific combinations of existing primitives.
- Minimal pending-trigger queue and deterministic ordering compatible with current priority windows; no recursive stack resolution. Minimal typed pre-event replacement/prevention pipeline for the existing monster abilities only. General simultaneous-order choices, universal replacement hooks and full static/continuous stats remain Sprints 23–25.
- Migrate incrementally, preserving existing public commands, bot behavior and tests. No card expansion in this sprint.

**Releases:**

| Release | Deliverable | Status |
|---|---|---|
| R13.5.1 | Shared ability definitions, runtime context and validated YAML schema | ✅ complete |
| R13.5.2 | Domain event dispatcher and zone-aware subscriptions | 📋 planned |
| R13.5.3 | Typed condition evaluator and event/source matching | 📋 planned |
| R13.5.4 | Shared effect registry and composable atomic effects | 📋 planned |
| R13.5.5 | Target resolution, identity, costs, durations and usage limits for current scope | 📋 planned |
| R13.5.6 | Minimal trigger queue and replacement/prevention adapter | 📋 planned |
| R13.5.7 | Migrate all seven Sprint 13 monsters; remove superseded specialized handlers and direct monster-ability dispatch from core | 📋 planned |
| R13.5.8 | Regression, composition and deterministic integration tests | 📋 planned |

**Acceptance criteria:**
- Gaper, Horf, Big Spider, Carrion Queen, Headless Horseman, Bony and Mega Fatty retain their existing verified behavior.
- A new combination of an existing trigger, condition and effect can be expressed in YAML without a new Python handler or changes to the game loop.
- Tests exercise multiple simultaneous subscriptions, covered/uncovered sources, death triggers, cancellation/fizzle, independent per-instance usage and duration cleanup.
- No duplicate dispatch or recursive resolution; same seed and commands yield the same state/events; all existing regression tests remain green on Python 3.11 and 3.12.
- Loot and treasure legacy paths remain compatible; migrate them when touched by later releases rather than broadening the sprint into a rewrite.

**Key files (proposed):** `foursouls/model/abilities.py`, `foursouls/engine/ability_engine.py`, `foursouls/engine/event_dispatcher.py`, existing effect/target/stack models and card YAML loaders.

---

## Sprint 14 — Combat miss on stack + cancel
**Goal:** Make combat miss damage a first-class stack item so players can respond before it resolves; introduce `StackItemTarget` and stack-item cancellation via Butter Bean.

**New cards this sprint:**

| Card | Type | Effect |
|---|---|---|
| BUTTER_BEAN | Loot | Cancel a stack item (loot being played, or item/loot ability on the stack) |

**New mechanics:**
- `CombatMissDamageEffect` pushed onto the stack when a roll misses instead of being applied synchronously; its `validate()` checks that combat is still active — if not, it fizzles.
- `StackItemTarget` — a new target type that identifies a live stack item by its stack ID; used by cancel effects.
- `prevent_damage: int` field on `MonsterInPlay`; `Soul Heart` can target a monster slot to grant `prevent_damage = 1`; `DealDamageToMonsterEffect` (Bomb) consumes `prevent_damage` before dealing damage.
- `CancelStackItemEffect(target: StackItemTarget)` — removes the targeted item from the stack without resolving it; fires `StackItemCancelled` event.
- Easy gap fills (from IMPL_STATUS [Easy]): `DestroyItemEffect`, `HealEffect`, `HealMonsterEffect`, `ForceAttackEffect` / `forced_attack_slot` on `TurnFlags`.

**Releases:**
- ✅ R14.1 — `CombatMissDamageEffect` on stack; fizzles if combat ends before it resolves
- ✅ R14.2 — `StackItemTarget`; `Soul Heart` targets monster slot (`prevent_damage`); `DealDamageToMonsterEffect` consumes `prevent_damage` first
- ✅ R14.3 — `BUTTER_BEAN` + `CancelStackItemEffect` + `StackItemCancelled` event
- R14.4 — `DestroyItemEffect` + `HealEffect` + `ForceAttackEffect` (remaining gap fills); `HealMonsterEffect` implemented in R13.7, integrate with shared effect registry
- R14.5 — RESERVED — `<insert cancel loot> card insertion A`
- R14.6 — Acceptance

**Depends on (remaining work):** Sprint 13.5; reuse shared ability/effect definitions rather than introducing parallel handlers.

**Key files:** `foursouls/rulesets/common/combat.py`, `foursouls/rulesets/common/effects.py`, `foursouls/model/target.py`, `foursouls/engine/actions.py`, `foursouls/cards/loot.py`

---

## Sprint 14.5 — Stabilization & integration

- Fix active-player vs priority-holder legality and item ownership.
- Discard cancelled and fizzled loot, including defensive stack cleanup.
- Populate demo decks with registered cards and remove duplicate effect class.
- Explicit package discovery and YAML package data.
- Add regression tests; require a passing full suite before declaring completion.
- Completed and merged via PR #3 (`c38b712`); CI passed. Mandatory deck attacks are addressed by Sprint 13; remaining ability infrastructure is scheduled for Sprint 13.5 and later sprints.

## Sprint 15 — Dice on stack + roll control
**Goal:** Make dice rolls first-class stack items so cards can respond to, reroll, or replace roll results. Also fixes `LootRollEffect` (currently resolves synchronously in `apply()`) to push the roll onto the stack and branch via a triggered ability.

**New cards this sprint:**

| Card | Type | Effect |
|---|---|---|
| DICE_SHARD | Loot — Dice Shard | Choose a dice roll. Its controller rerolls it |
| GODHEAD | Active Treasure | **↷ Effect** — Change the result of a dice roll to a 1 or 6 |

**New mechanics:**
- Dice rolls become real stack items.
- Rolls carry metadata: controller, source, and roll category (`"attack"` or `"non_attack"`).
- Reroll / modify / replace-result pipeline.
- Roll-response legality window.
- `LootRollEffect` refactored: roll pushed onto stack; branch selection triggered after roll resolves. [Hard]
- Branching roll abilities extend the shared Sprint 13.5 ability/effect schema (`RollAbilityDef` or equivalent adapter); do not introduce a parallel ability model. [Medium]
- `flip_roll()` helper: sets `roll.value = 7 - roll.value`; usable by any flip-a-roll card. [Easy]
- Circled-number trigger listening: triggered abilities that fire when a roll resolves with a specific value. [Easy]
- This sprint makes the Sprint 11 stubs for **The D6** and **Lucky Foot** functional.

**Releases:**
- R15.1 — Dice-on-stack infrastructure
- R15.2 — Roll-response framework + `LootRollEffect` refactor
- R15.3 — `RollAbilityDef` declarative model + `flip_roll()` helper
- R15.4 — Existing stubs become functional (`THE_D6`, `LUCKY_FOOT`)
- R15.5 — Roll-control card pack (`DICE_SHARD`, `GODHEAD`)
- R15.6 — RESERVED — `<insert dice shard> card insertion A`
- R15.7 — RESERVED — `<insert roll-control treasure> card insertion B`
- R15.8 — Acceptance

**Key files:** `foursouls/engine/game_loop.py`, `foursouls/model/stack.py`, `foursouls/rulesets/common/effects.py`, `foursouls/rulesets/common/combat.py`, `foursouls/cards/loot.py`, `foursouls/cards/treasures.py`

---

## Sprint 16 — Cancel / response stack interaction
**Goal:** Introduce the `NO` active treasure for targeted cancellation of item abilities while they are on the stack. (Loot cancellation via Butter Bean was shipped in Sprint 14.)

**New cards this sprint:**

| Card | Type | Effect |
|---|---|---|
| NO | Active Treasure | **↷ Effect** — Cancel the ↷ or $ ability of an item |

**New mechanics:**
- Stack items must expose enough metadata to distinguish:
  - loot being played
  - item tap abilities
  - item paid abilities
- Canceled stack items fizzle cleanly when resolved.
- Cancellation legality rules.

**Releases:**
- R16.1 — Cancelable stack-item substrate (item ability metadata)
- R16.2 — Cancel resolution for item abilities
- R16.3 — `NO` card
- R16.4 — Rules hardening
- R16.5 — RESERVED — `<insert cancel loot> card insertion A`
- R16.6 — RESERVED — `<insert cancel treasure> card insertion B`
- R16.7 — Acceptance

**Key files:** `foursouls/model/stack.py`, `foursouls/engine/game_loop.py`, `foursouls/rulesets/common/effects.py`, `foursouls/cards/treasures.py`

---

## Sprint 17 — Priority auto-advance
**Goal:** Players with no meaningful actions are automatically skipped. The engine runs to quiescence after every command — callers no longer drive a manual `PassPriority` loop.

**Rules:**
- A player with only `PassPriority` available is auto-skipped; priority advances to the next player.
- A player who *has* other actions may still explicitly pass priority without playing anything.
- After any priority reset, `Game._run_to_quiescence()` loops: auto-pass each player whose only legal command is `PassPriority()`, until someone has a real action or all have passed.
- If all pass, the existing resolution logic fires (resolve stack top, or call `on_all_passed_empty_stack`), then quiescence re-runs.
- `step()` returns only when a player with real choices holds priority, or when the game is over.
- Stack forced-pop cleanup: let the priority/resolution loop drain the stack naturally; no force-pops. [Medium, from IMPL_STATUS]

**Impact:** All existing tests that manually drive `PassPriority` pairs to resolve a stack item need updating — the stack resolves automatically inside `step(PlayLoot(...))`. Tests simplify from three calls to one.

**Releases:**
- R17.1 — `_run_to_quiescence()` core
- R17.2 — Preserve explicit pass for meaningful-choice states
- R17.3 — Simplify CLI/tests/API expectations
- R17.4 — RESERVED — `<insert reactive loot> card insertion A`
- R17.5 — RESERVED — `<insert interrupt treasure> card insertion B`
- R17.6 — Acceptance / regression pass

**Key files:** `foursouls/engine/game_loop.py`

---

## Sprint 18 — Statistics pipeline
**Goal:** A headless batch runner plays N games and records structured per-game statistics.

**New module `foursouls/sim/`:**
- `runner.py` — `run_game(game, agents) -> GameRecord`; `max_turns=500` guard emitting `GameTimeout`
- `batch.py` — `run_batch(n, factory, agents, seed_start=0) -> List[GameRecord]`
- `stats.py` — `summarise(records) -> dict` with win rates, mean/median turn count, timeout rate
- `__main__.py` — `python -m foursouls.sim --games 1000 --players 2 --seed 0`

**`GameRecord` fields:** `winner_id`, `turn_count`, `souls_per_player`, `items_bought_per_player`, `damage_taken_per_player`

**Releases:**
- R18.1 — `GameRecord` schema
- R18.2 — Headless runner
- R18.3 — Batch + summary
- R18.4 — RESERVED — `<insert benchmark monster> card insertion A`
- R18.5 — RESERVED — `<insert benchmark treasure/loot> card insertion B`
- R18.6 — Acceptance

**Key files:** `foursouls/sim/` (new package)

**Acceptance test:** 20 games with `combat_bot` vs `combat_bot`; all complete without timeout; `summarise()` returns `win_rates` and `mean_turns`.

---

## Sprint 19 — Heuristic bot
**Goal:** A scoring-based bot demonstrably outperforms `combat_bot` (≥55% win rate over 500 games).

**Scoring function per action kind:**
- `RollCombat`: `reward/10 + has_soul*5 - evade/6 * (1/hp)`
- `AttackMonster`: prefer soul monsters; among equal, prefer reward/evade ratio
- `BuyShop`: score by `TreasureDef.archetype` weighted by game state (low HP → HP items; late game → attack items)
- `PlayLoot`: expected value (coin=face, heal=HP_deficit*0.5, draw=1.0)
- `ActivateCharacterAbility` / `ActivateItem`: contextual (heal if HP < max/2; buff if in combat)
- `EndTurn`: 0.0; `PassPriority`: −0.1

**New files:** `agents/heuristic_bot.py`; `foursouls/sim/compare.py` (`head_to_head(n, factory, agent_a, agent_b) -> CompareResult`)

**Releases:**
- R19.1 — Feature extraction from legal actions
- R19.2 — First scoring policy
- R19.3 — Compare harness + tuning
- R19.4 — RESERVED — `<insert bot-facing monster> card insertion A`
- R19.5 — RESERVED — `<insert bot-facing treasure/loot> card insertion B`
- R19.6 — Acceptance

**Acceptance test:** `head_to_head(500, factory, heuristic_bot, combat_bot)` → `heuristic_win_rate >= 0.55`.

---

## Sprint 20 — Trinkets + pile targeting
**Goal:** Introduce trinket loot-to-item transition and the pile/discard browsing mechanics needed for deferred effects.

**Releases:**
- R20.1 — `PileTarget` / pile browsing substrate
- R20.2 — Trinket lifecycle (`is_trinket` flag, `TrinketResolveEffect`) [Easy from IMPL_STATUS]
- R20.3 — First trinket pack + complete *We Need To Go Deeper!*
- R20.4 — RESERVED — `<insert trinket> card insertion A`
- R20.5 — RESERVED — `<insert trinket> card insertion B`
- R20.6 — Acceptance

---

## Sprint 21 — Player interaction
**Goal:** Add give/steal/swap mechanics between players.

**Releases:**
- R21.1 — Ownership transfer infrastructure (`StealItemEffect`) [Medium from IMPL_STATUS]
- R21.2 — Interaction legality + resolution
- R21.3 — First interaction card pack
- R21.4 — RESERVED — `<insert interaction loot> card insertion A`
- R21.5 — RESERVED — `<insert interaction treasure> card insertion B`
- R21.6 — Acceptance

---

## Sprint 22 — Curses + rooms
**Goal:** Add the two remaining persistent side-system families after the stack and targeting architecture are stable.

**Releases:**
- R22.1 — Curse state model + lifecycle (`is_curse` flag, `PlayerState.curses`, discard-on-death hook) [Easy from IMPL_STATUS]
- R22.2 — Room deck + room slot + lifecycle [Complex from IMPL_STATUS]
- R22.3 — First curse/room pack
- R22.4 — RESERVED — `<insert curse> card insertion A`
- R22.5 — RESERVED — `<insert room> card insertion B`
- R22.6 — Acceptance

---

## Sprint 23 — Trigger queue
**Goal:** Extend the Sprint 13.5 dispatcher and minimal pending-trigger queue to all triggered abilities, with full rules-compliant timing and controller/turn ordering; retire remaining synchronous trigger adapters.

**Gaps covered (from IMPL_STATUS):**
- Trigger queue system [Complex] — enqueue instead of execute-immediately; all trigger sites updated
- Simultaneous trigger ordering [Complex] — sorted by game-controlled-first + turn order
- Declared ability hooks (attack/purchase triggers) [Complex]
- End-of-turn triggered abilities [Complex]
- Circled-number triggers (fully generalised) — reads `resolved_value` from roll stack item

**Depends on:** Sprint 13.5 foundation and Sprints 14–16 (stable stack/response architecture)

**Releases:**
- R23.1 — Extend Sprint 13.5 trigger queue substrate to all applicable event types
- R23.2 — Enqueue all existing triggers
- R23.3 — Ordering + simultaneous resolution
- R23.4 — EOT and declaration hooks
- R23.5 — Circled-number trigger generalisation
- R23.6 — Acceptance / regression pass

**Key files:** `foursouls/engine/game_loop.py`, `foursouls/engine/events.py`, `foursouls/model/stack.py`, all card definitions with triggered effects

---

## Sprint 24 — Replacement effects
**Goal:** Generalize the Sprint 13.5 replacement/prevention adapter to all "would happen" events (damage, gain, death) so cards can intercept and modify outcomes before they resolve.

**Gaps covered (from IMPL_STATUS):**
- Replacement effect system [Complex] — hook all "would happen" events; collect applicable effects; prompt for ordering; refactor all damage/gain/entry sites
- Damage-on-stack integration [Hard] — first-class `DamageStackItem` for prevention between declaration and marking
- Death as stack item [Hard] — universal HP-reaches-0 observer queuing deaths at priority

**Depends on:** Sprint 23 (trigger queue)

**Releases:**
- R24.1 — Extend shared replacement protocol and add universal hook sites
- R24.2 — `DamageStackItem` + prevention pipeline
- R24.3 — Death-as-stack-item
- R24.4 — Ordering prompt for simultaneous replacements
- R24.5 — Acceptance / regression pass

**Key files:** `foursouls/engine/game_loop.py`, `foursouls/rulesets/common/combat.py`, `foursouls/rulesets/common/effects.py`

---

## Sprint 25 — Continuous effects + static ability layer
**Goal:** Complete static/continuous execution on the shared ability model; derive stats (ATK, HP, evasion) on demand rather than direct field mutations. Generalize Sprint 13.5 duration handling.

**Gaps covered (from IMPL_STATUS):**
- Continuous effect layer [Complex] — maintain list of `ContinuousEffect` objects with endpoints; replace direct stat mutations; remove on source leave-play
- Static ability layer [Hard] — universal infrastructure; query derived stats from in-play static abilities
- HP/ATK counter recalculation passes [Medium] — `recalculate_hp(target)` and `recalculate_attack(target)` helper passes

**Depends on:** Sprint 24 (replacement effects)

**Releases:**
- R25.1 — `ContinuousEffect` data model + registry
- R25.2 — Derived-stat query functions (replace direct field reads)
- R25.3 — Static ability infrastructure
- R25.4 — Counter recalculation passes
- R25.5 — Acceptance / regression pass

**Key files:** `foursouls/model/`, `foursouls/engine/game_loop.py`, all card definitions with static/continuous abilities

---

## Mechanics placed in existing sprints

| Mechanic | Sprint | Notes |
|---|---|---|
| Generic ability model / event dispatcher / subscriptions | 13.5 | Shared foundation for future cards |
| Condition / selector / effect composition | 13.5 | YAML-only combinations of known primitives |
| Minimal trigger queue and replacement adapter | 13.5 | Migrated monster abilities; expanded in 23–24 |
| Combat miss damage on stack | 14 | First step toward full dice-on-stack |
| Stack-item targeting (`StackItemTarget`) | 14 | Required by Butter Bean and cancel effects |
| `DestroyItemEffect` / `HealEffect` | 14 | Easy gap fills from IMPL_STATUS |
| Dice as stack items | 15 | Required for rerolls and roll replacement |
| Roll category tagging | 15 | `"attack"` vs `"non_attack"` |
| `LootRollEffect` stack refactor | 15 | Fixes synchronous branch-in-apply() |
| `RollAbilityDef` declarative model | 15 | Replaces ad-hoc roll callbacks |
| The D6 reroll tap | 15 | Previously stubbed in Sprint 11 |
| Lucky Foot roll modification | 15 | Previously stubbed in Sprint 11 |
| Cancellation of item abilities | 16 | `NO` card; loot cancel already in Sprint 14 |
| Quiescence auto-run | 17 | Removes manual pass loops from most callers |
| Statistics batch runner | 18 | Requires stable engine API |
| Heuristic comparison harness | 19 | Depends on stats pipeline |
| Trinket zone transition | 20 | Loot resolving into `ItemInPlay` |
| `PileTarget` browsing | 20 | Needed for delayed pile-selection effects |
| Player give/steal/swap | 21 | Depends on mature targeting/runtime ownership |
| Curses / rooms | 22 | Deferred until core stack/response systems are stable |
| Full trigger queue system | 23 | Extend 13.5 foundation; all trigger sites updated |
| Replacement effect system | 24 | Depends on trigger queue |
| Continuous effects layer | 25 | Depends on replacement effects |

---

## Ordering rationale

- Sprint 12 remains a pure rules/correction sprint and therefore has no card insertions.
- Sprint 13 expands monster ability coverage before deeper stack interaction grows more complex.
- Sprint 13.5 is the next development milestone: extract reusable ability primitives and event subscriptions from the seven verified monsters before completing Sprint 14 and proceeding to Sprint 15. Sprint 14.5 is already shipped.
- Sprint 14 takes the first stack-items step (combat miss damage + cancel) before full dice-on-stack; Butter Bean is the simplest cancel and earns a response-window before rolls are fully on the stack.
- Sprint 15 follows naturally: once a non-roll item is on the stack, making dice rolls proper stack items is the next step; Sprint 11 roll stubs (D6, Lucky Foot) become functional here.
- Sprint 16 deepens cancellation to item abilities (`NO`) once the stack/cancel infrastructure from Sprint 14 is proven.
- Sprint 17 comes after stack-response depth increases, so quiescence can stabilize the full priority model.
- Sprint 18 precedes Sprint 19 because the bot needs a measurement framework.
- Sprint 20 introduces trinkets and pile targeting only after the runtime item model is mature.
- Sprint 21 adds direct player interaction after targeting and ownership systems have already expanded.
- Sprint 22 keeps curses and rooms before foundational refactors, as a final card-content sprint on the current architecture.
- Sprints 23–25 complete and generalize the shared foundations introduced in Sprint 13.5. Full timing, ordering, universal replacement and derived-stat semantics remain explicit later deliverables, not duplicated infrastructure.
