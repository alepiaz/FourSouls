# Four Souls Engine — Sprint Roadmap

This document is the living sprint plan for the project.  
Sprints 0–9 are complete. Sprints 10–16 are planned. Sprints 17+ are sketched.

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
| 6 | Win condition & game termination | ✅ done |
| 7 | Correct player death penalty | ✅ done |
| 8 | ATK stat & correct combat damage | ✅ done |
| 9 | Event cards in monster deck | ✅ done |
| 10 | Loot card diversity + targeting system | 📋 planned |
| 11 | Treasure card effects | 📋 planned |
| 12 | Character diversity | 📋 planned |
| 13 | Monster abilities | 📋 planned |
| 14 | Statistics pipeline | 📋 planned |
| 15 | Heuristic bot | 📋 planned |
| 16 | Priority auto-advance | 📋 planned |
| 17+ | Dice on stack, trinkets, steal, curses, rooms | 🔮 future |

---

## Completed sprints (0–7)

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

### Sprint 6 — Win condition & game termination
`game_over` flag on `Game`; soul win condition triggers it in `resolve_monster_death`; `legal_commands()` short-circuits; CLI exits cleanly. All players and monsters heal to full at end of every turn (R6.1).

### Sprint 7 — Correct player death penalty
Death penalty (destroy 1 non-eternal item, discard 1 loot, lose 1¢, deactivate tapped abilities) applied in `resolve_player_death`. `eternal: bool` on `ItemInPlay`. Active-player death cancels combat, drains stack, advances to end phase. `died_this_turn` guard on `TurnFlags`.

---

## Sprint 6 — Win condition & game termination
**Goal:** The game ends when a player reaches soul value ≥ 4. `legal_commands()` returns `[]`; CLI exits cleanly.

**Releases:**
- R6.1 — Healing timing: all players **and all monsters** heal to full at end of every turn ✅
- R6.2 — `game_over` flag on `Game`; `legal_commands()` short-circuits when set
- R6.3 — `game_over = True` triggered by soul win condition in `resolve_monster_death`
- R6.4 — CLI exit on `game_over`; `test_sprint6_acceptance.py` ✅

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
- R7.1 — `eternal: bool` flag on `ItemInPlay`; starting items are eternal; legality guards in death penalty ✅
- R7.2 — Death penalty applied in `resolve_player_death`; new `DeathPenaltyPaid` event ✅
- R7.3 — Active-player death: cancel combat → drain stack → advance to end phase ✅
- R7.4 — `died_this_turn` guard on `TurnFlags` (a player can only die once per turn); acceptance test ✅

**Key files:** `foursouls/rulesets/common/combat.py`, `foursouls/model/item_in_play.py`, `foursouls/model/phase.py`

---

## Sprint 8 — ATK stat & correct combat damage
**Goal:** Characters and monsters use their ATK stat for combat damage instead of the hardcoded value of 1.

**Official rules:** hit → deal ATK damage to monster; miss → monster deals ATK damage to attacker. You can't deal 0 damage.

**Releases:**
- R8.1 — `attack: int` on `MonsterDef` and `MonsterInPlay`; assign values to existing monsters (FLY=1, GAPER=1, SPIDER=1, HORF=2)
- R8.2 — `attack: int` on character definitions; `attack_bonus: int = 0` on `PlayerState` (permanent cumulative bonus from items/effects; shared by Meat! in Sprint 11)
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
- R9.3 — Add 3 example event cards to `monsters.py` (positive, negative, neutral); add official Base Game V2 event cards (see below)
- R9.4 — Update `_monster_deck()` in `app.py` to include event cards; acceptance test

**Official Base Game V2 event cards:**

| Card | Type | Effect |
|---|---|---|
| Cursed Chest | Bad | Roll d6 — 1–3: take 1 damage; 4–5: take 2 damage; 6: search treasure deck for a Guppy item, gain it, shuffle. |
| We Need To Go Deeper! | Good | Put any number of non-event monster cards in discard on top of the monster deck. Active player may attack one additional time this turn. |

**Cursed Chest — Sprint 9 vs. later:**
- The 1–3 / 4–5 branches (take damage) can be implemented in Sprint 9 using existing `DealDamageEffect`.
- The roll-6 branch ("search for a Guppy item") requires an item-search mechanic and a Guppy item definition — deferred to Sprint 11 when treasure cards are defined. In Sprint 9 the roll-6 branch is a no-op stub.
- Requires a provisional `d6_branch(roll, branches: Dict[int, Effect])` helper function (inline in `effects.py`). Sprint 10 supersedes this with the proper `LootRollEffect` class and wires up the roll-6 Guppy branch at that point.

**We Need To Go Deeper! — Sprint 9 vs. later:**
- "Put any number of non-event monster cards in discard on top of the deck" requires browsing and selecting from a pile — needs a `PileTarget` mechanic not covered by Sprint 10's `PlayerTarget`/`MonsterTarget`. Deferred to Sprint 17+ (trinket zone work). In Sprint 9 this branch is a no-op stub.
- "Active player may attack an additional time this turn" sets `turn_flags.attack_used = False` — implementable in Sprint 9.

**Key files:** `foursouls/cards/monsters.py`, `foursouls/rulesets/common/combat.py`, `foursouls/cli/app.py`

---

## Sprint 10 — Loot card diversity + targeting system
**Goal:** Expand the loot deck with official Base Game V2 cards. Introduce a targeting system for effects that designate a specific player or monster. Add a loot-roll dispatcher for d6-branching cards.

**Official loot cards added this sprint:**

| Card | Type | Effect | Expansion |
|---|---|---|---|
| Bomb! | Bomb | Deal 1 damage to a monster or player | Base Game V2 |
| Gold Bomb!! | Bomb | Deal 3 damage to a monster or player | Base Game V2 |
| Soul Heart | Dice Shard | Choose a player. Prevent the next 1 damage they would take this turn. | Requiem |
| Blank Rune | Pill/Rune | Roll d6 — 1: each player gains 1¢; 2: each player draws 2 loot; 3: each player takes 3 damage; 4: each player gains 4¢; 5: each player draws 5 loot; 6: each player gains 6¢ | Base Game V2 |

**⚠ BOMB correction:** The existing engine `BOMB` card deals damage to self (wrong). In Sprint 10 it is corrected: `BOMB` becomes `BOMB!` with a target, dealing 1 damage to any chosen monster or player.

**Targeting system:** `Target` union type (`PlayerTarget`, `MonsterTarget`) in `foursouls/model/target.py`; `PlayLoot` extended with `target: Optional[AnyTarget]`; `legal_commands()` emits one `PlayLoot` per valid target for targeted cards. Untargeted cards (Blank Rune) keep the existing single-`PlayLoot` form.

**Loot roll dispatcher:** `LootRollEffect(branches: Dict[int, Effect])` resolves a d6 and delegates to the matching branch. Reused by Blank Rune and Cursed Chest (Sprint 9 roll-6 branch can be wired up here). "All players" branch effects iterate `state.turn_order`; no targeting token needed.

**Damage prevention:** `prevent_damage: int = 0` on both `PlayerState` and `MonsterInPlay`; `DealDamageEffect` consumes 1 shield before applying damage and skips if fully prevented; shield resets to 0 at `EndTurn`. Required by Soul Heart (this sprint) and Yum Heart (Sprint 11).

**Releases:**
- R10.1 — `PlayerTarget`, `MonsterTarget`, `AnyTarget` in `foursouls/model/target.py`; `PlayLoot` extended with `target: Optional[AnyTarget] = None` ✅
- R10.2 — BOMB correction: rename to `Bomb!`, add `Gold Bomb!!`; `legal_commands()` emits one `PlayLoot` per valid target for targeted cards; `make_loot_effect` accepts target ✅
- R10.3 — Soul Heart card; `prevent_damage: int = 0` on `PlayerState` and `MonsterInPlay`; shield consumed by `DealDamageEffect`, `DealDamageToMonsterEffect`, and combat miss; resets at `EndTurn` ✅
- R10.4 — Blank Rune card; `LootRollEffect(branches: Dict[int, Effect])`; all-players effects; `Cursed Chest` and `We Need To Go Deeper!` event cards; acceptance test ✅

**Key files:** `foursouls/model/target.py` (new), `foursouls/model/monster_in_play.py`, `foursouls/model/player_state.py`, `foursouls/cards/loot.py`, `foursouls/rulesets/common/effects.py`, `foursouls/rulesets/common/legality.py`

---

## Sprint 11 — Treasure card effects + starting eternal items
**Goal:** Give placeholder treasure cards real, distinct effects. Introduce `ActivateItem` command, $ abilities, and the full range of passive/active/one-use archetypes. Give each character their starting Eternal item.

**Official treasure cards this sprint:**

| Card | Type | Effect | Expansion |
|---|---|---|---|
| Dry Baby | Passive | Damage you would take is reduced to 1 | Base Game V2 |
| Eye Of Greed | Passive | Each time any player rolls a 5, you gain 3¢ | Base Game V2 |
| The Dead Cat | Passive + Counters | Starts with 9 counters. If you would take damage while this has counters, remove that many counters and prevent that much damage. **Guppy** — first player to control 2+ Guppy items gains the Soul of Guppy | Base Game V2 |
| Mama Mega | One-Use ↷ | Tap → Destroy this. Deal 3 damage to each monster and player | Requiem |
| Tech X | Active ↷ + $ | Tap → Put a counter on this. Remove 3 counters: Kill a player or monster | Base Game V2 |
| Magic Mushroom | Paid + Counters | Starts with 3 counters. Remove a counter: +1ATK for next attack roll this turn OR prevent next 1 damage this turn. Your character gains ↷: Put a counter on this | Summer of Isaac |
| Meat! | Passive | +1 to attack rolls | Base Game V2 |
| Lucky Foot | Active ↷ | Tap → Add up to 2 to a non-attack roll *(full effect requires Sprint 16)* | Base Game V2 |

**Rules text (official cards):**
> **Dry Baby** — Damage you would take is reduced to 1.

> **Eye Of Greed** — Each time a player rolls a ❺, gain 3¢.

> **The Dead Cat** — This item starts with 9 counters on it. If you would take damage while this has counters on it, remove that many counters and prevent that much damage. *(Guppy: first player to control 2+ Guppy items gains the Soul of Guppy — if it's in the game.)*

> **Mama Mega** — **↷ Effect** — Destroy this. If you do, deal 3 damage to each monster and player.

> **Tech X** — **↷ Effect** — Put a counter on this. **Paid Effect** — Remove 3 counters from this: Kill a player or monster.

> **Magic Mushroom** — This starts with 3 counters on it. **Paid Effect** — Remove a counter from this: Choose one — • Gain +1ATK for your next attack roll this turn. • Prevent the next 1 damage you would take this turn. Your character has "↷: Put a counter on an item named Magic Mushroom."

> **Meat!** — You have +1 to attack rolls.

> **Lucky Foot** — **↷ Effect** — Add up to 2 to a non-attack roll.

**Starting Eternal items (one per character):**

| Character | Eternal Item | Tap Effect | Recharge |
|---|---|---|---|
| ISAAC | The D6 | Choose a dice roll — its controller rerolls it *(stubbed; see Sprint 16)* | End of your turn |
| MAGDALENE | Yum Heart | Choose a player or monster. Prevent the next damage they take this turn. | End of your turn |
| CAIN | Sleight Of Hand | Look at the top 5 cards of a deck. Put them back in any order. | End of your turn |
| EVE | The Curse | *Start of turn:* put the top card of a deck into discard. *Tap:* put the top card of any discard on top of its deck. | End of your turn |

**The D6 rules text:**
> **↷ Effect** — Choose a dice roll. Its controller rerolls it.
> At the end of your turn, recharge this.
> *Eternal — This can't be destroyed or put into discard.*

**Yum Heart rules text:**
> **↷ Effect** — Choose a player or monster. Prevent the next instance of damage they would take this turn.
> At the end of your turn, recharge this.
> *Eternal — This can't be destroyed or put into discard.*

**Sleight Of Hand rules text:**
> **↷ Effect** — Look at the top 5 cards of a deck. Put them back in any order.
> At the end of your turn, recharge this.
> *Eternal — This can't be destroyed or put into discard.*

**The Curse rules text:**
> At the start of your turn, put the top card of a deck into discard.
> **↷ Effect** — Put the top card of any discard on top of its deck.
> At the end of your turn, recharge this.
> *Eternal — This can't be destroyed or put into discard.*

**Loot cards added this sprint:**

| Card | Type | Effect | Expansion |
|---|---|---|---|
| Lil Battery | Battery | Recharge (untap) a target item under any player's control | Base Game V2 |

*Lil Battery* requires that items in `player.items` carry `is_tapped` state, which is gated on the `List[ItemInPlay]` promotion below. Target is an `ItemTarget(instance_id)` — a new variant added to `foursouls/model/target.py` alongside the Sprint 10 `PlayerTarget`/`MonsterTarget`.

**New infrastructure:**
- `TreasureDef` in `foursouls/cards/treasures.py`; `ActivateItem(instance_id)` command; `on_treasure_enters_play` hook; `counters: Dict[str, int]` on `ItemInPlay`; $ ability cost validation.
- `player.items` promoted from `List[CardRef]` to `List[ItemInPlay]` so each item in the zone carries its own `eternal`, `is_tapped`, and `counters` state.
- `setup_game` / `build_demo_game` assign each player their starting Eternal item (placed in `player.items`, `eternal=True`).
- `EndTurn` handler untaps items whose `recharge_on` == `"end_of_turn"` (vs. the default `"start_of_turn"` for character abilities). The D6 uses `end_of_turn`.
- `legal_commands` emits `ActivateItem(instance_id)` for each non-tapped item whose tap effect is defined. The D6 tap is a no-op stub until Sprint 16.

**New mechanics this sprint:**

- **`damage_cap: int = 0`** on `PlayerState` (0 = no cap); `DealDamageEffect` applies `damage = max(1, min(damage, cap)) if cap else damage` before reduction. Required by Dry Baby.
- **Roll-result passive hook**: after `resolve_roll` emits `CombatRollResult`, check all players' items for passive roll-watchers (e.g. Eye Of Greed watches for roll == 5). `TreasureDef` gains optional `on_roll(roll: int, owner: PlayerState, game: Game) -> None` callback.
- **Counter-based damage absorption**: `DealDamageEffect` checks if the target player has an item with `absorb_counters` > 0; removes `min(counters, damage)` and reduces damage accordingly. Dead Cat sets 9 absorb counters at entry. Absorb counters are independent of Dry Baby's damage cap (cap applies first, then absorption).
- **`is_one_use: bool = False`** on `ItemInPlay`; `ActivateItem` resolver destroys the item after applying the effect (removes from `player.items`, moves to treasure discard). Required by Mama Mega.
- **`AoDamageEffect(amount, skip_player_id=None)`**: deals `amount` damage to every player (via `DealDamageEffect`) and every live monster in all slots. Required by Mama Mega.
- **`InstantKillEffect(target)`**: sets target HP to 0 (player) or `current_hp` to 0 (monster) and calls the appropriate death resolver. Required by Tech X's paid effect. Uses Sprint 10's target union type.
- **Guppy tag**: `is_guppy: bool = False` on `TreasureDef`; after any item enters play, check if the controller now owns ≥ 2 Guppy items; if so, search treasure deck for Soul of Guppy and grant it. Soul of Guppy card definition added in Sprint 13 (R13.5) — Guppy check fires but is a no-op grant until then.
- **Modal paid effects**: `ModalEffect(options: List[Effect])` pushes a choice to the active player; `ChooseOption(index)` command resolves it. Required by Magic Mushroom (ATK boost vs. damage prevention).
- **Temporary per-turn ATK boost**: `attack_roll_bonus_this_turn: int = 0` on `PlayerState`; applied in `resolve_roll` for attack rolls only, reset at `EndTurn`. Different from permanent `attack_bonus`. Required by Magic Mushroom option A.
- **Character tap grants counter**: while Magic Mushroom is in play, the character's `ActivateCharacterAbility` additionally adds a counter to it (on top of the character's normal effect). Requires `on_character_tap: Optional[Callable]` hook on `TreasureDef`, called from the `ActivateCharacterAbility` resolver.
- **Meat! uses `attack_bonus`** (introduced Sprint 8) — no new field needed; `ActivateItem` for Meat! increments `player.attack_bonus += 1` at item-enters-play. Distinct from the temporary `attack_roll_bonus_this_turn` above.
- **Non-attack roll category**: rolls must be tagged as `"attack"` or `"non_attack"` so Lucky Foot knows whether to apply. Lucky Foot's tap effect is a no-op stub in Sprint 11; wired up in Sprint 16 when dice go on the stack with their roll-type tag.
- **Deck targeting**: `DeckTarget` enum (`LOOT_DECK`, `TREASURE_DECK`, `MONSTER_DECK`) and corresponding `DiscardTarget` enum; used by Sleight Of Hand, The Curse, and the loot-roll decoder for Cursed Chest. `legal_commands()` emits one `ActivateItem` per valid deck target for items that require it.
- **Start-of-turn item trigger**: `on_start_of_turn: Optional[Callable[[Game], None]]` on `TreasureDef`; called from `enter_start_phase` (or the START-phase resolver) for each item the active player controls. Required by The Curse's auto-discard.
- **Peek and reorder** (Sleight Of Hand): `PeekEffect(deck_target, count=5)` temporarily exposes the top N cards; `ReorderCards(order: List[InstanceId])` command submits the chosen sequence and puts them back. The game enters a `PendingReorder` sub-state while waiting for `ReorderCards`. In Sprint 11 this is simplified to **auto-shuffle** the top 5 (no player choice) — full interactive reorder deferred to Sprint 16+.

**Releases:**
- R11.1 — `TreasureDef` skeleton in `foursouls/cards/treasures.py`; card-ID constants for all Sprint 11 treasure cards; `ActivateItem(instance_id)` command; `ItemInPlay` gains `recharge_on: str` and `counters: Dict[str, int]`; `player.items` promoted from `List[CardRef]` to `List[ItemInPlay]`; `gain_treasure` wraps `CardRef` in `ItemInPlay`; death penalty filters for non-eternal; all callsites and affected tests updated ✅
- R11.2 — `ActivateItem(instance_id, target)` legality and resolution; `TreasureDef` gains `tap_target_type` and `make_tap_effect`; `TREASURE_REGISTRY`; `AoDamageEffect`, `PreventDamageToMonsterEffect`, `TreasureActivateEffect` in `effects.py`; `on_activate_item` in `items.py`; `end_of_turn` items untap in `on_end_turn`; `start_of_turn` items untap in `enter_start_phase`; `Mama Mega` and `Yum Heart` card definitions; acceptance test ✅
- R11.3 — `CharacterDef.starting_eternal`; `_assign_starting_eternals` in `setup_game`; `fire_on_enters_play` + `fire_on_start_of_turn` helpers; `damage_cap: int = 0` on `PlayerState`; cap applied in `DealDamageEffect`, `AllPlayersTakeDamageEffect`, `AoDamageEffect`; `Dry Baby`, `Meat!`, `The D6`, `Lucky Foot`, `Sleight Of Hand` (stub), `The Curse` (stub) card defs; `on_buy_shop` fires `on_enters_play`; acceptance test ✅

**Key files:** `foursouls/cards/treasures.py` (new), `foursouls/model/item_in_play.py`, `foursouls/model/player_state.py`, `foursouls/model/commands.py`, `foursouls/engine/game_loop.py`, `foursouls/rulesets/common/legality.py`, `foursouls/rulesets/common/setup.py`

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
**Goal:** Monsters with printed ability text get their effects. FLY and SPIDER have none; GAPER and HORF have roll-conditional effects.

| Monster | Trigger | Condition | Effect |
|---|---|---|---|
| FLY | — | — | No ability |
| GAPER | on_death | roll == 6 | Active player must make one additional attack on the monster deck |
| SPIDER | — | — | No ability |
| HORF | on_miss | roll == 2 | Combat damage dealt to attacker is increased by 1 |
| HEADLESS_HORSEMAN | on_would_die | first time per turn | Prevent death; heal 2 HP; gain +1 DC and −1 ATK until end of turn |

**Rules text:**
- GAPER: *"When this dies on an attack roll of 6, the active player must make an additional attack on the monster deck."*
- HORF: *"Combat damage this deals is increased by 1 on attack rolls of 2."*
- HEADLESS_HORSEMAN: *"The first time this would die each turn, prevent death. This heals 2 HP and gains +1 DC and −1 ATK till end of turn."*

**Infrastructure:**
- Store `last_combat_roll: int` on `CombatState` so ability checks can read the triggering roll value.
- `on_death: Optional[Callable[[Game, int], None]]` on `MonsterDef` (second arg = the roll); called from `resolve_monster_death` when set.
- `on_miss: Optional[Callable[[Game, int], int]]` on `MonsterDef` — returns modified damage amount; called in `resolve_roll` before applying miss damage.
- `on_would_die: Optional[Callable[[Game], bool]]` on `MonsterDef` — called before death resolves; returns `True` if death is prevented.
- `prevent_death_used: bool = False` on `MonsterInPlay`; set to `True` when triggered; reset at `EndTurn` for all monsters in play.
- `evade_bonus: int = 0` and `attack_bonus: int = 0` on `MonsterInPlay` for temporary modifiers; reset at `EndTurn`.
- GAPER `on_death`: if roll == 6, push a forced attack on the monster deck (no cost to attacker's `attack_used`).
- HORF `on_miss`: if roll == 2, return `monster.attack + 1`.
- HEADLESS_HORSEMAN `on_would_die`: if not `prevent_death_used`, heal +2 HP (capped at `base_hp`), apply `evade_bonus += 1` and `attack_bonus -= 1`, set flag; return True (prevent death). Combat continues.
- `MonsterTriggerFired` event with fields `card_id`, `trigger`, `roll`.
- R13.5 — `SOUL_OF_GUPPY` treasure card definition in `foursouls/cards/treasures.py`; grants a bonus soul (worth 1 soul toward win condition) and the `is_guppy` tag; wires up the Sprint 11 Guppy grant no-op.

**Key files:** `foursouls/cards/monsters.py`, `foursouls/cards/treasures.py`, `foursouls/model/combat_state.py`, `foursouls/model/monster_in_play.py`, `foursouls/rulesets/common/combat.py`, `foursouls/engine/events.py`

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

## Sprint 16 — Priority auto-advance
**Goal:** Players with no meaningful actions are automatically skipped. The engine runs to quiescence after every command — callers no longer drive a manual `PassPriority` loop.

**Rules:**
- A player with only `PassPriority` available is auto-skipped; priority advances to the next player.
- A player who *has* other actions may still explicitly pass priority without playing anything.
- After any priority reset, `Game._run_to_quiescence()` loops: auto-pass each player whose only legal command is `PassPriority()`, until someone has a real action or all have passed.
- If all pass, the existing resolution logic fires (resolve stack top, or call `on_all_passed_empty_stack`), then quiescence re-runs.
- `step()` returns only when a player with real choices holds priority, or when the game is over.

**Impact:** All existing tests that manually drive `PassPriority` pairs to resolve a stack item need updating — the stack resolves automatically inside `step(PlayLoot(...))`. Tests simplify from three calls to one.

**Key files:** `foursouls/engine/game_loop.py`

---

## Sprints 17+ — Future mechanics

These are scoped but not yet scheduled. They extend rules parity and are ordered by dependency.

| Sprint | Name | Depends on | Key mechanic |
|--------|------|------------|--------------|
| 17 | Dice on the stack | — | Rolls become real stack items; players can respond; reroll items become functional (The D6 tap); I. The Magician (set roll value); Mutant Spider (roll 4 dice, choose 1) |
| 18 | Trinkets | Sprint 10 (loot diversity) | Loot-to-item zone transition on resolution; canonical example: Curved Horn (+1ATK on first attack roll each turn) |
| 19 | Player interaction | Sprint 10 (targeting) | Steal item, give item, swap cents — give/steal/swap mechanic |
| 20 | Curses | Sprint 9 (events) | Persistent curse events assigned to a player; discarded on death |
| 21 | Rooms | Sprint 9 (events) | Optional room deck, room slot, end-phase room discard |

---

## Mechanics placed in existing sprints

The following rules concepts are not standalone sprints — they are implemented as part of the sprint that first needs them:

| Mechanic | Sprint | Notes |
|---|---|---|
| `eternal` flag on items | 7 | Death penalty says "destroy 1 **non-eternal** item" |
| $ abilities (non-tap cost) | 11 | `ActivateItem` supports both ↷ and $ costs |
| `damage_type: combat \| ability` | 8 | Added to `DealDamageEffect` alongside ATK stat |
| Item counters | 11 | `counters: Dict[str, int]` on `ItemInPlay`; needed by leveling items |
| Prevent damage | 10 | `prevent_damage: int = 0` on `PlayerState` and `MonsterInPlay`; consumed and zeroed in `DealDamageEffect`; cleared at `EndTurn` |
| Starting Eternal items per character | 11 | Each character gets their Eternal in `player.items` at setup; `eternal=True`, assigned via `CharacterDef` |
| `recharge_on` field on `ItemInPlay` | 11 | `"start_of_turn"` (default) vs `"end_of_turn"` (The D6); untap hook runs at the right phase |
| The D6 reroll tap | 16 | Requires dice-on-stack; stubbed as no-op in Sprint 11 |
| `LootRollEffect` dispatcher | 10 | d6 roll → branch dispatch for Blank Rune; supersedes the Sprint 9 provisional `d6_branch` helper and wires up Cursed Chest's roll-6 stub |
| `ItemTarget` in targeting system | 11 | Third target variant alongside `PlayerTarget`/`MonsterTarget`; required by Lil Battery |
| Loot card type tags | 10 | `card_type: str` on `LootDef` (e.g. `"bomb"`, `"rune"`, `"dice_shard"`, `"trinket"`, `"battery"`); used by legality to generate correct target prompts |
| Trinket zone transition | 17 | Trinket loot cards go to `player.items` (as `ItemInPlay`) instead of discard on resolution; `PlayLoot` handler checks `LootDef.is_trinket` |
| I. The Magician set-roll | 16 | Requires dice-on-stack; `ChooseValue(1–6)` command emitted by the D6-on-stack resolver |
| `BOMB` correction to targeted | 10 | Current engine `BOMB` damages self; corrected to `BOMB!` (deal 1 dmg to target monster/player) in Sprint 10 when targeting lands |
| `damage_cap: int = 0` on `PlayerState` | 11 | 0 = no cap; checked in `DealDamageEffect` before absorption; required by Dry Baby |
| Roll-result passive hook (`on_roll`) | 11 | `TreasureDef.on_roll(roll, owner, game)` callback called after every `CombatRollResult`; required by Eye Of Greed |
| Counter-based damage absorption | 11 | `DealDamageEffect` checks `absorb_counters` on owner's items; required by The Dead Cat |
| `is_one_use` on `ItemInPlay` | 11 | Item is destroyed (→ treasure discard) after its tap effect resolves; required by Mama Mega |
| `AoDamageEffect` (all targets) | 11 | Iterates all players and live monster slots; required by Mama Mega |
| `InstantKillEffect` | 11 | Sets target HP to 0 and calls death resolver; required by Tech X paid effect |
| Guppy tag (`is_guppy: bool`) | 11 | Checked on item entry; Soul of Guppy grant is a no-op stub until the card is defined |
| `ModalEffect` + `ChooseOption` command | 11 | Player picks from N effect options; required by Magic Mushroom |
| `attack_roll_bonus_this_turn` on `PlayerState` | 11 | Temporary; reset at `EndTurn`; distinct from permanent `attack_bonus`; required by Magic Mushroom option A |
| `on_character_tap` hook on `TreasureDef` | 11 | Fires when owner uses `ActivateCharacterAbility`; required by Magic Mushroom (put counter on self) |
| `attack_bonus` on `PlayerState` (permanent) | 8 | Introduced Sprint 8 for character ATK; Meat! (Sprint 11) increments this same field — no separate field needed |
| Non-attack roll tag | 11 | Rolls tagged `"attack"` or `"non_attack"`; Lucky Foot tap stubs to no-op until Sprint 16 wires it |
| `DeckTarget` + `DiscardTarget` enums | 11 | Choose which deck/discard to act on; required by Sleight Of Hand and The Curse |
| `on_start_of_turn` hook on `TreasureDef` | 11 | Fires from `enter_start_phase` for each item the active player controls; required by The Curse |
| Peek + reorder (Sleight Of Hand) | 11/16 | Sprint 11: auto-shuffle top 5 (no player choice); Sprint 16+: `PendingReorder` sub-state + `ReorderCards` command for full interaction |
| Multi-roll-choose (Mutant Spider) | 16 | Extension of dice-on-stack: roll 4 dice, `ChooseRoll(index)` command selects the result |

---

## Ordering rationale

- Sprint 6 (win condition) precedes Sprint 14 (statistics) — stats require game termination
- Sprint 7 (death penalty) corrects a rule before card breadth expands; the correct penalty (1 item + 1 loot + 1¢) must be in place before item interactions are built on top of it
- Sprint 8 (ATK stat) is a rules correction that must precede any stat-modifying cards in Sprint 11
- Sprint 9 (events) stresses the monster slot machinery before it gains trigger callbacks in Sprint 13
- Sprint 10 (targeting) must come before Sprint 12 (EVE's ability needs it)
- Sprint 10's `LootRollEffect` completes Cursed Chest's roll-6 stub from Sprint 9
- Sprint 11's `ItemTarget` and `List[ItemInPlay]` promotion is required by Lil Battery (Sprint 11 loot)
- Sprint 14 (statistics) precedes Sprint 15 (heuristic bot) — the bot needs the pipeline to prove superiority
- Sprint 16 (dice on stack) is required by both The D6 (Sprint 11 stub) and I. The Magician (Sprint 16)
- Sprint 17 (trinkets) requires Sprint 10's loot diversity infrastructure; Curved Horn is the canonical trinket example
- Sprint 17 (trinkets) is also the earliest point to introduce `PileTarget` (pile/discard browsing), completing We Need To Go Deeper!'s main effect

---

## Card Catalog

All cards planned or implemented across sprints, structured for direct lookup. Fields are as they will exist in the final data model (post all planned sprints). Cards not yet implemented are annotated with the sprint that introduces them.

```json
{
  "characters": [
    {
      "id": "ISAAC", "name": "Isaac",
      "set": "Base Game V2",
      "hp": 4, "attack": 1,
      "ability": { "trigger": "tap", "effect": "Gain 1¢", "recharge": "start_of_turn" },
      "eternal_item": "THE_D6",
      "sprint_added": 1,
      "ability_sprint": 12
    },
    {
      "id": "MAGDALENE", "name": "Magdalene",
      "set": "Base Game V2",
      "hp": 6, "attack": 1,
      "ability": { "trigger": "tap", "effect": "Heal 1 HP", "recharge": "start_of_turn" },
      "eternal_item": "YUM_HEART",
      "sprint_added": 1,
      "ability_sprint": 12
    },
    {
      "id": "CAIN", "name": "Cain",
      "set": "Base Game V2",
      "hp": 4, "attack": 1,
      "ability": { "trigger": "tap", "effect": "Draw 1 loot card", "recharge": "start_of_turn" },
      "eternal_item": "SLEIGHT_OF_HAND",
      "sprint_added": 1,
      "ability_sprint": 12
    },
    {
      "id": "EVE", "name": "Eve",
      "set": "Base Game V2",
      "hp": 2, "attack": 1,
      "ability": {
        "trigger": "tap",
        "effect": "Deal 1 damage to target player or monster",
        "target": "PlayerTarget | MonsterTarget",
        "recharge": "start_of_turn"
      },
      "eternal_item": "THE_CURSE",
      "sprint_added": 1,
      "ability_sprint": 12
    }
  ],

  "monsters": [
    {
      "id": "FLY", "name": "Fly",
      "set": "Base Game V2",
      "hp": 1, "evade": 2, "attack": 1,
      "reward_coin": 1, "reward_loot": 0, "reward_treasure": 0,
      "has_soul": false, "is_boss": false,
      "abilities": [],
      "sprint_added": 4,
      "attack_sprint": 8
    },
    {
      "id": "GAPER", "name": "Gaper",
      "set": "Base Game V2",
      "hp": 2, "evade": 4, "attack": 1,
      "reward_coin": 3, "reward_loot": 0, "reward_treasure": 0,
      "has_soul": false, "is_boss": false,
      "abilities": [
        {
          "trigger": "on_death",
          "condition": "combat_roll == 6",
          "effect": "Active player makes one additional forced attack on the monster deck (no attack_used cost)"
        }
      ],
      "sprint_added": 4,
      "attack_sprint": 8,
      "ability_sprint": 13
    },
    {
      "id": "SPIDER", "name": "Spider",
      "set": "Base Game V2",
      "hp": 1, "evade": 4, "attack": 1,
      "reward_coin": 0, "reward_loot": 1, "reward_treasure": 0,
      "has_soul": false, "is_boss": false,
      "abilities": [],
      "sprint_added": 4,
      "attack_sprint": 8
    },
    {
      "id": "HORF", "name": "Horf",
      "set": "Base Game V2",
      "hp": 1, "evade": 4, "attack": 2,
      "reward_coin": 3, "reward_loot": 0, "reward_treasure": 0,
      "has_soul": false, "is_boss": false,
      "abilities": [
        {
          "trigger": "on_miss",
          "condition": "combat_roll == 2",
          "effect": "Combat damage dealt to attacker is increased by 1 (returns monster.attack + 1)"
        }
      ],
      "sprint_added": 4,
      "attack_sprint": 8,
      "ability_sprint": 13
    },
    {
      "id": "MONSTRO", "name": "Monstro",
      "set": "Base Game V2",
      "hp": 4, "evade": 4, "attack": 1,
      "reward_coin": 6, "reward_loot": 0, "reward_treasure": 0,
      "has_soul": true, "is_boss": true,
      "abilities": [],
      "sprint_added": 4,
      "attack_sprint": 8
    },
    {
      "id": "HEADLESS_HORSEMAN", "name": "Headless Horseman",
      "set": "Base Game V2",
      "hp": 3, "evade": 3, "attack": 2,
      "reward_coin": 0, "reward_loot": 0, "reward_treasure": 1,
      "has_soul": true, "is_boss": true,
      "abilities": [
        {
          "trigger": "on_would_die",
          "condition": "prevent_death_used == false",
          "effect": "Prevent death. Heal 2 HP (capped at base_hp). Apply evade_bonus += 1 and attack_bonus -= 1 until end of turn. Set prevent_death_used = true.",
          "reset": "end_of_turn"
        }
      ],
      "sprint_added": 13
    }
  ],

  "events": [
    {
      "id": "FEAST", "name": "Feast",
      "set": "custom",
      "is_event": true,
      "abilities": [
        { "trigger": "on_enter", "effect": "Active player gains 5¢" }
      ],
      "sprint_added": 9
    },
    {
      "id": "PLAGUE", "name": "Plague",
      "set": "custom",
      "is_event": true,
      "abilities": [
        { "trigger": "on_enter", "effect": "Active player takes 2 damage" }
      ],
      "sprint_added": 9
    },
    {
      "id": "WANDERING", "name": "Wandering",
      "set": "custom",
      "is_event": true,
      "abilities": [
        { "trigger": "on_enter", "effect": "Active player draws 1 loot card" }
      ],
      "sprint_added": 9
    },
    {
      "id": "CURSED_CHEST", "name": "Cursed Chest",
      "set": "Base Game V2",
      "is_event": true,
      "abilities": [
        {
          "trigger": "on_enter",
          "effect": "Roll d6. 1–3: take 1 damage. 4–5: take 2 damage. 6: search treasure deck for a Guppy item, gain it, shuffle. (Roll-6 branch is a no-op stub until Sprint 10 wires LootRollEffect.)"
        }
      ],
      "sprint_added": 9,
      "roll6_sprint": 10
    },
    {
      "id": "WE_NEED_TO_GO_DEEPER", "name": "We Need To Go Deeper!",
      "set": "Base Game V2",
      "is_event": true,
      "abilities": [
        {
          "trigger": "on_enter",
          "effect": "Put any number of non-event monster cards in discard on top of the monster deck (requires PileTarget — stub until Sprint 17+). Active player may attack one additional time this turn (attack_used = false — implemented Sprint 9)."
        }
      ],
      "sprint_added": 9,
      "pile_target_sprint": "17+"
    }
  ],

  "loot": [
    {
      "id": "LOOT_COIN_1", "name": "A Penny",
      "set": "Base Game V2",
      "card_type": "coin",
      "effect": "Gain 1¢",
      "sprint_added": 1
    },
    {
      "id": "LOOT_COIN_2", "name": "A Penny",
      "set": "Base Game V2",
      "card_type": "coin",
      "effect": "Gain 1¢",
      "sprint_added": 1
    },
    {
      "id": "LOOT_COIN_3", "name": "A Penny",
      "set": "Base Game V2",
      "card_type": "coin",
      "effect": "Gain 1¢",
      "sprint_added": 1
    },
    {
      "id": "BOMB", "name": "Bomb",
      "set": "Base Game V2",
      "card_type": "bomb",
      "effect": "Deal 1 damage to self (pre-Sprint 10 placeholder — corrected to BOMB! in Sprint 10)",
      "sprint_added": 2,
      "corrected_sprint": 10
    },
    {
      "id": "BOMB_TARGETED", "name": "Bomb!",
      "set": "Base Game V2",
      "card_type": "bomb",
      "effect": "Deal 1 damage to target player or monster",
      "target": "PlayerTarget | MonsterTarget",
      "sprint_added": 10
    },
    {
      "id": "GOLD_BOMB", "name": "Gold Bomb!!",
      "set": "Base Game V2",
      "card_type": "bomb",
      "effect": "Deal 3 damage to target player or monster",
      "target": "PlayerTarget | MonsterTarget",
      "sprint_added": 10
    },
    {
      "id": "SOUL_HEART", "name": "Soul Heart",
      "set": "Requiem",
      "card_type": "dice_shard",
      "effect": "Choose a player. Prevent the next 1 damage they would take this turn.",
      "target": "PlayerTarget",
      "sprint_added": 10
    },
    {
      "id": "BLANK_RUNE", "name": "Blank Rune",
      "set": "Base Game V2",
      "card_type": "rune",
      "effect": "Roll d6. 1: each player gains 1¢. 2: each player draws 2 loot. 3: each player takes 3 damage. 4: each player gains 4¢. 5: each player draws 5 loot. 6: each player gains 6¢.",
      "target": null,
      "sprint_added": 10
    },
    {
      "id": "LIL_BATTERY", "name": "Lil Battery",
      "set": "Base Game V2",
      "card_type": "battery",
      "effect": "Untap (recharge) target item under any player's control.",
      "target": "ItemTarget",
      "sprint_added": 11
    }
  ],

  "treasures": [
    {
      "id": "DRY_BABY", "name": "Dry Baby",
      "set": "Base Game V2",
      "archetype": "passive",
      "abilities": [
        { "trigger": "passive", "effect": "Damage you would take is reduced to 1 (damage_cap = 1 on PlayerState)" }
      ],
      "sprint_added": 11
    },
    {
      "id": "EYE_OF_GREED", "name": "Eye of Greed",
      "set": "Base Game V2",
      "archetype": "passive",
      "abilities": [
        { "trigger": "on_roll", "condition": "roll == 5", "effect": "Owner gains 3¢ (fires via TreasureDef.on_roll callback after every CombatRollResult)" }
      ],
      "sprint_added": 11
    },
    {
      "id": "THE_DEAD_CAT", "name": "The Dead Cat",
      "set": "Base Game V2",
      "archetype": "passive_counters",
      "is_guppy": true,
      "counters_start": 9,
      "abilities": [
        { "trigger": "passive", "condition": "has absorb_counters > 0", "effect": "If owner would take damage, remove that many counters instead and prevent that damage" }
      ],
      "guppy_note": "First player to control 2+ Guppy items gains Soul of Guppy (defined Sprint 13 R13.5)",
      "sprint_added": 11
    },
    {
      "id": "MAMA_MEGA", "name": "Mama Mega",
      "set": "Requiem",
      "archetype": "one_use_tap",
      "is_one_use": true,
      "abilities": [
        { "trigger": "tap", "effect": "Destroy this. Deal 3 damage to each player and each live monster (AoDamageEffect)." }
      ],
      "sprint_added": 11
    },
    {
      "id": "TECH_X", "name": "Tech X",
      "set": "Base Game V2",
      "archetype": "active_paid",
      "counters_start": 0,
      "abilities": [
        { "trigger": "tap", "effect": "Put 1 counter on this." },
        { "trigger": "paid", "cost": "remove 3 counters", "effect": "Kill target player or monster (InstantKillEffect).", "target": "PlayerTarget | MonsterTarget" }
      ],
      "sprint_added": 11
    },
    {
      "id": "MAGIC_MUSHROOM", "name": "Magic Mushroom",
      "set": "Summer of Isaac",
      "archetype": "paid_counters",
      "counters_start": 3,
      "abilities": [
        {
          "trigger": "paid",
          "cost": "remove 1 counter",
          "effect": "Choose one: (A) +1 ATK for next attack roll this turn (attack_roll_bonus_this_turn += 1). (B) Prevent the next 1 damage you would take this turn. (ModalEffect)"
        },
        {
          "trigger": "on_character_tap",
          "effect": "Put 1 counter on this (on_character_tap hook on TreasureDef)"
        }
      ],
      "sprint_added": 11
    },
    {
      "id": "MEAT", "name": "Meat!",
      "set": "Base Game V2",
      "archetype": "passive",
      "abilities": [
        { "trigger": "on_enter_play", "effect": "attack_bonus += 1 on owner's PlayerState (permanent, stacks)" }
      ],
      "sprint_added": 11
    },
    {
      "id": "LUCKY_FOOT", "name": "Lucky Foot",
      "set": "Base Game V2",
      "archetype": "active_tap",
      "abilities": [
        { "trigger": "tap", "effect": "Add up to 2 to a non-attack roll. (Stub until Sprint 16 — dice-on-stack required for roll interception.)", "stub_until": 16 }
      ],
      "sprint_added": 11
    },
    {
      "id": "SOUL_OF_GUPPY", "name": "Soul of Guppy",
      "set": "Base Game V2",
      "archetype": "soul",
      "is_guppy": true,
      "abilities": [
        { "trigger": "on_gain", "effect": "Counts as 1 soul toward win condition." }
      ],
      "sprint_added": 13,
      "note": "Granted automatically when a player controls 2+ Guppy items; card lives in the treasure deck."
    }
  ],

  "eternal_items": [
    {
      "id": "THE_D6", "name": "The D6",
      "set": "Base Game V2",
      "owner_character": "ISAAC",
      "eternal": true,
      "recharge_on": "end_of_turn",
      "abilities": [
        {
          "trigger": "tap",
          "effect": "Choose a dice roll. Its controller rerolls it. (Stub until Sprint 16 — dice-on-stack required.)",
          "stub_until": 16
        }
      ],
      "sprint_added": 11
    },
    {
      "id": "YUM_HEART", "name": "Yum Heart",
      "set": "Base Game V2",
      "owner_character": "MAGDALENE",
      "eternal": true,
      "recharge_on": "end_of_turn",
      "abilities": [
        {
          "trigger": "tap",
          "effect": "Choose a player or monster. Prevent the next instance of damage they would take this turn.",
          "target": "PlayerTarget | MonsterTarget"
        }
      ],
      "sprint_added": 11
    },
    {
      "id": "SLEIGHT_OF_HAND", "name": "Sleight of Hand",
      "set": "Base Game V2",
      "owner_character": "CAIN",
      "eternal": true,
      "recharge_on": "end_of_turn",
      "abilities": [
        {
          "trigger": "tap",
          "effect": "Look at the top 5 cards of a deck. Put them back in any order. Sprint 11: auto-shuffle (no player choice). Sprint 16+: PendingReorder sub-state + ReorderCards command.",
          "target": "DeckTarget",
          "full_implementation_sprint": "16+"
        }
      ],
      "sprint_added": 11
    },
    {
      "id": "THE_CURSE", "name": "The Curse",
      "set": "Base Game V2",
      "owner_character": "EVE",
      "eternal": true,
      "recharge_on": "end_of_turn",
      "abilities": [
        {
          "trigger": "start_of_turn",
          "effect": "Put the top card of a chosen deck into that deck's discard (on_start_of_turn hook).",
          "target": "DeckTarget"
        },
        {
          "trigger": "tap",
          "effect": "Put the top card of any discard pile on top of its deck.",
          "target": "DiscardTarget"
        }
      ],
      "sprint_added": 11
    }
  ]
}
```
