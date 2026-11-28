# Delivery roadmap

## Playable baseline

Two or more seats can run a seeded CLI demo, draw/play loot, activate selected items, buy from the shop, attack face-up monsters or the deck, pass priority, resolve combat and win at four one-point soul cards. Trusted CPU policies can submit the same commands. The default pools are hand-built and mix editions. Several registered cards have incomplete or incorrect effects; roll responses, general player decisions, death timing, deck recycling, fair private views and large-batch analysis remain incomplete.

| Reference | Status on 28 November 2026 |
|---|---|
| Sprint 14.5, Sprint 13, Sprint 13.5 | Merged in that order via PRs #3, #4 and #5. Sprint 13.5 merged at `b39edc6`. R13.5 is also the historical Headless Horseman release within Sprint 13. |
| Sprint 14 completion | [PR #6](https://github.com/alepiaz/FourSouls/pull/6) merged at `main@c7e8ff7`. Its tree matches the audited Sprint 14 tip, `sprint-14-completion@0e668c1`. |
| Audit and planning | [Batch 055](BASE_GAME_V2_AUDIT.md), `audit-base-game-v2@0b3bef1`. 287 grouped designs, 370 ability/setup/reward rows. [Capability and wiring map](EFFECT_INVENTORY.md) · [Execution traces and tested baselines](IMPL_STATUS.md). |

## Next playable milestone

**A corrected V2 demo pack and a board that refills after ordinary events.** Deliver four new demo entries, repair Clotty, and remove a reproduced cause of stalled CPU games. The content and refill changes can start on merged Sprint 14. Publish the pack only after both lanes pass. This milestone has its own name (V2 demo pack); the historical optional R14.5 insertion and the completed Sprint 14.5 keep their meanings.

| Order | Developer task and files | Acceptance |
|---|---|---|
| 1 | Start with the incorrect Clotty expectation in `tests/unit/test_phase0_cards.py::BASIC_MONSTER_SPECS`. Change expected HP/DC/ATK/reward to 2/3/1/4. Confirm the old definition fails; fix `foursouls/data/monsters.yaml`. | Exact definition and instance, no abilities or soul. A plain 1-ATK hit leaves 1 HP; second hit pays four cents once. |
| 2 | Extend the existing numeric registries in `cards/monsters.py`, `cards/loot.py`, `data/monsters.yaml`, `data/loot.yaml`. Add Dip (1/4/1, 1¢), Pale Fatty (4/3/1, 6¢), Red Host (2/3/1, 5¢), A Dime!! (gain 10¢). | Each ref loads its exact definition, no fallback, no new effect type. Test amounts and empty monster ability tuples. A canceled Dime pays zero and reaches loot discard once. |
| 3 | Wire the IDs in `cli/app.py::_monster_deck/_loot_deck`. Use one demo copy each, adjusting counts of ordinary monsters/coins to retain the existing demo pool sizes; record the demo distribution. Extend `test_stabilization.py`. | Pool contains each ID, distinct physical refs, stable order before shuffle and reproducible setup. Reach cards from a normal factory. Preserve existing named cards and a winnable soul supply. Official multiplicities stay at R26. |
| 4 (parallel with 1–3) | Split the existing `test_event_slot_cleared_after_resolution` expectation in `tests/acceptance/test_sprint9_acceptance.py` into empty-supply and available-supply cases. Trace `EventCardEffect.apply`, `place_monster_card`, `Game.step` and `SlotsZone.remove_top`. At the normal priority boundary service a due vacant slot through existing placement. Restore covered occupants first. Expose the same refill operation to R24 when that milestone introduces death-held slots. | Consecutive ordinary events each get their actual response/resolve window, then expose one monster. With an uncovered occupant draw zero new cards. Empty supply returns control without spinning. Event discard/entry/subscription happens once. No recursion or auto-pass past an actionable response. |
| 5 | Add one scenario fixture built with `setup_game`, genuine YAML IDs, fixed deck composition and a scripted roll stream or selected seed. Use `get_legal_actions` and `Game.step` for all moves, including both seats' passes. Reuse Sprint 10/13 acceptance helpers where possible. | After setup, play Dime from hand. Respond/pass until it pays 10¢. Attack corrected Clotty; roll two hits. Verify HP after the first, a **net 14¢** from the two cards, one Clotty in discard, no soul, a fixed refill event with no coin change resolves and the next monster is attackable when an allowance is available. Assert command actor and ordered events; repeat same seed/actions. No direct effect call, synthetic death, or clearing the stack in this test. |
| 6 | Run the existing suite and the fixed 20-seed CPU panel described in IMPL_STATUS. Record completion/caps and investigate residual caps independently of throughput. | All pack and refill scenarios pass. No capped game leaves ordinary monster slots empty indefinitely while eligible cards remain. Report residual reasons and names/IDs wired; the strict full-design verification gate remains per audit row. |

**Delivery accounting.** The pack changes four absent designs to demo-wired and repairs one already-wired design. The refill fix earns zero additional card credits. Register-only alternatives include single-loot and boss monsters listed in the inventory. Count those at their actual pack. A universal final-roll signal alone also earns zero cards: Cursed Gaper needs group resolution and expiry, Holy Dinga additionally needs healing and a variable reward, and item listeners need acquisition/subscription.

<a id="ordering-rationale"></a>

## Dependency order

| Start when | Work that can proceed | Integration gate |
|---|---|---|
| Merged main | Start demo data and refill in parallel. Reproduce the known timing and visibility failures. | Run the suite and fixed-seed replay panel against the merged Sprint 14 baseline. |
| Existing command/stack kernel | R23 decision and captured-context slice, R16 stack kind/sequence contract, R20 target incarnation slice. Private observation work in R17 can start with current actions. | A pending ability can ask the authorized owner once on resolution; source exit and target exit have different effects. A nested roll returns to its original instruction. Decide this contract before card packs depend on eager target binding. |
| Stack metadata and decision contract | R15 roll path, R16 cancellation pack, R23 typed event subscriptions. Build R20 deck transactions in parallel. | Attack and non-attack rolls are actionable, revalidate by ID and finalize once; unchanged seed/decisions replay. This is the next rules-heavy playable release after the demo pack. |
| Staged resolution and identity | R24 damage/death/rewards (ordinary souls first); R25 simple derived stats; R17 quiescence/private views; R20 piles/trinket. | Wizoob normal death with delegated choice, Cursed Gaper group expiry, legal off-turn responses. Each feature runs with CLI or scripted CPU. |
| Choice, zones and per-viewer observations | R21 transfer/votes; R22 curses/bonus souls after death stages; R25 complex statics; R18 measured batch runner, then R19 bot comparison. | Fair observation for agent comparison; consistent transfer/replacement for card certification. Full V2 is independent of heuristic bot tuning. |
| Individual capability exits | R26 edition-specific content/edge packs can land incrementally. Multiplicity research can start immediately. | Every design satisfies the verification gate; manifest reconciles all 340 entries. |

<a id="mechanics-placed-in-existing-sprints"></a>

## Release ownership and migration

Completed milestone IDs are retained below. The ranges here keep the original planned release IDs as lookup keys; the order above governs delivery. Optional reserved slots are available for audited cards only after all their dependencies pass. They never count as shipped work by themselves.

### Sprint 15 — Dice on stack + roll control

R15.1–2 add a roll stack kind and resumable consumers in `engine/stack.py`, `game_loop.py`, `common/combat.py` and `common/effects.py` after early R16/R23 contracts. R15.3 supports roll branches, flip, set and add; R15.4 wires The D6 and Lucky Foot, R15.5 Dice Shard and Godhead. R15.6–7 remain optional packs. R15.8 requires attack and non-attack responses, reroll by original controller, category-restricted Lucky Foot, bounds 1–6, source cancellation, final-only observer and unchanged seeded replay. Reserve the pre-final and continuous-modifier stages; Sacred Heart/Bum-Bo! require those later providers. Integrate Cursed Gaper once R23 group selection and per-beneficiary expiry are available, independently of full R25 statics.

### Sprint 16 — Cancel / response stack interaction

Pull R16.1 stack-kind metadata ahead of R15. Include source kind, ability ID, mode and captured controller. R16.2 uses one cancelable entry per printed ability with ordered effects. Expose tap/paid item IDs and explicit costs here for The Bone, Battery Bum and No!; compound payments wait for R21. R16.3 wires No!, R16.4 filters Butter Bean targets, R16.5–6 remain optional. R16.7 exit: cancel a paid item ability without refunding it, reject a roll as a Butter Bean target, discard one canceled physical loot and zero synthetic copies. Depends on early R23 decisions for mode/target choice.

### Sprint 17 — Priority auto-advance

R17.1–3 put pass-only advancement in the referee, bind legal actions/decisions to a viewer, project private hands and events, and adapt `cli/render.py`, `cli/app.py` and trusted bots. Retain explicit passing anywhere another action is legal; support entitled loot/item responses during START/END. R17.4–5 reserved; R17.6 exit: two states differing only in an opponent hand or secret order serialize identically to the viewer. A character-granted off-turn play remains available to its owner. Current priority, active player and decision owner can differ. An interactive handoff must avoid leaving private cards on a shared terminal. Depends on early R23 chooser contract; R18/19 consume the public interface.

### Sprint 18 — Statistics pipeline

R18.1–3 ship a bounded headless runner and streaming aggregation with run metadata (revision, deck hash, seeds, policies, cap policy), winner/turns, capped games and reasons. Keep independent per-game RNG streams and a configurable trace sink. R18.4–5 optional benchmark fixtures. R18.6 exit: same 20 seeds twice produce identical per-seed outcomes/events, short batch equals the concatenation of shards, wins plus caps/errors equals attempts, and peak memory stays bounded with summary-only output. Publish games/s, commands/s and cap rate. Depends on stable actions/decisions and R17 for fair-agent measurements; the diagnostic seed panel runs today. Million-game throughput is a measured later target.

### Sprint 19 — Heuristic bot

R19.1–3 score public legal actions/decisions, including off-turn choices, and compare policies on paired seeds with reversed seats. R19.4–5 optional. R19.6 exit: reproduce a 500-game comparison with wins/losses/caps, seat split and uncertainty; retain the historical 55% target as an experiment. Requires R17 and R18. Bot strength does not gate V2 rules delivery.

### Sprint 20 — Trinkets + pile targeting

Pull the incarnation part of R20.1 forward for slot targets, rolls and beneficiaries. Complete pile selection, multi-card inspection/reorder, reveal, search/shuffle, recycling, expand/refill, and conservation after R17 private decisions. R20.2 models trinket entry carrying loot origin; R20.3 integrates pile abilities including We Need to Go Deeper! after R23 attack grants. R20.4–5 optional; R20.6 exit: short pile reorders preserve exact identities, buried cards have no active subscriptions, a previously covered ref becomes a fresh incarnation, a destroyed trinket goes to loot discard. Private “look”/continuous permission and public “reveal” have distinct views.

### Sprint 21 — Player interaction

R21.1–2 reuse R20 zone/ownership and R23 decision contracts for give, steal, swap, rotate, chooser-owned discard and compound costs. Include turn-relative neighbors, seeded random selection including self where printed, optional decisions and Remote Detonator ballots. R21.3 pack: Decoy, Incubus, Chaos or Remote Detonator after their own dependencies. R21.4–5 optional; R21.6 exit: exchange two items atomically with counters preserved, a previously activated ability resolves for its original controller, private hand selection goes to the proper seat, ties destroy nothing, failed costs leave all assets untouched.

### Sprint 22 — Curses + rooms

R22.1/R22.3–4 deliver curse entry, transfer, owner-bound subscriptions and removal on owner death, then optional outside-game bonus souls, threshold checks, permanent retirement and victory on any grant/transfer. Depends on R20 incarnation/origin, R23 timing and R24 death/soul value. R22.6 exit: Curse of Loss fires at the correct death stage and leaves once; Soul of Greed is claimed at the threshold and cannot be reclaimed after destruction. R22.2/R22.5 room deck/room pack explicitly deferred beyond Base V2. This frees the original room capacity for the three audited bonus souls.

### Sprint 23 — Trigger queue

Pull the decision/continuation part of R23.1–2 forward. Add the event and producer through the shared dispatcher; extend registration from monsters to items, characters, curses and outside-game listeners as those zones ship. R23.3 orders simultaneous triggers by rules, including the appropriate player's ordering decision. R23.4 adds start/end, purchase/attack declaration before/after target selection, optional/mandatory allowances, future/skip turns, force-end cleanup and pre/post-reward timing with R24. R23.5 shares one R15 final-roll notification. R23.6 exit: no stale registration, no event doubled, no priority inside a single instruction sequence except rules-defined interruptions. Cursed Psy Horf listens to successful item activation, including a paid ability, and ignores a character tap. Verify observed roller, active seat and captured controller independently.

### Sprint 24 — Replacement effects

R24.1 extends selected combat interception to shared, observable amount/recipient transactions for gain/loot, loss, acquisition, destruction, prevention and replacement. R24.2 models pending damage with origin, cause, combat/ability and actual positive amount; R24.3 provides resumable monster/player death and cleanup, holding zone, exact destination, replaceable rewards, soul values and victory check. R24.4 adds affected-player ordering and once-per-event application; depends on early R23 decisions and R16 metadata. R24.5 exit: Wizoob's two owners and loot-three order through normal play, a boss never in both discard and souls, lethal damage to a non-attacker, zero damage and direct kill differentiated. Variable/doubled rewards and rolled prevention also require R15. Test a short reward deck, simultaneous deaths and before/after penalty triggers separately.

### Sprint 25 — Continuous effects + static ability layer

Start R25.1–2 after R20 identity to derive ordinary HP, ATK, evasion, roll modifiers, hand limits, loot/purchase/attack allowances and shop cost from current sources. R25.3 adds evolving conditions, targeting/attack restrictions and private top-card permission. R25.4 covers counters, first/every-N occurrence and effective characteristics for R26 copies. R25.5 exit: Stoney cannot be attacked but can be damaged, buffs vanish when it leaves; Cursed Gaper's already granted buffs persist on surviving recipients. Repeated queries never accumulate stats. A change of control/hand size refreshes conditions. Depends on R15 only for roll-dependent statics and on R24 only for replacement-dependent behavior. Death’s Head remains an out-of-set probe.

### Sprint 26 — Base Game V2 closure

Deliver remaining audited items, loot, monsters, characters, curses and events in small packs as their capability families pass. Include copying an ability vs copying a loot/physical item, delayed/conditional effects, setup exceptions (Eden, Cain), vote and deck-search rulings, Guppy tags, optional bonus souls and catalog validation. Revisit original short entries as well as later detailed rows. R26 owns every residual test and card-specific edge case in [the 370-row routing index](EFFECT_INVENTORY.md#audit-row-routing), even if an earlier feature has shipped.

**Exit:** each of the 287 distinct designs has a matching edition-specific definition, normal setup/entry, every required ability and a reproducible normal-play test. Verify the 20 provisional representative IDs and reconcile 53 extra copies to reach 340 exact physical entries, filtering by player count/options. Reject missing, duplicate or unknown manifest IDs. Run mixed-deck seeded matches with conservation, winner rules, replay and cap diagnostics. Publish verified numerator, remaining open rulings and exact profile. Full V2 release requires closure of all blocking rulings; expansions and rooms stay outside it.

## Open rules and operating assumptions

| Decision to settle | Owner and gate |
|---|---|
| Which obligation is consumed when several restricted and unrestricted attack grants can satisfy one declaration? What if none is legal? | R23.4 before certifying Portal/Conquest/Ambush. Resolve against declaration rules and test multiple simultaneous grants, optionality, cancel and forced end. |
| At which damage stage and amount do Dople/Evil Twin/Rage Creep duplicate, and how are linked instances prevented or replaced? | R24 before these cards. Preserve cause/recipient links and test two seats, both neighbor directions and shields without recursive duplication. |
| Does a canceled first attack roll consume the ordinal for Polydactyly/Curved Horn? How do roll ordinal and continuous modifiers interact? | R15 captures stable roll identity; R25 resolves the ruling before granting either design credit. Rerolling the same die never creates a second identity. |
| Per-card ambiguities on optional choices, costs, source movement and alternate destinations | Each audit assessment records the disputed case. The owning capability milestone supplies a ruling or retains it in R26. Add the official citation and a discriminating test; keep unresolved cases out of verified totals. |

The [extended rulebook](https://foursouls.com/rules/extended-rulebook/) governs timing, refills, targets, rolls, damage and zone changes. The [historical proposed R15–25 breakdown](https://github.com/alepiaz/FourSouls/blob/0e668c1a524288e3fdebb24eca03f9471178641c/ROADMAP.md#L196-L487) preserves the original detail. History below is the completed scope at the relevant release, with PR #6 status called out separately.

## Status at a glance

Historical releases through Sprint 14.5. Future release IDs, outcomes and dependencies are listed above.

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
| 13.5 | Ability architecture refactoring | ✅ done — R13.5.1–R13.5.8 complete |
| 14 | Combat miss on stack + cancel | R14.1–4 and R14.6 merged. R14.5 is an optional card slot. |
| 14.5 | Stabilization & integration | ✅ done — merged PR #3; CI passed |

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

**Historical Sprint 13 infrastructure (the callback fields below were retired by PR #5):**
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
| R13.5.2 | Domain event dispatcher and zone-aware subscriptions | ✅ complete |
| R13.5.3 | Typed condition evaluator and event/source matching | ✅ complete |
| R13.5.4 | Shared effect registry and composable atomic effects | ✅ complete |
| R13.5.5 | Target resolution, identity, costs, durations and usage limits for current scope | ✅ complete |
| R13.5.6 | Minimal trigger queue and replacement/prevention adapter | ✅ complete |
| R13.5.7 | Migrate all seven Sprint 13 monsters; remove superseded specialized handlers and direct monster-ability dispatch from core | ✅ complete |
| R13.5.8 | Regression, composition and deterministic integration tests | ✅ complete |

**Acceptance criteria:**
- Gaper, Horf, Big Spider, Carrion Queen, Headless Horseman, Bony and Mega Fatty retain their existing verified behavior.
- A new combination of an existing trigger, condition and effect can be expressed in YAML without a new Python handler or changes to the game loop.
- Tests exercise multiple simultaneous subscriptions, covered/uncovered sources, death triggers, cancellation/fizzle, independent per-instance usage and duration cleanup.
- No duplicate dispatch or recursive resolution; same seed and commands yield the same state/events; all existing regression tests remain green on Python 3.11 and 3.12.
- Loot and treasure legacy paths remain compatible; migrate them when touched by later releases rather than broadening the sprint into a rewrite.

**Implementation files:** `foursouls/model/abilities.py`, `foursouls/engine/ability_engine.py`, `foursouls/engine/event_dispatcher.py`, existing effect/target/stack models and card YAML loaders.

---

## Sprint 14 — Combat miss on stack + cancel
**Branch status:** R14.1–3 shipped first. PR #6 merged the R14.4 effects and R14.6 inventory and acceptance tests at `c7e8ff7`. R14.5 is optional.

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
- ✅ R14.4 — `DestroyItemEffect` + `HealEffect` + `ForceAttackEffect` (remaining gap fills); `HealMonsterEffect` implemented in R13.7, integrate with shared effect registry
- R14.5 — Optional card insertion slot remains reserved
- ✅ R14.6 — Acceptance tests and [first effect inventory snapshot](EFFECT_INVENTORY.md)

**Effect inventory milestone:** Use Base Game V2 as the initial corpus. Track one row per ability with card ID and source, trigger, conditions, cost, chooser and target, atomic effects, duration and usage limit, implementation status, and regression test. Distinguish shared YAML support, legacy-only support, and missing primitives or timing. Start with the effects shipped in Sprint 14 and publish the coverage boundary of the first snapshot. Track remaining corpus coverage separately from engine implementation.

**Dependency:** The R14.4 implementation uses the merged Sprint 13.5 foundation.

**Key files:** `foursouls/rulesets/common/combat.py`, `foursouls/rulesets/common/effects.py`, `foursouls/model/target.py`, `foursouls/engine/actions.py`, `foursouls/cards/loot.py`

---

## Sprint 14.5 — Stabilization & integration

- Fix active-player vs priority-holder legality and item ownership.
- Discard cancelled and fizzled loot, including defensive stack cleanup.
- Populate demo decks with registered cards and remove duplicate effect class.
- Explicit package discovery and YAML package data.
- Add regression tests; require a passing full suite before declaring completion.
- Completed and merged via PR #3 (`c38b712`); CI passed. Mandatory deck attacks are addressed by Sprint 13; the Sprint 13.5 foundation subsequently merged via PR #5.
