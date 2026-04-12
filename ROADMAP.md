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
| 13 | Monster abilities + expansion pack | 📋 planned |
| 14 | Dice on stack + roll control | 📋 planned |
| 15 | Cancel / response stack interaction | 📋 planned |
| 16 | Priority auto-advance | 📋 planned |
| 17 | Statistics pipeline | 📋 planned |
| 18 | Heuristic bot | 📋 planned |
| 19 | Trinkets + pile targeting | 🔮 future |
| 20 | Player interaction | 🔮 future |
| 21 | Curses + rooms | 🔮 future |

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

**New monster cards this sprint:**

| Card | Type | HP | DC | ATK | Potential Rewards | Effect |
|---|---|---:|---:|---:|---|---|
| BIG_SPIDER | Basic | 3 | 4 | 1 | 1 Loot | When this dies, the active player may attack the monster deck an additional time |
| CARRION_QUEEN | Boss | 3 | 4 | 1 | 1 Soul, 1 Treasure | This takes no combat damage on attack rolls of 4 or 5 |

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
- R13.1 — Monster trigger substrate
- R13.2 — Combat integration
- R13.3 — Printed monster abilities pack A (`GAPER`, `HORF`)
- R13.4 — Printed monster abilities pack B (`BIG_SPIDER`, `CARRION_QUEEN`)
- R13.5 — Boss trigger pattern (`HEADLESS_HORSEMAN`)
- R13.6 — RESERVED — `<insert monster> card insertion A`
- R13.7 — RESERVED — `<insert boss monster> card insertion B`

**Key files:** `foursouls/cards/monsters.py`, `foursouls/model/combat_state.py`, `foursouls/model/monster_in_play.py`, `foursouls/rulesets/common/combat.py`, `foursouls/engine/events.py`

---

## Sprint 14 — Dice on stack + roll control
**Goal:** Make dice rolls first-class stack items so cards can respond to, reroll, or replace roll results.

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
- This sprint makes the Sprint 11 stubs for **The D6** and **Lucky Foot** functional.

**Releases:**
- R14.1 — Dice-on-stack infrastructure
- R14.2 — Roll-response framework
- R14.3 — Existing stubs become functional (`THE_D6`, `LUCKY_FOOT`)
- R14.4 — Roll-control card pack (`DICE_SHARD`, `GODHEAD`)
- R14.5 — RESERVED — `<insert dice shard> card insertion A`
- R14.6 — RESERVED — `<insert roll-control treasure> card insertion B`
- R14.7 — Acceptance

**Key files:** `foursouls/engine/game_loop.py`, `foursouls/model/stack.py`, `foursouls/rulesets/common/effects.py`, `foursouls/rulesets/common/combat.py`, `foursouls/cards/loot.py`, `foursouls/cards/treasures.py`

---

## Sprint 15 — Cancel / response stack interaction
**Goal:** Introduce targeted cancellation of loot plays and item abilities while they are on the stack.

**New cards this sprint:**

| Card | Type | Effect |
|---|---|---|
| BUTTER_BEAN | Loot | Cancel the ↷ or $ ability of an item or a loot being played |
| NO | Active Treasure | **↷ Effect** — Cancel the ↷ or $ ability of an item |

**New mechanics:**
- Stack items must expose enough metadata to distinguish:
  - loot being played
  - item tap abilities
  - item paid abilities
- Cancelable stack-item categories.
- Canceled stack items fizzle cleanly when resolved.
- Cancellation legality rules.

**Releases:**
- R15.1 — Cancelable stack-item substrate
- R15.2 — Cancel resolution
- R15.3 — Cancel card pack (`BUTTER_BEAN`, `NO`)
- R15.4 — Rules hardening
- R15.5 — RESERVED — `<insert cancel loot> card insertion A`
- R15.6 — RESERVED — `<insert cancel treasure> card insertion B`
- R15.7 — Acceptance

**Key files:** `foursouls/model/stack.py`, `foursouls/engine/game_loop.py`, `foursouls/rulesets/common/effects.py`, `foursouls/cards/loot.py`, `foursouls/cards/treasures.py`

---

## Sprint 16 — Priority auto-advance
**Goal:** Players with no meaningful actions are automatically skipped. The engine runs to quiescence after every command — callers no longer drive a manual `PassPriority` loop.

**Rules:**
- A player with only `PassPriority` available is auto-skipped; priority advances to the next player.
- A player who *has* other actions may still explicitly pass priority without playing anything.
- After any priority reset, `Game._run_to_quiescence()` loops: auto-pass each player whose only legal command is `PassPriority()`, until someone has a real action or all have passed.
- If all pass, the existing resolution logic fires (resolve stack top, or call `on_all_passed_empty_stack`), then quiescence re-runs.
- `step()` returns only when a player with real choices holds priority, or when the game is over.

**Impact:** All existing tests that manually drive `PassPriority` pairs to resolve a stack item need updating — the stack resolves automatically inside `step(PlayLoot(...))`. Tests simplify from three calls to one.

**Releases:**
- R16.1 — `_run_to_quiescence()` core
- R16.2 — Preserve explicit pass for meaningful-choice states
- R16.3 — Simplify CLI/tests/API expectations
- R16.4 — RESERVED — `<insert reactive loot> card insertion A`
- R16.5 — RESERVED — `<insert interrupt treasure> card insertion B`
- R16.6 — Acceptance / regression pass

**Key files:** `foursouls/engine/game_loop.py`

---

## Sprint 17 — Statistics pipeline
**Goal:** A headless batch runner plays N games and records structured per-game statistics.

**New module `foursouls/sim/`:**
- `runner.py` — `run_game(game, agents) -> GameRecord`; `max_turns=500` guard emitting `GameTimeout`
- `batch.py` — `run_batch(n, factory, agents, seed_start=0) -> List[GameRecord]`
- `stats.py` — `summarise(records) -> dict` with win rates, mean/median turn count, timeout rate
- `__main__.py` — `python -m foursouls.sim --games 1000 --players 2 --seed 0`

**`GameRecord` fields:** `winner_id`, `turn_count`, `souls_per_player`, `items_bought_per_player`, `damage_taken_per_player`

**Releases:**
- R17.1 — `GameRecord` schema
- R17.2 — Headless runner
- R17.3 — Batch + summary
- R17.4 — RESERVED — `<insert benchmark monster> card insertion A`
- R17.5 — RESERVED — `<insert benchmark treasure/loot> card insertion B`
- R17.6 — Acceptance

**Key files:** `foursouls/sim/` (new package)

**Acceptance test:** 20 games with `combat_bot` vs `combat_bot`; all complete without timeout; `summarise()` returns `win_rates` and `mean_turns`.

---

## Sprint 18 — Heuristic bot
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
- R18.1 — Feature extraction from legal actions
- R18.2 — First scoring policy
- R18.3 — Compare harness + tuning
- R18.4 — RESERVED — `<insert bot-facing monster> card insertion A`
- R18.5 — RESERVED — `<insert bot-facing treasure/loot> card insertion B`
- R18.6 — Acceptance

**Acceptance test:** `head_to_head(500, factory, heuristic_bot, combat_bot)` → `heuristic_win_rate >= 0.55`.

---

## Sprint 19 — Trinkets + pile targeting
**Goal:** Introduce trinket loot-to-item transition and the pile/discard browsing mechanics needed for deferred effects.

**Releases:**
- R19.1 — `PileTarget` / pile browsing substrate
- R19.2 — Trinket lifecycle
- R19.3 — First trinket pack + complete *We Need To Go Deeper!*
- R19.4 — RESERVED — `<insert trinket> card insertion A`
- R19.5 — RESERVED — `<insert trinket> card insertion B`
- R19.6 — Acceptance

---

## Sprint 20 — Player interaction
**Goal:** Add give/steal/swap mechanics between players.

**Releases:**
- R20.1 — Ownership transfer infrastructure
- R20.2 — Interaction legality + resolution
- R20.3 — First interaction card pack
- R20.4 — RESERVED — `<insert interaction loot> card insertion A`
- R20.5 — RESERVED — `<insert interaction treasure> card insertion B`
- R20.6 — Acceptance

---

## Sprint 21 — Curses + rooms
**Goal:** Add the two remaining persistent side-system families after the stack and targeting architecture are stable.

**Releases:**
- R21.1 — Curse state model + lifecycle
- R21.2 — Room deck + room slot + lifecycle
- R21.3 — First curse/room pack
- R21.4 — RESERVED — `<insert curse> card insertion A`
- R21.5 — RESERVED — `<insert room> card insertion B`
- R21.6 — Acceptance

---

## Mechanics placed in existing sprints

| Mechanic | Sprint | Notes |
|---|---|---|
| Dice as stack items | 14 | Required for rerolls and roll replacement |
| Roll category tagging | 14 | `"attack"` vs `"non_attack"` |
| The D6 reroll tap | 14 | Previously stubbed in Sprint 11 |
| Lucky Foot roll modification | 14 | Previously stubbed in Sprint 11 |
| Cancellation of loot / item abilities | 15 | Introduced by `BUTTER_BEAN` / `NO` |
| Quiescence auto-run | 16 | Removes manual pass loops from most callers |
| Statistics batch runner | 17 | Requires stable engine API |
| Heuristic comparison harness | 18 | Depends on stats pipeline |
| Trinket zone transition | 19 | Loot resolving into `ItemInPlay` |
| `PileTarget` browsing | 19 | Needed for delayed pile-selection effects |
| Player give/steal/swap | 20 | Depends on mature targeting/runtime ownership |
| Curses / rooms | 21 | Deferred until core stack/response systems are stable |

---

## Ordering rationale

- Sprint 12 remains a pure rules/correction sprint and therefore has no card insertions.
- Sprint 13 expands monster ability coverage before deeper stack interaction grows more complex.
- Sprint 14 is pulled earlier because multiple Sprint 11 stubs depend on real roll interaction.
- Sprint 15 follows naturally once rolls are truly on the stack: it introduces cancellation and response play.
- Sprint 16 comes after stack-response depth increases, so quiescence can stabilize the full priority model.
- Sprint 17 precedes Sprint 18 because the bot needs a measurement framework.
- Sprint 19 introduces trinkets and pile targeting only after the runtime item model is mature.
- Sprint 20 adds direct player interaction after targeting and ownership systems have already expanded.
- Sprint 21 keeps curses and rooms last, because they are persistent side systems that benefit from a stable engine core.