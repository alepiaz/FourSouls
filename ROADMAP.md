# Four Souls Engine — Sprint Roadmap

This document is the living sprint plan for the project.  
Sprints 0–5 are complete. Sprints 6–15 are planned. Sprints 16+ are sketched.

---

## Status at a glance

| Sprint | Name | Status |
|--------|------|--------|
| 0 | Priority kernel | ✅ done |
| 1 | Setup + phases + EndTurn | ✅ done |
| 2 | Loot play + character abilities | ✅ done |
| 3 | Shop | ✅ done |
| 4 | Combat — attack, roll, death, rewards, souls | ✅ done |
| 5 | CLI + legal actions API + event enrichment | ✅ done |
| 6 | Win condition & game termination | 🔄 in progress |
| 7 | Correct player death penalty | 📋 planned |
| 8 | ATK stat & correct combat damage | 📋 planned |
| 9 | Event cards in monster deck | 📋 planned |
| 10 | Loot card diversity + targeting system | 📋 planned |
| 11 | Treasure card effects | 📋 planned |
| 12 | Character diversity | 📋 planned |
| 13 | Monster abilities | 📋 planned |
| 14 | Statistics pipeline | 📋 planned |
| 15 | Heuristic bot | 📋 planned |
| 16+ | Dice on stack, trinkets, steal, curses, rooms | 🔮 future |

---

## Completed sprints (0–5)

### Sprint 0 — Priority kernel
Priority manager, pass cycles, AllPlayersPassed detection, stack infrastructure.

### Sprint 1 — Setup + phases + EndTurn
`GameState`, turn order, START/ACTION/END phases, `EndTurn`, Loot1 draw, turn rotation, healing.

### Sprint 2 — Loot play + character abilities
`PlayLoot`, `GainCentsEffect`, `DealDamageEffect`, `ActivateCharacterAbility`, tap/untap, loot play quota.

### Sprint 3 — Shop
`BuyShop`, shop slot refill from treasure deck, `purchase_used` flag, economy bot.

### Sprint 4 — Combat
`AttackMonster`, `RollCombat`, hit/miss, `MonsterDied`, `PlayerDied`, soul collection, combat bot.

### Sprint 5 — CLI + legal actions API + event enrichment
`StepResult`, `LegalAction`, `get_legal_actions()`, `foursouls/cli/` package, `build_demo_game`, interactive `run()` loop, 50+ events auto-named via `__post_init__`, `GameWon` signal (no lockout yet), `DamageDealt`, `StepResult` wrapper, all players heal at `EndTurn`.

---

## Sprint 6 — Win condition & game termination
**Goal:** The game ends when a player reaches soul value ≥ 4. `legal_commands()` returns `[]`; CLI exits cleanly.

**Releases:**
- R6.1 — Healing timing: all players **and all monsters** heal to full at end of every turn ✅
- R6.2 — `game_over` flag on `Game`; `legal_commands()` short-circuits when set
- R6.3 — `game_over = True` triggered by soul win condition in `resolve_monster_death`
- R6.4 — CLI exit on `game_over`; `test_sprint6_acceptance.py`

**Key files:** `foursouls/engine/game_loop.py`, `foursouls/rulesets/common/combat.py`, `foursouls/rulesets/common/legality.py`, `foursouls/cli/app.py`

**Acceptance test:** Drive `combat_bot` to 4 souls; assert `game.game_over is True`, `get_legal_actions() == []`, `GameWon` was emitted.

---

## Sprint 7 — Correct player death penalty
**Goal:** Player death applies the correct rules penalty and active-player death correctly ends the turn.

**Official rules penalty:**
1. Destroy 1 chosen non-eternal item
2. Discard 1 loot card from hand
3. Lose 1¢
4. Deactivate all objects with ↷ ability
- Non-active player: stops here
- Active player: cleanup (stack must empty) → end phase

**Releases:**
- R7.1 — `eternal: bool` flag on `ItemInPlay`; starting items are eternal; legality guards in death penalty
- R7.2 — Death penalty applied in `resolve_player_death`; new `DeathPenaltyPaid` event
- R7.3 — Active-player death: cancel combat → drain stack → advance to end phase
- R7.4 — `died_this_turn` guard on `TurnFlags` (a player can only die once per turn); acceptance test

**Key files:** `foursouls/rulesets/common/combat.py`, `foursouls/model/item_in_play.py`, `foursouls/model/phase.py`

---

## Sprint 8 — ATK stat & correct combat damage
**Goal:** Characters and monsters use their ATK stat for combat damage instead of the hardcoded value of 1.

**Official rules:** hit → deal ATK damage to monster; miss → monster deals ATK damage to attacker. You can't deal 0 damage.

**Releases:**
- R8.1 — `attack: int` on `MonsterDef` and `MonsterInPlay`; assign values to existing monsters (FLY=1, GAPER=1, SPIDER=1, HORF=2)
- R8.2 — `attack: int` on character definitions; `attack_bonus: int = 0` on `PlayerState`
- R8.3 — `resolve_roll` uses `attacker.attack + attack_bonus` on hit; `monster.attack` on miss; skip if 0 damage
- R8.4 — `attack_stat: int` field on `CombatRollResult` event; `damage_type: "combat" | "ability"` on `DealDamageEffect`; acceptance test

**Key files:** `foursouls/cards/monsters.py`, `foursouls/cards/characters.py`, `foursouls/model/monster_in_play.py`, `foursouls/model/player_state.py`, `foursouls/rulesets/common/combat.py`

---

## Sprint 9 — Event cards in monster deck
**Goal:** Monster cards without a stat block become events when placed in a slot. They cannot be attacked, trigger abilities on entry, and discard when resolved.

**Official rules:** event cards have no stat block; all abilities are triggered abilities that fire when the card enters play; the card goes to discard when all abilities resolve.

**Releases:**
- R9.1 — `is_event: bool` on `MonsterDef`; event cards skip combat legality
- R9.2 — Slot refill detects event cards: emit `EventEntered`, push triggered ability onto stack, discard event on resolution
- R9.3 — Add 3 example event cards to `monsters.py` (positive, negative, neutral)
- R9.4 — Update `_monster_deck()` in `app.py` to include event cards; acceptance test

**Key files:** `foursouls/cards/monsters.py`, `foursouls/rulesets/common/combat.py`, `foursouls/cli/app.py`

---

## Sprint 10 — Loot card diversity + targeting system
**Goal:** Expand the loot deck from 4 types to ~10 types. Introduce a targeting system for effects that need to designate a specific player or monster.

**New loot cards:** `SOUL_HEART` (heal 1 HP), `LOOT_DRAW_1` (draw 1), `BUTTER_BEAN` (deal 1 damage to target player), `BIBLE` (+2 to this attack roll), `PILLS` (random: gain 3¢ or take 1 damage), `BOOM!` (deal 2 damage to self)

**Targeting system:** `Target` union type (`PlayerTarget`, `MonsterTarget`) in `foursouls/model/target.py`; `PlayLoot` extended with `target: Optional[AnyTarget]`; `legal_commands()` emits one `PlayLoot` per valid target for targeted cards.

**Key files:** `foursouls/model/target.py` (new), `foursouls/cards/loot.py`, `foursouls/rulesets/common/effects.py`, `foursouls/rulesets/common/legality.py`

---

## Sprint 11 — Treasure card effects
**Goal:** Give all 12 placeholder treasure cards real, distinct effects. Introduce `ActivateItem` command and $ abilities.

**Card archetypes:**
- Passive stat boosts (via `PlayerState` fields): `LUCKY_FOOT` (+1 to all rolls), `MATCH_STICK` (+1 ATK), `WIRE_COAT_HANGER` (+1 max HP)
- Activated ↷: `YUM_HEART` (heal 1 HP), `BOX_OF_WORM` (draw 2 loot), `DEAD_CAT` (max_hp=1, hp=9)
- On-enter: `MAGIC_MUSHROOM` (+2 max HP), `MEAT!` (each kill grants +1 max HP)
- 4 more across archetypes

**New infrastructure:** `TreasureDef` in `foursouls/cards/treasures.py`; `ActivateItem(instance_id)` command; `on_treasure_enters_play` hook; `counters: Dict[str, int]` on `ItemInPlay`; $ ability cost validation.

**Key files:** `foursouls/cards/treasures.py` (new), `foursouls/model/item_in_play.py`, `foursouls/engine/game_loop.py`, `foursouls/rulesets/common/legality.py`

---

## Sprint 12 — Character diversity
**Goal:** Each character has a unique ↷ activated ability.

| Character | HP | Ability |
|---|---|---|
| ISAAC | 4 | Gain 1¢ |
| MAGDALENE | 6 | Heal 1 HP |
| CAIN | 4 | Draw 1 loot |
| EVE | 2 | Deal 1 damage to target player or monster |

**Infrastructure:** `character_ability_effect(card_id, controller_id, target, game) -> Effect` factory; `ActivateCharacterAbility` extended with optional `target` (for EVE); `legal_commands()` emits one action per valid target for EVE only.

**Key files:** `foursouls/cards/characters.py`, `foursouls/engine/game_loop.py`, `foursouls/rulesets/common/legality.py`

---

## Sprint 13 — Monster abilities
**Goal:** Monsters have on-hit and on-death trigger effects so combat carries asymmetric risk.

| Monster | Trigger | Effect |
|---|---|---|
| FLY | on_hit | Attacker takes 1 extra damage |
| GAPER | on_death | Attacker draws 1 loot |
| SPIDER | on_hit | Push SlowEffect (one extra pass before next roll) |
| HORF | on_death | All other players take 1 damage |

**Infrastructure:** `on_hit` and `on_death` callable fields on `MonsterDef`; `MonsterDef` reference stored on `MonsterInPlay`; `MonsterTriggerFired` event.

**Key files:** `foursouls/cards/monsters.py`, `foursouls/model/monster_in_play.py`, `foursouls/rulesets/common/combat.py`

---

## Sprint 14 — Statistics pipeline
**Goal:** A headless batch runner plays N games and records structured per-game statistics.

**New module `foursouls/sim/`:**
- `runner.py` — `run_game(game, agents) -> GameRecord`; `max_turns=500` guard emitting `GameTimeout`
- `batch.py` — `run_batch(n, factory, agents, seed_start=0) -> List[GameRecord]`
- `stats.py` — `summarise(records) -> dict` with win rates, mean/median turn count, timeout rate
- `__main__.py` — `python -m foursouls.sim --games 1000 --players 2 --seed 0`

**`GameRecord` fields:** `winner_id`, `turn_count`, `souls_per_player`, `items_bought_per_player`, `damage_taken_per_player`

**Key files:** `foursouls/sim/` (new package)

**Acceptance test:** 20 games with `combat_bot` vs `combat_bot`; all complete without timeout; `summarise()` returns `win_rates` and `mean_turns`.

---

## Sprint 15 — Heuristic bot
**Goal:** A scoring-based bot demonstrably outperforms `combat_bot` (≥55% win rate over 500 games).

**Scoring function per action kind:**
- `RollCombat`: `reward/10 + has_soul*5 - evade/6 * (1/hp)`
- `AttackMonster`: prefer soul monsters; among equal, prefer reward/evade ratio
- `BuyShop`: score by `TreasureDef.archetype` weighted by game state (low HP → HP items; late game → attack items)
- `PlayLoot`: expected value (coin=face, heal=HP_deficit*0.5, draw=1.0)
- `ActivateCharacterAbility` / `ActivateItem`: contextual (heal if HP < max/2; buff if in combat)
- `EndTurn`: 0.0; `PassPriority`: −0.1

**New files:** `agents/heuristic_bot.py`; `foursouls/sim/compare.py` (`head_to_head(n, factory, agent_a, agent_b) -> CompareResult`)

**Acceptance test:** `head_to_head(500, factory, heuristic_bot, combat_bot)` → `heuristic_win_rate >= 0.55`.

---

## Sprints 16+ — Future mechanics

These are scoped but not yet scheduled. They extend rules parity and are ordered by dependency.

| Sprint | Name | Depends on | Key mechanic |
|--------|------|------------|--------------|
| 16 | Dice on the stack | — | Rolls become real stack items; players can respond; reroll items become functional |
| 17 | Trinkets | Sprint 10 (loot diversity) | Loot-to-item zone transition on resolution |
| 18 | Player interaction | Sprint 10 (targeting) | Steal item, give item, swap cents — give/steal/swap mechanic |
| 19 | Curses | Sprint 9 (events) | Persistent curse events assigned to a player; discarded on death |
| 20 | Rooms | Sprint 9 (events) | Optional room deck, room slot, end-phase room discard |

---

## Mechanics placed in existing sprints

The following rules concepts are not standalone sprints — they are implemented as part of the sprint that first needs them:

| Mechanic | Sprint | Notes |
|---|---|---|
| `eternal` flag on items | 7 | Death penalty says "destroy 1 **non-eternal** item" |
| $ abilities (non-tap cost) | 11 | `ActivateItem` supports both ↷ and $ costs |
| `damage_type: combat \| ability` | 8 | Added to `DealDamageEffect` alongside ATK stat |
| Item counters | 11 | `counters: Dict[str, int]` on `ItemInPlay`; needed by leveling items |
| Prevent damage | 10 | Prevention shield on `PlayerState`; checked in `DealDamageEffect` |

---

## Ordering rationale

- Sprint 6 (win condition) precedes Sprint 14 (statistics) — stats require game termination
- Sprint 7 (death penalty) corrects a rule before card breadth expands; the correct penalty (1 item + 1 loot + 1¢) must be in place before item interactions are built on top of it
- Sprint 8 (ATK stat) is a rules correction that must precede any stat-modifying cards in Sprint 11
- Sprint 9 (events) stresses the monster slot machinery before it gains trigger callbacks in Sprint 13
- Sprint 10 (targeting) must come before Sprint 12 (EVE's ability needs it)
- Sprint 14 (statistics) precedes Sprint 15 (heuristic bot) — the bot needs the pipeline to prove superiority
- Sprints 16–20 require stable dice-on-stack foundations before any of the reactive mechanics (reroll, trinkets, curses) can be correctly implemented
