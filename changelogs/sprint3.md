# Sprint 3 — Shop

### 1) Sprint / commit context

**Sprint:** Sprint 3  
**What's done vs partial:**

Done:
- R3.0 — `SlotsZone.is_occupied/is_empty` helpers; `PlayerState.gain_treasure()` + `treasures` property; shop slot and player treasure area tests
- R3.1 — Setup fills shop deterministically; tests for zone isolation and no cross-contamination
- R3.2 — `BuyShop(slot_index)` command; `TREASURE_COST = 10`; full legality matrix (6 conditions); stub in `game_loop`
- R3.3 — `on_buy_shop` handler: deducts cents, moves card, sets `purchase_used`; `TreasureBought` event
- R3.4 — Slot refill from treasure deck after purchase; empty-deck path leaves slot empty
- R3.5 — Integration hardening: earn-then-buy chain, EndTurn cleanup with purchase, two-turn purchase cycle
- R3.6 — `economy_bot` agent; deterministic acceptance slice driven by the bot

Partial / skipped:
- No treasure activated abilities (treasures are owned but inert)
- No cost modifiers or discounts
- No combat, monster interaction, passive/triggered treasure text
- No soul system
- No top-of-deck buy

---

### 2) Files changed

**New files**

- `foursouls/rulesets/common/shop.py` — `on_buy_shop(game, slot_index)`: clears slot, deducts `TREASURE_COST`, calls `gain_treasure`, sets `purchase_used`, refills slot from treasure deck if non-empty, emits `TreasureBought`
- `agents/economy_bot.py` — shop-aware bot; priority: `BuyShop` → `PlayLoot` (real cards only) → `EndTurn` → `PassPriority`
- `tests/test_shop_state.py` — 16 tests: `SlotsZone` primitives, shop fill after setup, player treasure area (R3.0)
- `tests/test_buy_shop.py` — 12 tests: resolution mutations, purchase-limit enforcement, `TreasureBought` event, zone isolation, `purchase_used` reset on `EndTurn` (R3.3)
- `tests/test_shop_refill.py` — 11 tests: refill from top of deck, determinism, empty-deck path, neighboring slots unchanged, zone isolation (R3.4)
- `tests/test_sprint3_loop.py` — 11 integration tests + `test_sprint3_integration_full_flow` + `test_sprint3_acceptance_economy_bot` (R3.5/R3.6)

**Modified files**

- `foursouls/engine/zones.py` — `SlotsZone`: added `is_occupied(idx: int) -> bool`, `is_empty(idx: int) -> bool`
- `foursouls/model/player_state.py` — added `gain_treasure(ref: CardRef) -> None`; added `treasures: List[CardRef]` property (live alias for `items`)
- `foursouls/model/commands.py` — added `BuyShop(slot_index: int, kind="BUY_SHOP")` frozen dataclass
- `foursouls/engine/events.py` — added `TreasureBought(player_id, card_ref, slot_index, cost)`; added `CardRef` import
- `foursouls/rulesets/common/legality.py` — added `TREASURE_COST = 10`; added `BuyShop` import; `BuyShop` generation block: legal when ACTION + empty stack + slot occupied + `cents >= TREASURE_COST` + `not purchase_used` + `zones is not None`
- `foursouls/engine/game_loop.py` — `step()` dispatches `BuyShop` to `on_buy_shop`; added `BuyShop` and `on_buy_shop` imports
- `tests/test_setup.py` — 4 new tests: shop cards are subset of treasure input, no double-counting, zone isolation, fill order determinism (R3.1)
- `tests/test_legality.py` — 7 new `BuyShop` legality tests; added `_make_zones` / `_game_with_shop` helpers; added `TREASURE_COST`, `BuyShop`, zone imports (R3.2)

---

### 3) Public API changes

```python
# New command:
BuyShop(slot_index: int, kind="BUY_SHOP")   # frozen dataclass

# New event (engine/events.py):
TreasureBought(player_id: PlayerId, card_ref: CardRef, slot_index: int, cost: int)

# New constant (rulesets/common/legality.py):
TREASURE_COST: int = 10   # default shop cost; used by legality and on_buy_shop

# New ruleset hook (rulesets/common/shop.py):
on_buy_shop(game: Game, slot_index: int) -> None

# SlotsZone extended (engine/zones.py):
SlotsZone.is_occupied(idx: int) -> bool
SlotsZone.is_empty(idx: int) -> bool

# PlayerState extended (model/player_state.py):
PlayerState.gain_treasure(ref: CardRef) -> None
PlayerState.treasures: List[CardRef]   # property; live alias for .items

# New agent:
agents.economy_bot.choose_command(game: Game) -> Command
```

---

### 4) Behavioral rules implemented

- **Shop zone:** `shop_slots` (`SlotsZone[CardRef]`) is the official public shop zone, owned by `GameZones`. `setup_game` fills it from the treasure deck before returning. If the deck has fewer cards than `shop_size`, remaining slots stay `None`.
- **Buy legality:** `BuyShop(slot_index)` is legal only when: phase is `ACTION`, stack is empty, `game.zones` is set, the target slot is occupied, `active_player.cents >= TREASURE_COST`, and `turn_flags.purchase_used == False`.
- **Buy resolution (immediate):** No stack push — buying is immediate. Slot cleared → `cents -= TREASURE_COST` → card appended to `player.items` → `purchase_used = True` → refill attempted → `TreasureBought` emitted.
- **Slot refill:** After each purchase, the emptied slot is refilled by drawing one card from the top of `treasure_deck`. If the deck is empty, the slot remains `None`. Refill is part of the same `step()` call, not deferred.
- **Once-per-turn purchase:** `TurnFlags.purchase_used: bool` gates `BuyShop` legality. It is reset to `False` by `TurnFlags.reset()`, called inside `reset_for_new_turn()` at `EndTurn`. No changes to the reset path were needed.
- **Treasure ownership:** Bought cards live in `PlayerState.items`. `gain_treasure()` is the canonical write path. `treasures` is a read-only property alias. Treasures are inert — no effects fire on acquisition.

**Ambiguities picked:**
- `TREASURE_COST = 10` cents for all treasures. No per-card cost exists yet; a flat constant avoids a premature cost model while satisfying legality and effect correctness.
- Refill is immediate (same step as the buy), not deferred to end of turn. This matches the physical game and keeps the shop board visible at all times.
- `purchase_used` is a simple bool, not a counter. The base rule is exactly one purchase per turn; a counter would be premature.

---

### 5) Critical decisions

| Decision | Choice | Why |
|---|---|---|
| Buy is immediate, not stacked | No stack push in `on_buy_shop` | Legality already requires empty stack. Buying has no meaningful response window in the base game. Keeps the flow simple. |
| Refill in `on_buy_shop`, not a separate hook | Inline after purchase | Refill is a deterministic side-effect with no response window. A separate hook would add indirection without benefit at this scope. |
| `TREASURE_COST` constant in `legality.py` | Not on `CardRef` or a separate cost table | Sprint 3 has no per-card costs. A named constant in the legality module is readable, testable, and easy to replace in Sprint 4+ when a real cost model is introduced. |
| `PlayerState.items` kept, `treasures` added as alias | No rename | Renaming `items` would break all Sprint 1–2 tests. `treasures` as a property makes intent explicit without touching the backing field. |
| `economy_bot` skips cards with `card_id=None` | `if cmd.card_ref.card_id is not None` guard | Placeholder loot cards (used in test setup without a catalog entry) would crash `make_loot_effect`. Skipping them is correct bot behavior and avoids leaking test-setup details into the agent. |

---

### 6) Tests added/updated

**New test files:**
- `tests/test_shop_state.py` — 16 tests: `SlotsZone` set/clear/occupied/empty/OOB, filled/empty indices complete partition, shop fill after `setup_game`, short treasure deck, determinism, player treasure area isolation and growth
- `tests/test_buy_shop.py` — 12 tests: cents reduced, slot cleared, card in player area, correct slot targeted, `purchase_used` set, second buy raises `ValueError`, illegal buy makes no mutation, `TreasureBought` emitted with correct fields, other slots unchanged, other player unaffected, loot deck untouched, flag resets on `EndTurn`
- `tests/test_shop_refill.py` — 11 tests: slot occupied after refill, top-of-deck card used, deterministic refill, deck shrinks by 1, refill card absent from deck, empty deck leaves slot empty, neighboring slots unchanged, refill in correct slot index, loot deck untouched, treasure discard untouched
- `tests/test_sprint3_loop.py` — 12 tests: buy legality gated by cents, once-per-turn limit, buy removes card from shop, refill with non-exhausted deck, empty-deck slot stays empty, EndTurn cleanup still works, two-turn purchase cycle, earn-then-buy chain, loot quota orthogonal to purchase quota, scripted integration target, economy-bot acceptance slice

**Updated test files:**
- `tests/test_setup.py` — 4 new tests: shop cards subset of treasure input, no double-counting with remaining deck, loot/monster zone isolation, fill order determinism
- `tests/test_legality.py` — 7 new `BuyShop` tests (legal with enough cents, illegal outside ACTION, illegal with non-empty stack, illegal for empty slot, illegal with insufficient cents, illegal after purchase used, illegal when all slots empty); added `_make_zones` / `_game_with_shop` helpers

**Not yet covered (known gaps):**
- Treasure activated abilities
- Passive and triggered treasure text
- Cost modifiers or discounts
- `BuyShop` in a game with multiple players all having different cent totals (multi-player economy)

---

### 7) Current demo path

```
pytest -q tests/test_sprint3_loop.py::test_sprint3_acceptance_economy_bot
```

Verbal walkthrough:
1. `setup_game(seed=13)` — decks shuffled, hands dealt (3 each), shop filled (3 slots), Loot1 queued for P1
2. P1 starts with 9 cents and one `LOOT_COIN_1` in hand
3. Economy bot drives START phase: passes until Loot1 resolves, passes into ACTION
4. Bot sees `PlayLoot(coin)` is legal (real card) → plays it; PASS/PASS → 10 cents
5. Bot sees `BuyShop(0)` is legal → buys; slot cleared → 0 cents → treasure in P1's area → slot refilled from deck
6. Bot sees `EndTurn` is legal → ends turn; `purchase_used` resets, P2 becomes active, turn 2 begins
7. Assertions: P1 owns 1 treasure, 0 cents; all 3 shop slots occupied; deck shrank by 1; P2 active; `purchase_used = False`

---

### 8) Problems / open questions

- **Inert treasures:** Bought cards live in `PlayerState.items` but have no effects. Sprint 4 will need a mechanism to activate, trigger, or passively apply treasure text.
- **Flat cost:** `TREASURE_COST = 10` is hardcoded. Real Four Souls treasures have individual costs. A per-card cost lookup (catalog or `CardRef` metadata) is a Sprint 4 concern.
- **No multi-purchase rule variants:** Some Four Souls items or effects allow multiple purchases per turn. The current `purchase_used: bool` model supports exactly one. Converting to a counter (`purchases_used / purchases_allowed`) mirrors the loot quota pattern and can be done when needed.
- **Inherited open questions from Sprint 2:** Fizzled loot limbo; Bomb self-target only; single hardcoded character ability.
