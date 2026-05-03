# Implementation Status vs Rules.md

Legend:
- ✅ Implemented
- ⚠️ Partial
- ❌ Missing
- Complexity of missing work: [Trivial] [Easy] [Medium] [Hard] [Complex]

---

## Anatomy of a Card

**Name Box — "Contains a card's name."**
- ✅ Every card definition (`TreasureDef`, `MonsterDef`, `CharacterDef`, loot constants) carries a `name: str` field.

**Text Box — effect text, gray text, ability tags, dividing lines.**
- ✅ Effect text is modelled as Python callbacks (`make_tap_effect`, `event_effect`, `on_enters_play`, etc.) — the mechanical content is fully captured.
- ❌ Gray/flavor text is absent. Not needed for engine correctness; relevant only for a UI that wants to display card text verbatim. [Trivial] — add an optional `flavor: str` field to card defs.
- ⚠️ Ability tags (↷ vs $): implicit from whether `make_tap_effect` is present vs a cost-paying effect. No explicit `ability_type` enum on the data model, so tooling cannot inspect which tag a card has without reading the callback. [Easy] — add an `ActivatedAbilityKind` enum (`TAP | PAID`) to `TreasureDef`.
- ❌ Multiple distinct abilities on a single card: each `TreasureDef` currently supports exactly one `make_tap_effect` callback. Cards with both a ↷ and a $ ability, or two separate ↷ abilities, cannot be expressed. [Medium] — replace the single callback with a `list[AbilityDef]`, each carrying its kind, cost, and effect factory.
- ❌ Roll abilities with branching outcomes (bullet-point outcomes): no dedicated data model for "roll → outcome table". Currently ad-hoc inside individual effect callables. [Medium] — a `RollAbilityDef(outcomes: dict[int, Effect])` structure would make these declarative.

**Stat Box — Health, Evasion, Attack.**
- ✅ Monsters: `MonsterDef.hp`, `.evade`, `.attack` — all three stats present.
- ✅ Characters: `CharacterDef.base_hp`, `.attack` — correct; characters have no default evasion (it is specified by whichever ability enables player-vs-player combat).
- ❌ Attackable items and rooms have stat boxes in the rules but the engine has no item/room stat blocks. [Hard] — requires making items/rooms valid combat targets with their own `hp`, `evade`, `attack` fields and a `Familiar`-keyword path in legality.

**Reward Box — "When an object with a reward box dies or is destroyed, the active player gains rewards."**
- ✅ `MonsterDef.reward_cents`, `.reward_loot`, `.reward_treasure`, `.has_soul` are all read in `resolve_monster_death()` and granted to `active_player_id`.
- ❌ Reward box on items and rooms (attackable objects). Not needed until those are implemented. [Trivial once attackable items exist] — same reward-processing call, different caller.

**Soul Icon — "Indicates the soul value the card would provide if gained as a soul."**
- ⚠️ `MonsterDef.has_soul` is a boolean. Soul value is hard-coded as 1 per entry. A card worth 2 souls (e.g. an epic boss) would be miscounted. [Easy] — replace with `soul_value: int = 0`; adjust win-condition check to sum values.

**Set Symbol — "Informs you of the card's origin set."**
- ❌ No `set_id` or equivalent field on any card def. Not needed mechanically. [Trivial] — add an optional `set_id: str` to card defs for future filtering.

**3+ Player Only Symbol — "Remove this card when playing solo or with 2 players."**
- ❌ No `min_players: int` field; no filtering at setup. Any 3+-only card would silently enter the game regardless of player count. [Easy] — add `min_players: int = 1` to card defs; filter in `setup_game()` before shuffling.

---

## Game Zones — General Rules

**"If a card moves from one game zone to another it is considered a new object. Any abilities that targeted it before it moved will fizzle."**
- ⚠️ `CardRef` is built from a stable `InstanceId` (a `NewType(str)` assigned once at creation) that never changes when a card moves zones. If an ability targets a `CardRef` and that card changes zones before the ability resolves, `validate()` on the effect does check game-state validity (e.g. "is this `ItemInPlay` still in this player's items list?"), so it will correctly fizzle in most practical cases. However the fizzle is a side-effect of state checking rather than an explicit zone-identity rule; edge cases (e.g. a card that returns to the same zone it left) would not fizzle when they should.
  [Medium] — proper fix: generate a fresh `InstanceId` (e.g. `uuid4`) every time a card enters a new zone; store the expected zone alongside the `CardRef` in targeting data; `validate()` checks both.

**"In play includes all objects a player controls, and the topmost object in any shop/monster/room slots. In play is a public zone."**
- ✅ Player-controlled objects (`character`, `items`, `souls`) and topmost slot occupants are the only things legality and effect code operate on.
- ❌ Room slots not present.
- ⚠️ "Public zone" enforcement: the engine model is correct (everything in play is accessible) but there is no view-filtering layer — the CLI and any agent can read all in-play state directly.

**"Abilities only check for or target objects that are in play, unless otherwise specified."**
- ⚠️ Partially enforced. Each effect's `validate()` checks whether the target is still in the expected location (e.g. still in a monster slot, still in a player's items). There is no universal gate that prevents an effect from targeting an out-of-play object, so a new effect implemented without a proper `validate()` could silently target non-in-play objects.

---

## Decks

**"Four deck zones: Treasure, Loot, Monster, Room."**
- ✅ `DeckZone` instances for Treasure, Loot, and Monster exist in `GameZones`.
- ❌ Room deck absent.

**"Each deck can only contain cards of the corresponding type."**
- ⚠️ `DeckZone` is a generic `List[T]`; no type enforcement inside the zone itself. Correctness relies entirely on calling code sending the right card type to the right deck. A programming mistake would not be caught at runtime. [Easy] — parameterise `DeckZone` on an enum tag (`DeckKind`) and assert on `put_on_top` / `put_on_bottom`.

**"Bonus souls and cards like The Harbingers don't have a deck and can't be put into one."**
- ❌ Not enforced (bonus souls not implemented). Rule is implicitly respected because those cards are never added to a deck in the current code.

**"Decks are hidden information. Cards can't be viewed or reordered unless an ability instructs."**
- ⚠️ Hidden info: `DeckZone.peek()` is a public method with no access control; any code (or agent) can call it freely.
- ⚠️ Order protection: `DeckZone.cards` is a public list accessible and mutatable directly. No guard prevents arbitrary reordering.
- In practice neither issue matters for the current rule-correct engine (effects only call `draw()`, `put_on_top()`, `put_on_bottom()`, `shuffle()` when appropriate), but it is an honour-system rather than an enforced invariant.
  [Easy] — make `cards` a private `_cards` attribute; expose only the intentional mutation methods; remove or gate `peek()` behind an ability-context parameter.

**"If a deck runs out of cards, immediately shuffle the appropriate discard pile and make that the new deck."**
- ✅ Handled in `GameZones` (the draw-with-reshuffle logic). `DeckZone.draw()` itself raises `ZoneEmptyError`; the reshuffle is the responsibility of the caller, which is consistently `GameZones`.

---

## Discard

**"Four discard zones, one per deck type."**
- ✅ `DiscardZone` instances for Treasure, Loot, and Monster in `GameZones`.
- ❌ Room discard absent.

**"Cards that don't correspond to a certain discard can't be put into that discard."**
- ⚠️ `DiscardZone` is generic; no type enforcement. Same situation as decks — calling code convention rather than a runtime guard. [Easy] — same fix as decks: tag `DiscardZone` with a `DeckKind` and assert on `add()`.

**"A card put into discard is put on top of that discard."**
- ✅ `DiscardZone.add()` appends to the end of a list; `DiscardZone.top()` returns `cards[-1]`. Semantically correct (last added = top).

**"If a card or object doesn't have a discard, it is instead removed from the game."**
- ❌ No "remove from game" action exists. If a non-standard card were somehow sent to discard routing, there is no fallback path to an out-of-game zone; it would likely cause an error or be silently dropped. [Easy] — add a `removed_from_game: list[CardRef]` collection to `GameZones`; route unroutable cards there.

**"Discards are a public zone; order can't be changed unless instructed."**
- ⚠️ Public-zone: not enforced, but model is flat and readable.
- ⚠️ Order protection: `DiscardZone.cards` is a public list. No guard against arbitrary reordering. [Easy] — same private-field fix as decks.

---

## Hand

**"Each player has their own hand zone. The hand only ever consists of loot cards."**
- ✅ Each player has a `HandZone` in `GameZones`. Convention keeps it loot-only.
- ❌ No type guard preventing a non-loot card from entering the hand. The rules say "if instructed to move a non-loot card into hand, nothing happens" — this is not enforced; a non-loot card would be silently added. [Trivial] — add a loot-type check in `HandZone.add()` or in the effect that calls it.

**"A player's hand is a hidden zone; cards only viewable by the controlling player. The count is public."**
- ⚠️ Hidden-zone: not enforced. `HandZone.cards` is a public list readable by anyone. The CLI and agents can see all hands. This is intentional for single-device play but would need a view-filtering layer for networked or AI-vs-human play. [Medium] — access-control layer at the CLI/API boundary; engine-level model is fine as-is.
- ✅ Card count: `len(hand)` is always accessible.

**"If instructed to discard a loot card, a loot card of the player's choice is moved to the loot discard."**
- ✅ The death penalty discards the first card in hand. A general player-choice discard (e.g. from an ability) is implemented via effect classes that call `hand.remove(card)` and `loot_discard.add(card)`.

**"If instructed to gain a loot card, it is moved from its previous zone into that player's hand."**
- ✅ `DrawLoot1Effect` and `AllPlayersDrawLootEffect` both call `hand.add(card)` after drawing from the loot deck.
- ⚠️ "From its previous zone": when looting from the deck the source zone is correctly the loot deck. Gaining a loot card from a non-deck zone (e.g. directly from discard, or from another player's hand) is not generically supported as a zone-transfer; those paths would need specific effect implementations. [Easy per case] — each ability that does this would need its own effect; the framework supports it but no generic "move loot from zone X to hand" effect exists.

---

## Covered in a Slot

**All rules in this section.**
- ❌ Entirely absent. `SlotsZone` is a flat `List[Optional[T]]` with one item per slot index (see `engine/zones.py`). There is no inner stack, no "covered" concept, and no mechanism to place a card on top of an occupied slot while keeping the occupant present.

The rules that depend on this zone:
- Attacking the top of the monster deck reveals it and places it on a slot, covering the existing monster — **not implemented** (attacking the top of the deck is itself unimplemented).
- Ambush loot cards become a monster in a chosen slot, potentially covering another — **not implemented**.
- "Cards covered in a slot are not in play" — **not enforced** (no covered state exists).
- "When the covering card leaves play, the covered card re-enters play (firing on_enters_play for Ambushes and Trinkets)" — **not implemented**.
- "Covered in a slot is a public zone" — **not implemented**.
- "Order of cards in a slot can't be changed unless instructed" — **not applicable** (no stacking).

  [Hard] — foundational change required. `SlotsZone` slots need to become `List[List[T]]` (a stack per slot). Every place in `combat.py`, `setup.py`, `legality.py`, and `shop.py` that reads `slot[idx]` must use `slot[idx][-1]` (top of inner stack). A new `uncover_slot(idx)` helper must pop the top card, put the result into discard/game as appropriate, and fire `on_enters_play` for what becomes newly uncovered. This is a prerequisite for the blind monster-deck attack feature, Ambush cards, and any card that stacks monsters.

---

## The Stack (Zone)

**"The stack is a zone where loot, abilities, dice rolls, and other things go to resolve."**
- ✅ `Stack` class in `engine/stack.py`. Each `StackItem` carries a `stack_id`, `controller_id`, `effect` (an `Effect` protocol instance), and `source` (`CardRef`). LIFO ordering is maintained.

**"A loot or ability resolves when each player passes priority in succession."**
- ✅ `PriorityManager.all_passed()` triggers resolution of the top stack item in `game_loop.py`.

**"If a loot or ability is canceled, it is removed from the stack without resolving. Loot cards removed this way go to the loot discard."**
- ⚠️ `CancelStackItemEffect` (triggered by Butter Bean) removes the target `StackItem` from the stack. However, when a `PlayLootEffect` wrapper is the item canceled, the loot card has already been removed from hand but the wrapper's discard step never runs — the card could be left in limbo. The cancel correctly targets the inner loot effect in current card implementations (Butter Bean targets the activated ability, not the wrapper), but this is fragile. [Medium] — `CancelStackItemEffect` should check if the canceled item is a loot wrapper and explicitly discard the loot card to the loot discard as part of the cancel.

---

## Outside the Game

**"Outside the game = cards not in any of the previously listed zones."**
- ⚠️ There is no explicit "outside the game" zone object in `GameZones`. Cards that start outside the game (characters, starting items) are created directly into play at setup and never tracked as being outside the game beforehand. This is correct in outcome but means there is no query like "which cards are currently outside the game?".

**"Active bonus souls start outside the game and their abilities are active while there."**
- ❌ Bonus souls not implemented. The out-of-game ability-while-outside rule cannot be modelled until bonus souls exist.

**"If instructed to remove an object from the game, it is moved outside the game."**
- ❌ No `remove_from_game()` action or out-of-game collection. Some cards (e.g. Dead Cat) have abilities that remove things. Currently there is no valid destination for such a card. [Easy] — add `removed_from_game: list[CardRef]` to `GameZones`; add a `RemoveFromGameEffect`.

**"Cards under an object not in a slot are considered outside the game (e.g. Friendly Ball)."**
- ❌ No "under an item" mechanic. [Hard] — requires tracking which cards are parked under which in-play object; those cards are outside the game and lose their abilities until the host object leaves play.

**"Face-down cards outside the game are hidden information."**
- ❌ No face-down state tracked anywhere. Relevant for destroyed bonus souls (placed face-down and unclaimable). [Easy] — add `face_down: bool` to the out-of-game record; hide from public queries.

---

## Setup

**"Shuffle the Treasure, Loot, and Monster Decks. Also shuffle the Room Deck, if you are playing with it."**
- ✅ `setup_game()` in `rulesets/common/setup.py` shuffles all three base decks via `RNG.shuffle()`.
- ❌ Room Deck not implemented. [Medium] — requires a new deck zone, a room slot zone, and lifecycle hooks in the END phase.

**"Set aside space for a discard zone next to each of these decks."**
- ✅ `DeckZone` and `DiscardZone` objects exist for each deck type in `engine/zones.py` and `engine/game_zones.py`.

**"Decide on the number of ¢ in the game's ¢ pool. This must be at least 100¢."**
- ✅ `setup_game()` initialises `game_state.cents_pool` to 100. The minimum constraint is not validated at runtime (no guard if someone passes a lower value), but the default is correct.
- ❌ No validation that the pool is ≥ 100. [Trivial] — one assertion in `setup_game()`.

**"Place the top two cards of the treasure deck face up next to it, forming two shop slots."**
- ✅ `setup_game()` draws 2 cards from the treasure deck into `SlotsZone` shop slots.

**"Place the top two cards of the Monster Deck face up next to it, forming two monster slots. Place any event cards put in these slots during setup on the bottom of the deck and replace them. Repeat until both slots have monsters."**
- ✅ `setup_game()` fills monster slots and rejects events (checks `is_event` flag), placing them at the bottom of the deck and retrying, until both slots hold true monsters.

**"If you are playing with the Room Deck, place the top card of the Room Deck next to it, forming a room slot."**
- ❌ Not implemented. [Medium] — see Room Deck note above.

**"If you are playing with bonus souls, shuffle them and pick 3 at random. Place face-up next to the play area."**
- ❌ Bonus souls entirely absent. No `BonusSoulDef`, no out-of-play zone for them, no condition checking.
  [Hard] — requires: a new card type with condition callbacks, an out-of-play tracking zone, win-condition checks after every state change (not just monster death), and the "destroyed → face-down, unclaimable" rule.

**"Deal a random character card to each player, as well as that character's starting item card."**
- ⚠️ Characters are assigned in order (player 0 → index 0, etc.) rather than randomly. The starting item eternal is created and placed correctly. [Trivial] — shuffle the character list before assignment in `setup_game()`.

**"Characters start the game deactivated (turned sideways). Starting items start the game charged (turned upright)."**
- ✅ Characters are created with `tapped=True` (deactivated). Starting eternals are created with `tapped=False` (charged/upright).

**"Abilities that trigger at the start of the game trigger. No one has priority here and so these abilities will all resolve instantly."**
- ⚠️ `_assign_starting_eternals()` calls `fire_on_enters_play()` for each eternal item. This bypasses the stack (correct), but the "no priority" guarantee is implicit rather than explicitly enforced — if `on_enters_play` pushed something to the stack it would silently accumulate before the first START phase. Eden (whose character ability triggers at game start) is not yet a card in the set. [Easy] — add an assertion or explicit comment that on_enters_play at setup must not push to the stack.

**"Deal 3 loot cards and 3¢ to each player."**
- ✅ `setup_game()` deals 3 loot cards into each player's hand and sets `player_state.cents = 3`.

**"The first player will be the saddest player (or use any fair randomisation)."**
- ⚠️ First player is always player 0. No randomisation is applied. [Trivial] — `RNG.choice()` on player indices before the first START phase.

---

## Card Types — Treasure Cards

**"Treasure cards are found in the treasure deck. Whilst in play, a treasure card is referred to as an item. Items are either controlled by a player or in the shop."**
- ✅ `TreasureDef` in `cards/treasures.py`. In-play items tracked in `PlayerState.items` (list of `ItemInPlay`). Shop items tracked in `SlotsZone` shop slots.

**"Any time a card instructs a player to gain treasure, they gain that many cards from the top of the treasure deck, putting them into play under their control."**
- ⚠️ Effects that grant treasure as a *reward* (e.g. a monster rewarding treasure on death) are handled via a `reward_treasure` field on `MonsterDef`, processed in `resolve_monster_death()`. However, there is no general-purpose `GainTreasureEffect` that arbitrary abilities or loot cards can push onto the stack. [Easy] — add a `GainTreasureEffect(n)` effect class that draws n cards from the treasure deck and calls `fire_on_enters_play()`.

**"A player's starting item is considered an item. Starting items intrinsically have the starting item quality."**
- ✅ Starting items are `ItemInPlay` instances with `eternal=True` and are indistinguishable from other items in play. The Eternal quality prevents them from being destroyed or discarded.

**"Item Borders: gold-bordered = has activated abilities; silver-bordered = no activated abilities."**
- ✅ Modelled implicitly: a `TreasureDef` with a `make_tap_effect` callback corresponds to gold-bordered (active/paid), while one without corresponds to silver-bordered (passive). The distinction is never violated at the model level. No explicit `border` field exists because it carries no mechanical weight.

**"Shop Items: can be purchased. Item abilities do not function while in the shop."**
- ✅ Shop items sit in `SlotsZone` (not in any player's `items` list). Triggered/static callbacks on `TreasureDef` are only called via `fire_on_enters_play()` (purchase) and `fire_on_start_of_turn()` (owning player's START phase), neither of which fires for shop items.

---

## Card Types — Loot Cards

**"When a player is instructed to loot, they draw that many cards from the top of the loot deck into their hand."**
- ✅ `DrawLoot1Effect` (and `AllPlayersDrawLootEffect`) move cards from `DeckZone(loot)` into `HandZone`. If the loot deck is empty, `DeckZone` reshuffles the discard.

**"A player's hand is private, but anyone can count the number of cards in a player's hand."**
- ⚠️ Modelled correctly at the data level (`HandZone` per player). The CLI renders full hand contents to all players — there is no hidden-information enforcement in the engine. [Medium] — requires a view-filtering layer at the CLI/API boundary; not needed for single-device play.

**"Players can play loot cards from their hand whenever they have priority and a loot play available."**
- ✅ `legal_commands()` in `rulesets/common/legality.py` emits `PlayLoot` commands only when the player has priority, has a loot play remaining (`loot_plays_used < max_loot_plays`), and is holding a loot card.

**"When loot cards are played they are put onto the stack. When a loot resolves, perform its loot ability, then put it into the loot discard."**
- ✅ `on_play_loot()` removes the card from hand, wraps the effect in `PlayLootEffect` (which handles the discard on resolution), and pushes it to the stack.

**"Some abilities permit playing loot cards from other zones."**
- ❌ No mechanism for playing loot from zones other than hand. [Medium] — would require a zone parameter on `PlayLoot` command and corresponding legality checks.

**"Some abilities permit playing a loot card without using a loot play."**
- ⚠️ The character ↷ ability grants an extra loot play via `GrantExtraLootPlayEffect`, so the quota tracks "extra plays" correctly. A true "play without consuming a loot play" ability (e.g. a card that says "play a loot for free") is not generically supported. [Easy] — add a `free=True` flag to `PlayLoot` command; in `on_play_loot()` skip quota decrement when set.

**"Trinket: when a trinket resolves it becomes an item. Gain it."**
- ❌ Not implemented. Trinkets are listed in the Deck Ratio table but the `Trinket` keyword and its resolution behaviour (loot → item, gains Eternal, placed in play) are absent from the card data and engine.
  [Medium] — requires: `is_trinket` flag on `LootDef`, a `TrinketResolveEffect` that creates an `ItemInPlay` from the loot card's associated `TreasureDef`, calls `fire_on_enters_play()`, and adds it to the player's items instead of discarding it.

---

## Card Types — Monster Cards

**"Whilst in play, monster cards are referred to as either a monster (if they have a stat block) or an event (if they don't)."**
- ✅ `MonsterDef.is_event` flag distinguishes the two. `MonsterInPlay` wraps monsters; events are handled inline in `place_monster_card()`.

**"If an ability on a monster card doesn't specify a particular player, 'you' means the active player."**
- ✅ All monster event effect callbacks receive `game` and use `game.state.active_player_id` as the implicit "you".

**"Abilities on monster cards only function while in play."**
- ✅ Monster callbacks (`on_death`, `on_miss`, `on_would_take_combat_damage`, `on_would_die`) are only called from combat/death functions in `rulesets/common/combat.py`, which operate exclusively on in-play monsters.

**"When a monster is killed, the active player always receives rewards regardless of who killed it."**
- ✅ `resolve_monster_death()` grants rewards (cents, loot, treasure, souls) to `game.state.active_player_id`, unconditionally.

**"Boss cards have a soul icon. Harder, greater rewards, also yield souls."**
- ✅ `MonsterDef.has_soul`. After death, `resolve_monster_death()` appends the monster's `CardRef` to `active_player.souls` and emits `SoulGained`. Win condition is checked immediately after.

**"Event cards have no stat block. All abilities trigger when the card enters play. When all have resolved, put it into the monster discard."**
- ✅ `place_monster_card()` detects `is_event`, fires `MonsterDef.event_effect(game)` wrapped in `EventCardEffect`, and pushes it to the stack. On resolution, `EventCardEffect.apply()` moves the card to the monster discard.
- ⚠️ Each event currently has exactly one effect function. A card with multiple distinct abilities would need a list of effect factories. [Easy] — change `event_effect` from a single callable to a list.

**"Curse cards: active player chooses which player receives the curse. Placed near their character. When that player dies, put curses into discard."**
- ❌ Curse cards not implemented. No `is_curse` flag, no per-player curse list, no discard-on-death hook.
  [Medium] — requires: `is_curse` flag on `MonsterDef`, a curse assignment effect (active player picks target), a `PlayerState.curses` list, and a hook in `resolve_player_death()` that discards all curses from the dead player.

---

## Card Types — Souls

**"When a player controls a card with a soul icon as a soul, it provides a soul value."**
- ✅ Each `CardRef` in `PlayerState.souls` corresponds to a monster with `has_soul=True`. Soul value is 1 per card (all current monsters).

**"When a player controls a total soul value of 4, they win."**
- ✅ `check_win_condition()` (called after every `SoulGained` event) counts `len(player.souls)` and triggers `GameWon` if ≥ 4.

**"Even if a soul has a soul value greater than 1 it is still a single object."**
- ⚠️ The engine stores souls as a flat list of `CardRef`; there is no `soul_value` field per entry. All current cards have value 1, so this is not yet a problem. A boss worth 2 souls would be counted as 1.
  [Easy] — add `soul_value: int = 1` to `MonsterDef`; change win check to sum values instead of counting entries.

**"Abilities that look for the number of souls a player controls refer to the total soul value."**
- ⚠️ Same issue as above. Win condition uses `len(souls)` rather than summing values. [Easy] — same fix as above; abstract a `total_soul_value(player)` helper used everywhere.

---

## Card Types — Bonus Souls

**All bonus soul rules.**
- ❌ Entirely absent. No `BonusSoulDef`, no out-of-play zone, no condition-checking infrastructure, no face-down destroyed state.
  [Hard] — this is a self-contained subsystem. Requires: a new card type, a set of three face-up out-of-play cards at setup, condition callbacks that fire after every relevant state change, and a one-time-claim flag. Most individual bonus souls will each need their own condition implementation.

---

## Card Types — Character Cards

**"A random character card is assigned to each player. While in play, character cards are referred to as characters."**
- ⚠️ Assignment is sequential (not random). Four characters exist: Isaac, Magdalene, Cain, Eve. [Trivial] — shuffle before assigning.

**"A character card may list a starting item. This is a triggered ability that doesn't use the stack."**
- ✅ `_assign_starting_eternals()` creates an `ItemInPlay(eternal=True)` for each character's starting item and calls `fire_on_enters_play()` without going through the stack.

**"Starting items have the keyword ability Eternal."**
- ✅ `ItemInPlay.eternal = True` for all starting items. `resolve_player_death()` skips eternal items when choosing the death penalty item.

**"Character cards have a stat box with Health and Attack stats."**
- ✅ `CharacterDef.base_hp` and `CharacterDef.attack` are read into `PlayerState.max_hp` and `PlayerState.attack` at setup.

**"If an ability allows a player to be attacked by another player, it will specify what their evasion is for that attack."**
- ❌ Player-vs-player attacks not implemented. [Hard] — requires: a new `PlayerAttackTarget`, evasion lookup from the ability that enables it, and extending the combat loop to handle players as defenders (including their death steps mid-combat).

**"A character may be worth souls if it has a soul icon (e.g. The Lost provides 1 soul value)."**
- ❌ No character in the current card set has a soul icon. The rule is not violated but also not modelled. [Easy] — add `soul_value: int = 0` to `CharacterDef`; contribute to `total_soul_value()` computation.

---

## Card Types — Room Cards

**All room card rules.**
- ❌ Entirely absent. Rooms (from the Requiem expansion) are an optional system. No `RoomDef`, no room slot zone, no end-phase discard logic, no room abilities.
  [Complex] — a self-contained expansion module. Requires: new card type + deck zone, a room slot, activated-ability-only-for-active-player restriction, end-phase "discard if monster died" option, and stale-room auto-discard after a full round.

---

## Abilities — General

**"Abilities only function while an object is in play."**
- ⚠️ Enforced by convention rather than by architecture. Monster trigger callbacks (`on_death`, `on_miss`, etc.) are only called from `combat.py` while the monster is in a slot. `on_start_of_turn` and `on_enters_play` on treasure items are only called while the item is in a player's `items` list. There is no universal in-play gate checked before any callback fires — a programming mistake in a new card could invoke an ability from a non-in-play source without triggering any guard.

**"If an ability is activated or triggered and put on the stack, and the object that created it subsequently leaves play before that ability resolves, the ability is not removed from the stack and will still take effect."**
- ⚠️ Partially correct. `TreasureActivateEffect` is built from the `TreasureDef` callback at activation time and pushed to the stack; the `ItemInPlay` that sourced it is not held by reference in the effect wrapper, so destroying the item before the effect resolves does not remove the stack item. However, the `inner` effect inside `TreasureActivateEffect` is often a closure that captured `game` directly rather than a snapshot. If the game-state at resolution differs from at activation (item destroyed, etc.) the closure may behave differently but won't fizzle as intended. This is partially correct in outcome for current cards but is not architecturally guaranteed.
- ❌ Monster trigger callbacks are not put onto the stack at all (see Triggered Abilities below), so this rule is moot for them currently.

**"Targets of abilities are chosen when the ability is put onto the stack, not when it resolves. If the target is no longer valid when it resolves, the ability fizzles."**
- ⚠️ Targets are included in the command at dispatch time (e.g. `ActivateItem.target`, `PlayLoot.target`), which is correct. The target is passed directly to `make_tap_effect(target, game)` and baked into the `Effect` object before it is pushed to the stack — so the target is locked in at stack-push time.
- `validate()` on effects checks target validity at resolution time and returns `False` to fizzle — this is correct.
- ❌ However, fizzle logic is inconsistent. `PlayLootEffect.validate()` delegates to `inner.validate()` — if the inner fizzles, the loot card is never discarded (it is in limbo between hand and discard). The comment in the source acknowledges this: *"If inner.validate() returns False the card remains out-of-zone (limbo)."* [Medium] — `PlayLootEffect` should always discard the loot card regardless of whether the inner validates.

**"'Choose one-' choices are made when the ability is put onto the stack."**
- ❌ No multi-choice ability exists yet. The architecture has no `ChoiceEffect` or branching-at-stack-push mechanism. [Medium] — requires a `ChoiceAbilityDef` that prompts the player at push time and selects a sub-effect to wrap.

---

## Abilities — Costs

**"Costs are effect text followed by a colon."**
- ⚠️ Costs for ↷ abilities (deactivate the item) and $ abilities (pay cents) are checked in `legality.py` before a command is legal and consumed in `on_activate_item()` / `on_activate_character_ability()` before the effect is pushed to the stack — which is correct.
- ❌ No declarative `cost` field on ability definitions. Costs are implicit in the legality check and the activation handler. A new card with an unusual cost (e.g. "pay 1 HP" or "discard a loot card") requires custom legality code and custom activation code rather than declaring `cost=PayHPCost(1)`. [Medium] — add a `Cost` protocol with `can_pay(game) -> bool` and `pay(game) -> None`; store it on `AbilityDef`.

---

## Abilities — Activated Abilities

**"Activated abilities can be activated at any time a player has priority and can pay their costs."**
- ❌ **Bug**: `on_activate_item()` in `rulesets/common/items.py` always looks up the item in `game.state.active_player_id`'s items list, regardless of which player submitted the `ActivateItem` command. If a non-active player has priority and activates one of their own items, the engine looks in the wrong player's items and silently does nothing. Item activation is effectively restricted to the active player only, which contradicts the rules.
  [Easy] — `on_activate_item()` must accept the commanding player's ID and look in that player's items, not `active_id`.

**"↷ abilities can only be activated if the object is charged (upright)."**
- ✅ `legality.py` checks `not item.tapped` before emitting an `ActivateItem` command for ↷ items.

**"$ abilities can be activated even if the object is deactivated."**
- ✅ Modelled correctly: the legality check for $ items does not require `not item.tapped`; it only checks that the cost (cents) can be paid.

**"Activated abilities on rooms can only be activated by the active player."**
- ❌ Rooms not implemented.

---

## Abilities — Static Abilities

**"Static abilities are always true. They don't use the stack."**
- ⚠️ Static abilities are not a formal category in the engine. They are modelled as fields directly on `PlayerState` or `MonsterInPlay` that are checked at the point of need:
  - `ItemInPlay.eternal` — prevents death-penalty destruction and discard routing. ✅ Correctly implemented, doesn't use stack.
  - `PlayerState.damage_cap` — caps damage per hit (from Dead Cat). ✅ Checked inline in damage effects.
  - `MonsterInPlay.evade_bonus / attack_bonus` — temporary stat modifiers. These are better described as continuous effects (reset at end of turn) than static abilities. ⚠️
  - `is_guppy` flag on `TreasureDef` — ✅ flag exists; ❌ the static ability it enables (counts toward Guppy soul condition) is not checked anywhere.
- ❌ No general static-ability infrastructure. A card with a novel static ability (e.g. "You have +1 ATK") requires a new field on `PlayerState` or `MonsterInPlay` and manual checks at every relevant site. [Hard] — a proper static-ability layer would compute derived stats on demand from all in-play static abilities rather than mutating model fields directly.

---

## Abilities — Triggered Abilities

**"Triggered abilities are put onto the stack the next time a player would receive priority."**
- ❌ **This is the largest architectural gap in the engine.** All triggered abilities in the current codebase are implemented as direct Python callbacks that execute immediately and synchronously when the triggering condition is met — they are never pushed onto the stack. Specifically:
  - `on_enters_play` on `TreasureDef`: called directly by `fire_on_enters_play()`.
  - `on_start_of_turn` on `TreasureDef`: called directly by `fire_on_start_of_turn()`.
  - `on_death`, `on_miss`, `on_would_take_combat_damage`, `on_would_die` on `MonsterInPlay`: called directly inline in `combat.py`.
  - Monster event card effects: pushed to the stack via `EventCardEffect` — ✅ this is the only triggered ability correctly using the stack.
  
  Per the rules, all of these (except event cards and the start-of-game ability) should be pushed to the stack at the next priority window, allowing players to respond. The current implementation means no player can ever respond to a triggered ability from an item or monster trigger.
  
  [Complex] — A trigger queue is needed. When a triggering condition is met, the callback should enqueue a `PendingTrigger` rather than executing immediately. At the next priority window, all pending triggers are pushed to the stack (game-controlled ones first, in active-player-chosen order; then player-controlled ones in turn order). This is a foundational change that touches every triggered ability site in the engine.

**"If multiple triggered abilities trigger at once: game-controlled first (in active-player-chosen order), then player-controlled (in turn order starting from active player)."**
- ❌ No simultaneous-trigger ordering system. Triggers currently fire in the order the code encounters them, which is deterministic but not rules-correct (and not player-controlled). [Complex] — depends on the trigger queue above; the queue must be sorted by controller type and turn order before pushing to the stack.

**"Circled-number triggers fire whenever any roll resolves as that number, regardless of context."**
- ❌ Dice rolls are not first-class stack items; there is no roll-resolution event that circled-number triggers can listen to. [Hard] — depends on Sprint 14 dice-on-stack work; once rolls are stack items with a `resolved_value`, circled-number triggers can be checked after each roll resolves.

---

## Abilities — Loot Abilities

**"Any ability written on a loot card is a loot ability. Loot abilities are performed when the loot resolves."**
- ✅ Every loot card's effect is built by `make_loot_effect()` in `cards/loot.py` and wrapped in `PlayLootEffect`. The effect is only applied when `PlayLootEffect.apply()` runs (i.e., when the stack item resolves), not when the loot is played. This is correct.
- ⚠️ `LootRollEffect` rolls a d6 **inside its own `apply()`** method and immediately dispatches to a branch effect. The roll is not put onto the stack as a separate item — players cannot respond between the roll result becoming known and the outcome applying. This violates the rules for roll abilities on loot cards. [Hard] — depends on Sprint 14; the d6 result must be a stack item, and the branch selection must be a triggered ability that fires after the roll resolves.

---

## Abilities — Keyworded Abilities

**Eternal**
- ✅ Fully implemented as `ItemInPlay.eternal = True`. Eternal objects are skipped by death-penalty item destruction and by `resolve_monster_death` discard routing. The `Destroy/Kill` logic in `combat.py` respects the eternal flag. Functions correctly in play; correctly absent outside play (characters that are deactivated/killed still go through death steps because the Eternal constraint is on items, not characters).

**Trinket**
- ❌ Not implemented. No `is_trinket` flag, no loot-to-item resolution path. [Medium] — see Card Types section.

**Ambush**
- ❌ Not implemented. No `is_ambush` flag, no "place in monster slot and force additional attack" logic. [Hard] — requires covered-in-slot support (see Game Zones section) plus a mechanism to grant an additional forced attack against the newly placed monster.

**Guppy**
- ⚠️ `TreasureDef.is_guppy: bool` flag exists and is set on the correct cards. However the flag is never read anywhere in the engine — there is no check that counts Guppy items a player controls, no soul-award when the threshold (2) is reached, and no guppy-count used by any ability. [Easy] — add a `count_guppy_items(player) -> int` helper; check it after any item enters or leaves play; award the Guppy soul if count reaches 2 (when playing with bonus souls).

**Curse**
- ❌ Not implemented. No `is_curse` flag on monster cards, no per-player curse list, no assignment step, no discard-on-death hook. [Medium] — see Card Types section.

**Indomitable**
- ❌ Not implemented. No `is_indomitable` flag. The expand-monster-slots mechanic (which Indomitable requires) is not implemented. "This can't be covered" is also not enforceable until covered-in-slot exists. [Medium] — requires slot expansion (add a slot to `SlotsZone`, fill it) and a pre-placement check.

**Roll-**
- ⚠️ The concept exists via `LootRollEffect` (branch-on-roll-result), but it does not match the rules definition. Per the rules, a Roll- ability: (1) creates a dice roll on the stack, (2) after the roll resolves, puts a triggered ability on the stack that reads the result. Currently both steps happen atomically inside a single `apply()` call with no stack involvement and no priority windows between them. [Hard] — Sprint 14 work; dice must be first-class stack items.

**Team Up**
- ❌ Not implemented. No `has_team_up` flag, no "other players make attack rolls after each active-player roll" logic in the combat loop. [Hard] — requires the combat loop to query whether each monster has Team Up and, if so, iterate through non-active players and generate attack rolls for each of them after every active-player roll.

**Familiar**
- ❌ Not implemented. No `is_familiar` flag on items; items cannot be selected as attack targets in `legality.py`. [Medium] — add `is_familiar` to `TreasureDef`; add familiar items to legal attack targets in `legality.py`; extend combat to handle item-as-defender (using its stat block from `TreasureDef`).

---

## Effects

**"`Effect` protocol: `validate(ctx) -> bool` and `apply(ctx) -> None`."**
- ✅ Defined in `model/effects.py`. All concrete effect classes implement this protocol. `validate()` is checked at resolution time before `apply()` is called; returning `False` fizzles the effect.

**Concrete effect inventory in `rulesets/common/effects.py`:**

| Effect class | What it does | Rules-complete? |
|---|---|---|
| `DrawLoot1Effect` | Draw 1 loot into target player's hand | ✅ |
| `GainCentsEffect` | Player gains N cents | ✅ |
| `DealDamageEffect` | Damage a player (respects damage_cap + prevent_damage) | ✅ |
| `DealDamageToMonsterEffect` | Damage a monster in a slot (validate checks slot occupied) | ✅ |
| `PreventDamageEffect` | Add prevent_damage shield to a player | ✅ |
| `PreventDamageToMonsterEffect` | Add prevent_damage shield to a monster | ✅ |
| `AoDamageEffect` | Damage all players and all monsters | ✅ |
| `CombatMissDamageEffect` | Pending miss damage; fizzles if combat ends | ✅ |
| `AllPlayersGainCentsEffect` | Each player gains N cents in turn order | ✅ |
| `AllPlayersTakeDamageEffect` | Each player takes N damage in turn order | ✅ |
| `AllPlayersDrawLootEffect` | Each player draws N loot in turn order | ✅ |
| `ResetAttackEffect` | Grant active player one additional attack (reset attack_used) | ✅ |
| `GrantExtraLootPlayEffect` | Grant player one additional loot play this turn | ✅ |
| `CancelStackItemEffect` | Remove a StackItem from the stack without resolving | ⚠️ loot discard bug (see Stack zone) |
| `LootRollEffect` | Roll d6 inline and apply a branch effect | ⚠️ roll not on stack |
| `PlayLootEffect` | Wrapper: resolve inner effect then discard loot card | ⚠️ fizzle leaves card in limbo |
| `TreasureActivateEffect` | Wrapper: resolve inner effect; destroy if one-use | ✅ |
| `EventCardEffect` | Wrapper: resolve inner effect; clear slot and discard event | ✅ |

**Missing effect classes needed for planned features:**
- `GainTreasureEffect` — gain N cards from treasure deck top [Easy]
- `RemoveFromGameEffect` — move a card to outside-the-game zone [Easy]
- `HealEffect` — heal a player or monster by N HP [Easy]
- `RechargeItemEffect` — recharge a specific item (Battery cards) [Easy]
- `DestroyItemEffect` — destroy a specific item [Easy]
- `StealItemEffect` — give an item from one player to another [Medium]
- `DiscardLootFromHandEffect` — player-choice discard (not just first card) [Easy]
- `LoseXCentsEffect` — player loses N cents to pool [Easy]

---

## Effects — Continuous Effects

**"Continuous effects change characteristics, either indefinitely or until an endpoint."**
- ❌ No continuous effect layer exists. The engine has no `ContinuousEffect` class, no list of active continuous effects, and no stat-derivation pass that applies them. Instead, all stat modifications are immediate mutations to model fields (`player.damage_cap`, `monster.evade_bonus`, `monster.attack_bonus`, `player.prevent_damage`).

**"Effects created by triggered/activated abilities last until the indicated endpoint."**
- ⚠️ End-of-turn cleanup in `turn.py` resets some temporary fields: `monster.prevent_damage`, `monster.evade_bonus`, `monster.attack_bonus`, `player.prevent_damage` are cleared. This is a hard-coded cleanup sweep rather than endpoint tracking on individual effects.
- ❌ "Indefinite" continuous effects (no endpoint specified) are modelled as permanent field mutations with no removal path unless the source card is destroyed (no tracking of which mutation came from which card). If a passive item is stolen or destroyed, its static modifications to `PlayerState` fields are not undone.
- ❌ Effects like "Items you control gain Eternal till end of turn" cannot be expressed. There is no way to temporarily set a flag on a set of objects and automatically clear it at a specified endpoint.

  [Complex] — a proper continuous effect layer would: (1) maintain a list of `ContinuousEffect` objects with a source, an affected target, a modified characteristic, and an optional endpoint; (2) replace direct field reads of derived stats with a `query_stat(target, stat)` function that applies all applicable continuous effects; (3) remove expired effects at each endpoint.

**"Static abilities create a continuous effect that lasts while the card is in its appropriate zone."**
- ❌ Not modelled. The practical consequence is the same as above: if an item with a static ability (e.g., "+1 ATK while in play") is destroyed, the modifier it applied is not removed from `PlayerState.attack`.
  [Complex] — same fix as above; the continuous effect layer must know which effects are sourced from static abilities and remove them when the source leaves play.

---

## Effects — Replacement Effects

**"Replacement effects modify how things work. They most commonly use the word 'instead'. They don't use the stack."**
- ❌ No replacement effect system exists anywhere in the engine. There is no `ReplacementEffect` class, no event-interception mechanism, and no "would happen / replace with" framework.

**"Prevent damage" and "prevent death" are replacement effects.**
- ⚠️ Damage prevention is implemented as a `prevent_damage` integer shield on `PlayerState` and `MonsterInPlay` that is consumed before HP is reduced. This produces the correct numerical outcome but is architecturally a pre-damage modifier field, not a replacement effect. It cannot be conditionally applied ("prevent the next instance of damage dealt by a monster"), only consumed unconditionally in FIFO order.
- ❌ Death prevention (preventing death from going onto or resolving off the stack) is not modelled as a replacement effect. The `on_would_die` monster callback is the only death-prevention mechanism, and it is a direct synchronous check rather than a stack-level replacement.

**"This enters play deactivated / as [condition]."**
- ❌ No replacement-on-entry system. `on_enters_play` callbacks can apply post-entry mutations but cannot replace the entry event itself. A card with "this enters play deactivated" would need a hardcoded `item.tap()` call in its `on_enters_play` callback — functional but not architecturally correct.

**"If two replacement effects replace the same event, the affected player chooses the order."**
- ❌ Entirely absent. Player-choice ordering of simultaneous replacement effects requires both the replacement effect layer and a player-prompt mechanism.

  [Complex] — a replacement effect system is one of the harder engine additions. It requires hooking into every point where a game event "would happen" (damage, gaining resources, entering play, dying, etc.), collecting all applicable replacement effects, potentially prompting the player to choose an order, and executing the modified event. Every existing damage/gain/entry site in `effects.py` and `combat.py` would need to be refactored to go through this hook.

---

## Specific Mechanics

**Activate**
- ✅ ↷ abilities: `on_activate_item()` taps the item and pushes the effect. ✅ Character ↷: `on_activate_character_ability()` taps the character and pushes `GrantExtraLootPlayEffect`.
- ❌ Non-active player item activation bug — see Activated Abilities section.

**Additional Names**
- ❌ No `additional_names: list[str]` field on any card def. No ability that grants additional names exists in the current card set, but the model cannot express it. [Easy] — add `additional_names: list[str] = []` to all card defs; extend name-matching logic in any ability that checks card names.

**And vs Then (effect composition)**
- ❌ No structured "and vs then" in effect composition. Python effect closures do not distinguish between dependent chaining ("and") and independent chaining ("then"). A two-part effect is always expressed as a single `apply()` method that executes both parts unconditionally — equivalent to "then". To model "Discard a loot card **and** loot 2" (where the second part depends on the first succeeding), the effect's `apply()` would need to check whether the first action succeeded before proceeding. No current effects need this distinction, but it is a latent correctness gap. [Medium] — introduce a `ConditionalEffect(condition_effect, consequent_effect)` that only applies the consequent if the condition effect applied successfully.

**Attackable Items and Rooms**
- ❌ Not implemented. Items and rooms have no stat blocks, no `Familiar` keyword path, and are not valid attack targets in `legality.py`. [Hard] — see Familiar keyword and Anatomy of a Card.

**Attacking Other Players**
- ❌ Not implemented. `legality.py` only generates `AttackMonster` commands targeting monsters. No `AttackPlayer` command type exists. [Hard] — requires a new command, a player evasion source (from the enabling ability), and extending the combat loop to handle a player as the defender.

**Cancel**
- ✅ `CancelStackItemEffect` removes a target `StackItem` by `stack_id`. Used by Butter Bean.
- ✅ "If death is canceled, heal to at least 1 HP": the death-cancellation path in `combat.py` / `resolve_player_death()` includes a heal-to-1 step.
- ⚠️ The loot-card-to-discard issue when canceling a `PlayLootEffect` wrapper — see Stack zone section.

**Copying (skipped here)**
- See Abilities section above. No `CopyEffect`, no item-copies-item, no loot-copies-loot, no ability-copies-ability. [Complex] — copying items requires cloning `copiable qualities` (abilities, name, stat block, reward box, soul icon) without carrying over instance-specific state (counters, tap state, damage); copying loot requires creating a new `StackItem` with the same effect but fresh targets; copying an ability requires re-pushing the effect to the stack without paying costs again. Each sub-case is Medium on its own; all three together are Complex.

---

## Counters

**"Generic counters vs named counters. Named counters count as counters for all purposes."**
- ⚠️ `ItemInPlay.counters: Dict[str, int]` stores named counters only. There is no separate generic counter slot — a generic counter would be stored under an arbitrary key (e.g. `"counter"`). The rules say named and generic counters are interchangeable for count-checking purposes, but this is not enforced; each ability would need to manually sum all counter types to get a total. No current card needs this, but it is a latent gap. [Easy] — document a convention (e.g. generic counters stored under key `"generic"`); add a helper `total_counters(item) -> int` that sums all keys.

**"Counters can serve as the activation cost for $ abilities."**
- ⚠️ The cost-checking infrastructure for $ abilities is in `legality.py` and is cent-based. A counter-spend cost would require a new cost type. `ItemInPlay.counters` exists and can be read in a legality check, but there is no `RemoveCounterCost` in the cost model. [Easy] — add a cost-check path for `counters[key] >= n` in legality and a `counters[key] -= n` step in activation.

**"Counters are tied to the object. Move with it if given or stolen. Not copied."**
- ✅ `ItemInPlay.counters` travels with the `ItemInPlay` object wherever it goes (give/steal not yet implemented, but the data would move correctly since the object itself moves).
- ❌ Not copied: copying not implemented; no copy path exists to accidentally carry counters.

**"Counters removed when object leaves play."**
- ⚠️ When an item is destroyed (removed from `player.items` and added to discard as a bare `CardRef`), the `ItemInPlay` wrapper (and its `counters` dict) is simply discarded — counters vanish implicitly. This is correct in outcome, but no explicit "clear counters on leave-play" step fires, so any triggered ability listening for counter removal would not be invoked. [Easy] — add a `clear_counters()` call in the leave-play path if triggered counter-removal abilities are ever added.

**"Counters put on a player are tied to the player, not their character card."**
- ❌ `PlayerState` has no `counters` field. Players cannot hold counters at all. Any ability that places a counter on a player (not on an item) has no model to write to. [Easy] — add `counters: Dict[str, int]` to `PlayerState` following the same pattern as `ItemInPlay`.

**Special Counters — HP Counters, ATK Counters, Eternal Counters**
- ❌ None of the three special counter types are implemented. No card in the current set uses them, but they are part of the core rules.
  - HP counters: would require that adding/removing them triggers a `max_hp` recalculation on the target. [Medium] — a `recalculate_hp(target)` pass that sums base HP + HP counter bonuses.
  - ATK counters: same pattern; `recalculate_attack(target)`. [Medium]
  - Eternal counters: adding one should set `eternal = True` (or increment an `eternal_counter_count`); removing the last one should unset it. [Easy] — but depends on having player-level counters if placed on a player.

---

## Damage

**"Damage is put on the stack targeting an object. When it resolves, it is marked on the object."**
- ❌ **Core architectural gap.** Damage is never a first-class stack item in the current engine. Every damage-dealing effect in `effects.py` (`DealDamageEffect`, `AllPlayersTakeDamageEffect`, `CombatMissDamageEffect`, etc.) applies HP reduction directly inside `apply()` with no intermediate stack representation. The sole exception is `CombatMissDamageEffect`, which is itself a stack item — but it applies the damage directly when it resolves, without creating a further "damage" stack item. This means players can never respond between "damage is declared" and "damage is marked". [Hard] — a proper damage-on-stack system would represent each damage instance as a `DamageStackItem(target, amount, source)`, allowing Soul Hearts and other prevention tools to target it before it resolves.

**"Objects cannot go below 0 HP. An object at 0 HP can still be targeted by damage but it won't be marked."**
- ✅ `max(0, player.hp - amount)` in all damage effects; `max(0, monster.current_hp - ...)` in `MonsterInPlay.take_damage()`. HP floors at 0 correctly.
- ⚠️ "Damage not marked if object is at 0 HP": `DealDamageEffect.apply()` subtracts from `player.hp` which is already 0, resulting in `max(0, 0 - n) = 0` — correct numerical outcome, but no explicit guard skips the call when HP is already 0.

**"Death put on the stack the next time a player would receive priority."**
- ⚠️ Player and monster deaths are queued and checked at priority-pass points in the game loop (via `check_combat_attacker_death`, `check_combat_defender_death`, `check_all_monster_deaths_out_of_combat`). This is architecturally correct in concept but is triggered by explicit check calls at specific sites, not by a universal HP-reaches-0 listener. A damage path that isn't followed by one of these check calls would leave a dead-but-not-dying object in play. [Medium] — centralise the death-check into a single post-mutation hook called after every HP modification.

**"Damage source is tracked. Source is only considered to have dealt damage when it resolves."**
- ❌ No `damage_source` field on any damage effect or stack item. The concept of "who dealt this damage" (relevant for abilities like "each time this deals damage, do X") cannot be queried. [Easy] — add an optional `source: Optional[CardRef]` to `DealDamageEffect` and `CombatMissDamageEffect`; emit it in the damage event.

**"You can't deal or take 0 damage."**
- ❌ No guard. `DealDamageEffect(amount=0)` is a valid object; calling code could push it to the stack and it would resolve as a no-op, but it should not be pushed at all. [Trivial] — assert `amount > 0` in each damage effect's `__post_init__`, or add a pre-push check in the sites that create damage effects.

**"If max HP is reduced, remove equivalent marked damage (not considered healing)."**
- ❌ Not implemented. `PlayerState` has both `max_hp` and `hp`. Reducing `max_hp` (e.g. via Dead Cat consuming a charge) does not trigger any adjustment to `hp`. A player at 1/2 HP who loses a max-HP point should remain at 1/1, but the engine would leave them at 1/1 anyway only because HP is not stored as a "damage marked" value — it is stored as current HP directly. However, if `max_hp` is reduced below current `hp`, the player would have HP above their max, which is incorrect. [Easy] — after any `max_hp` reduction, clamp `player.hp = min(player.hp, player.max_hp)`.

**"If an object stops having an HP stat, any marked damage is removed."**
- ❌ No mechanism. Items do not currently have HP stats so this is moot in practice, but there is no general hook for "HP stat removed → clear damage". [Easy once attackable items exist] — clear the HP fields when the stat block is removed (e.g. if an item loses its Familiar keyword mid-combat).

---

## Deactivate

**"To deactivate an object, change it to a deactivated state (turned sideways 90°)."**
- ✅ `ItemInPlay.tap()` sets `is_tapped = True`. Character cards use the same `ItemInPlay` wrapper and the same `tap()` method. `legality.py` gates ↷ abilities on `not item.is_tapped`.

---

## Destroy and Kill

**"Set HP to 0 if the object has an HP stat. If it doesn't die or has no HP stat, move to discard. Characters and eternal objects are not moved to discard."**
- ⚠️ The death-penalty item destruction path (`resolve_player_death()`) correctly removes the item from `player.items` and adds its `CardRef` to `treasure_discard`, skipping eternal items. This is correct for that specific case.
- ❌ No general-purpose `DestroyItemEffect` usable by arbitrary card abilities. Any card that says "destroy target item" would need its own bespoke effect implementation. [Easy] — add `DestroyItemEffect(target_instance_id, player_id)` that finds and removes the item, routes its `CardRef` to `treasure_discard`, and checks for the eternal flag.
- ❌ Destroying souls: `PlayerState.souls` is a `List[CardRef]`. No soul-destroy effect exists; souls cannot currently be targeted for destruction by abilities. [Easy] — add a `DestroySoulEffect`.
- ❌ Destroying monsters outside of combat (e.g. via a bomb ability): `DealDamageToMonsterEffect` reduces HP but does not trigger `resolve_monster_death()`. A monster killed by an ability outside of a `RollCombat` command would be left at 0 HP without dying. The `check_all_monster_deaths_out_of_combat()` helper exists and is called at certain points, but whether it covers all ability-triggered kills depends on call-site discipline. [Medium] — centralise into a post-ability-resolve hook.

**"Die is a related action: the game destroys/kills a specified object."**
- ⚠️ Monster death via the combat path is well-handled. A general "die" command for arbitrary in-play objects (items, souls, players outside of normal death flow) is not a first-class action; each case needs bespoke code.

---

## Discard (action)

**"To discard, move the specified number of loot cards from your hand into the loot discard."**
- ⚠️ The death-penalty discard calls `player.hand.pop(0)` — it always discards the **first** card in the hand list, not a card of the player's choice. Per the rules, the player chooses which loot card to discard. [Easy] — for the death-penalty discard, prompt the player to choose a card index; in a non-interactive context (bots) default to index 0, but the interface should expose the choice.
- ❌ No general `DiscardLootFromHandEffect` that lets the active player select which card to discard (needed for abilities like "discard a loot card: gain 3¢"). [Easy] — add `DiscardChosenLootEffect(player_id, choice_index)` that removes `hand[choice_index]` and adds it to loot discard; legality generates one command per hand card.

---

## Doubling ¢

**"If an ability instructs you to double ¢, that player gains x¢ where x is the number they currently have."**
- ❌ No `DoubleCentsEffect`. No current card in the set uses it. [Trivial] — add `DoubleCentsEffect(player_id)` that reads `player.cents` and calls `gain_cents(player.cents)`.

---

## Each

**"Each player does something — in turn order, starting from the controller (or active player if game-controlled)."**
- ✅ `AllPlayersGainCentsEffect`, `AllPlayersTakeDamageEffect`, `AllPlayersDrawLootEffect` all iterate `ctx.turn_order`, which starts from the active player. Correct for game-controlled abilities.
- ❌ For player-controlled "each" abilities, the iteration should start from the controlling player, not always the active player. No current "each" effect tracks a `controller_id` to start from. [Easy] — add an optional `start_player_id` parameter to each "all players" effect; default to `ctx.active_player_id`.

**"Each player dies / takes damage — deaths added to stack in REVERSE turn order so they resolve in forward turn order."**
- ❌ Not modelled. `AllPlayersTakeDamageEffect` applies damage directly in `apply()` rather than pushing individual damage instances to the stack. The reverse-order stacking rule is therefore irrelevant currently, but it will matter once damage and death are first-class stack items. [Hard] — depends on damage-on-stack (see Damage section).

**"Each monster takes damage — the controlling player (or active player) chooses the order."**
- ❌ `AoDamageEffect` iterates `monster_slots.filled_indices()` which returns slot indices in array order. No player choice is offered. [Easy] — once a player-choice UI mechanism exists, request ordering before the loop; for bots, array order is a valid default.

**"Each living player" filter.**
- ❌ The "each" effects iterate `ctx.turn_order` unconditionally. Dead players (HP = 0) are included in the iteration. Per the rules, "each living player" should skip players with 0 HP. `PlayerState.is_alive()` exists but is not called by any "each" effect. [Easy] — add an `alive_only: bool = False` parameter to each "all players" effect and filter with `player.is_alive()` when set.

**"Each item in play — shop items rerolled last."**
- ❌ No effect currently targets all items in play. When such an effect is added, it would need to iterate player-controlled items first (in turn order) and shop items last. [Easy] — when implementing such an effect, follow this ordering explicitly.

---

## Expand Slots

**"Expanding increases the number of slots of the specified type."**
- ❌ `SlotsZone` has a fixed `size: int` set at construction time with `slots = [None] * size`. There is no `expand()` method; the list and the size counter cannot be grown after creation. This blocks: the Indomitable keyword, any card that adds a shop slot, and any card that adds a monster slot.
  [Medium] — add `SlotsZone.expand(n: int = 1)` that appends `n` `None` entries to `self.slots` and increments `self.size`; update `__len__` to use `len(self.slots)` dynamically. All code that iterates slots by index already works correctly; only `size`-based boundary checks need updating.

---

## Fizzle

**"Fizzling is when the game cancels a loot, ability, or dice roll because the game state is invalid."**
- ✅ `Effect.validate(ctx) -> bool` is checked at resolution time in the game loop. Returning `False` causes the `StackItem` to be popped without calling `apply()`, and an `EffectFizzled` event is logged (visible in the CLI renderer).

**"Targets may become invalid (e.g. item recharged, item destroyed) — ability fizzles."**
- ✅ Effect `validate()` methods check current game state, not state at push time. `DealDamageToMonsterEffect.validate()` checks the slot is still occupied; `CombatMissDamageEffect.validate()` checks `combat.is_active`. These correctly fizzle when targets change.
- ⚠️ Not all effects have meaningful `validate()` implementations — several return `True` unconditionally. A `DealDamageEffect` targeting a player will never fizzle even if the player has left the game, because no such condition is checked. [Easy per effect] — add state-validity checks wherever a target could become invalid between push and resolution.

**"Any unresolved attack rolls and combat damage fizzle when an attack is canceled."**
- ✅ `combat.is_active = False` is set when the attack ends. `CombatMissDamageEffect.validate()` returns `self.combat.is_active`, so any pending miss damage on the stack fizzles immediately when the attack is canceled.
- ❌ Attack rolls are not stack items (dice are not on the stack), so there is nothing to fizzle for them specifically. This will need to be implemented as part of Sprint 14.

**"Dice rolls fizzle."**
- ❌ Dice rolls are not first-class stack items; they cannot fizzle as stack items. [Hard] — Sprint 14 prerequisite.

---

## Flip

**"Flip an object means to flip it onto its back face, if it has one. Object is still the same object. Only visible face characteristics apply."**
- ❌ No back-face concept exists anywhere in the engine. No card def has a `back_face` field. No `is_flipped` state on `ItemInPlay` or `MonsterInPlay`. No card in the current set has a back face, but several exist in the full game (e.g. double-sided boss cards).
  [Medium] — add `back_face: Optional[TreasureDef | MonsterDef]` to the relevant def types; add `is_flipped: bool` to `ItemInPlay` / `MonsterInPlay`; gate all stat and ability lookups on which face is currently visible.

**"Flip a dice roll means change the result to 7 minus the current result."**
- ❌ Dice rolls are not stack items; there is no roll-result value to flip. [Easy once Sprint 14 lands] — add a `flip_roll()` helper that sets `roll.value = 7 - roll.value`; usable by any card or ability that says "flip a roll".

---

## Gaining and Giving

**"To gain ¢, move ¢ from the game's pool into your pool."**
- ✅ `GainCentsEffect` increments `player.cents` directly. `player.cents` is not bounded above (no pool depletion check). The game pool is modelled as a separate value but depletion is not enforced.

**"To gain treasure, move cards from the top of the treasure deck into play under your control."**
- ⚠️ The monster reward path (`reward_treasure`) draws from the treasure deck and calls `player.gain_treasure()`. There is no general-purpose `GainTreasureEffect` for arbitrary abilities (e.g. a loot card that says "gain 1 treasure"). [Easy] — add `GainTreasureEffect(player_id, count)`.

**"To gain an object in play (e.g. an item or soul), move it under your control."**
- ⚠️ Souls are appended to `player.souls` on monster death — correct. Moving an already-in-play item from one player to another (give/steal) is not implemented. [Medium] — requires Give/Steal mechanics below.

**"Gaining and giving are mechanically distinct. Stealing and swapping count as giving, not gaining."**
- ❌ No distinction is tracked. There is no event or trigger that fires on "gave" vs "gained"; all item-acquisition paths emit the same events. Abilities that specifically watch for gaining vs giving would have no mechanism to differentiate. [Medium] — add separate `ItemGained` and `ItemGiven` events; trigger checks must distinguish them.

**Give / Steal / Swap — items, loot, and ¢**
- ❌ None of these three actions are implemented. There is no `GiveItemEffect`, `StealItemEffect`, `SwapItemEffect`, `GiveLootEffect`, `GiveCentsEffect`, or their steal/swap variants. No command type, no legality path, no effect class.
  [Medium each] — Give: find object in giver's zone, move to receiver's zone, fire on-give hooks. Steal: same but controller chooses the object. Swap: atomic simultaneous give in both directions. The give/steal/swap distinction for trigger purposes (see above) must be wired at the same time.

---

## Heal

**"An object can be healed a specified amount or to full HP. Cannot heal past max HP. Cannot heal while death is on the stack unless death is also prevented/canceled."**
- ❌ No `HealEffect` exists as a standalone effect class. Healing currently happens only in two places: the end-of-turn full-heal sweep in `on_end_turn()` and implicit HP restoration when death is prevented (`on_would_die` for monsters). Neither is a reusable effect that arbitrary card abilities can invoke.
  [Easy] — add `HealEffect(target_id, amount)` for player healing and `HealMonsterEffect(slot_index, amount)` for monsters; both clamp to `max_hp` and include a `validate()` guard that checks death is not currently on the stack for the target.

**"Heal a specified amount: remove that much damage from the object."**
- ⚠️ `PlayerState` models HP as current `hp` (not as "damage marked separately"), so healing is just `player.hp = min(player.max_hp, player.hp + amount)`. Semantically identical to the rules, just a different internal representation.

**"Cannot heal while death is on the stack."**
- ❌ No guard. Nothing prevents healing a dead player before their death resolves. [Easy] — in `HealEffect.validate()`, check that no `PlayerDeathEffect` (or equivalent) targeting this player is on the stack.

---

## If You Do

**"'If you do' means the first part must have taken effect for the second part to happen."**
- ❌ No `ConditionalEffect` class. Multi-part effects in `apply()` execute their parts unconditionally in sequence, equivalent to "then" semantics rather than "and" (dependent) semantics. For example, a card that says "Destroy this. If you do, gain 25¢" cannot be expressed correctly — the gain would happen even if the item could not be destroyed (e.g. it was eternal).
  [Medium] — add `ConditionalEffect(condition: Effect, consequent: Effect)` that calls `condition.apply()`, checks a success flag, and only calls `consequent.apply()` if the condition succeeded. Requires effects to signal success/failure (currently `validate()` is the only failure path, and `apply()` has no return value).

---

## Levels

**"Objects use level counters (named counters) to determine which abilities they have."**
- ❌ No level system. No `levels` tag on any card def, no `LevelUp`/`LevelDown` effect, and no ability-selection logic that reads the level counter count to determine which abilities are active. No card in the current set uses levels.
  [Hard] — requires: named counters (partially there), a `level_thresholds: list[tuple[int, AbilityDef]]` field on card defs, and a stat/ability query path that finds the highest threshold not exceeding the current level counter count.

---

## Loot (action)

**"To loot, move the specified number of loot cards from the top of the loot deck to your hand."**
- ✅ `DrawLoot1Effect` draws exactly 1 card. `AllPlayersDrawLootEffect` draws N cards for each player. Both call `loot_deck.draw(n)` and extend the player's hand.
- ✅ `DrawLoot1Effect.validate()` returns `False` if the deck is empty (correct — no loot to draw). `AllPlayersDrawLootEffect` clamps to `min(count, len(deck))` per player rather than fizzling, which is probably fine.
- ❌ No general `LootNEffect(player_id, n)` for arbitrary N used by card abilities. [Trivial] — `DrawLoot1Effect` is effectively `LootNEffect(n=1)`; parameterise it.

---

## Lose (¢)

**"To lose ¢, move that many from your pool to the game's pool. If you don't have enough, lose as many as possible."**
- ⚠️ The death penalty does `player.cents = max(0, player.cents - 1)` which is correct. There is no standalone `LoseCentsEffect` for arbitrary ability use.
  [Easy] — add `LoseCentsEffect(player_id, amount)` that does `player.cents = max(0, player.cents - amount)`.

---

## Note

**"When instructed to note something, keep track of it. Notes are tied to the object that caused them. Cleared when that object is destroyed or discarded."**
- ❌ No note system anywhere in the engine. No `noted_values` field on `ItemInPlay`, `PlayerState`, or any other model object. No card in the current set uses notes.
  [Medium] — add `noted_values: dict[str, list[int]]` (keyed by source `InstanceId`) to `GameState` or a dedicated `NoteRegistry`; add `NoteValueEffect`, `ClearNotesEffect`; wire clearing into item-leave-play path.

---

## Pay

**"To pay ¢: move from your pool to specified pool. Can't pay what you don't have."**
- ✅ Cost-check is in `legality.py` (`active.cents >= TREASURE_COST`). Cost deduction is in `on_buy_shop()`. Both correctly enforce "can't pay what you don't have."
- ❌ No general `PayCentsEffect(player_id, amount, destination_pool)` for arbitrary card costs. Each cost-paying site is hardcoded. [Easy] — add a reusable effect.

**"To pay HP: you lose that much HP. Can't pay if not enough HP."**
- ❌ Not implemented. No card in the current set uses it, but it is a real rules mechanic (e.g. "pay 1♥: gain 3¢"). No legality check for HP cost, no `PayHPEffect`. [Easy] — add `PayHPEffect(player_id, amount)` with `validate()` checking `player.hp > amount` (strictly greater, since paying to 0 would kill the player).

---

## Play (loot action)

**"To play means to move a loot card from one zone to the stack. The player who played it controls it."**
- ✅ `on_play_loot()` removes the card from `player.hand`, wraps its `Effect` in `PlayLootEffect`, pushes it to the stack with `controller_id` set. Controller identity is stored on the `StackItem`.

**"By default, plays loot from hand. Abilities can allow playing from another zone."**
- ✅ Default: from hand. ❌ From other zones: no path exists (see Loot Cards section).

---

## Prevent

**"Prevent damage: remove that damage from the stack."**
- ⚠️ Damage is not a stack item (see Damage section), so there is nothing on the stack to remove. The current `prevent_damage` shield on `PlayerState` / `MonsterInPlay` is consumed at HP-deduction time inside `apply()`, not at a stack-removal step. The functional outcome is the same for the current card set, but it cannot intercept damage between its being "declared" and its being "marked" since that window doesn't exist.
  Once damage-on-stack lands (Sprint 14+), `PreventDamageEffect` would need to target the specific `DamageStackItem` and remove it. The current `PreventDamageEffect` class adds a numeric shield — it would need to become an actual stack-removal effect.

**"Prevent death: remove that death from the stack, heal to at least 1 HP."**
- ❌ No player death-prevention effect exists. The `on_would_die` callback on monsters is the only death-interception mechanism, and it operates as a synchronous callback rather than a stack-level removal. Players have no equivalent. A card like "prevent the next death" cannot currently be expressed.
  [Medium] — requires death to be a first-class stack item (a `PlayerDeathStackItem`); a `PreventDeathEffect` would target and remove it, then heal to 1 HP.

---

## Recharge

**"To recharge an object, change it to a charged state (turned upright)."**
- ✅ `ItemInPlay.untap()` sets `is_tapped = False`. Used at start-of-turn (`enter_start_phase()`), end-of-turn for `recharge_on="end_of_turn"` items (`on_end_turn()`), and by the death-penalty deactivation step (see bug below).

**Recharge as a standalone effect (e.g. Battery loot cards: "Recharge an item").**
- ❌ No `RechargeItemEffect`. Battery cards are listed in the deck ratio but their effect is not implemented. [Easy] — add `RechargeItemEffect(player_id, instance_id)` that calls `item.untap()`.

---

## Reroll

**"To reroll a dice roll: roll that dice again. Modifies the existing roll, not a second roll."**
- ❌ Dice rolls are not first-class stack items; there is no roll object to reroll. Dice Shard cards exist in the loot ratio but their effect is absent. [Hard] — Sprint 14 prerequisite.

**"To reroll an item: destroy it; if destroyed, the controlling player gains +1 treasure. If a shop item, the shop gains the treasure instead."**
- ❌ No `RerollItemEffect`. No card in the current set uses this, but it is a rules-defined action. [Easy] — destroy the item (remove from items list, add to treasure discard), then call `GainTreasureEffect(1)` for the player; if the item was a shop item, draw from the treasure deck into the shop slot.

---

## Voting

**"Ability specifies participants. Each votes in turn order (or from ability controller). Votes are final once cast."**
- ❌ No voting mechanism anywhere in the engine. No multi-player simultaneous-choice infrastructure; no `VoteEffect`, no vote-result aggregation. No card in the current set uses voting.
  [Hard] — requires a synchronous multi-step interaction: enumerate voters, collect one choice per voter in turn order (requires a prompt/response loop for each), aggregate results, apply the outcome. This is architecturally similar to multi-target selection and would need the same request/response pattern as a player-choice discard.

---

## Turn Structure — Start Phase

**"Recharge Step: active player recharges objects they control. Game-controlled objects (except shop items) also recharge."**
- ✅ `enter_start_phase()` untaps the active player's character and all their `recharge_on="start_of_turn"` items.
- ⚠️ "Game-controlled objects (except shop items) recharge": no recharge step for monster-slot objects. Monsters have no tapped state, so this is largely N/A. If any future game-controlled object with a tapped state is added, it would need to be recharged here.

**"Start-of-turn triggered abilities trigger, then priority passes."**
- ⚠️ `fire_on_start_of_turn()` calls `TreasureDef.on_start_of_turn` callbacks directly and synchronously — they do not go onto the stack and no priority window exists for other players to respond. [Complex] — depends on the trigger-queue system described in the Triggered Abilities section.

**"Loot Step: active player loots 1. Priority passes, then action phase begins."**
- ✅ `DrawLoot1Effect` is pushed to the stack in `enter_start_phase()`. It resolves when all players pass priority. `on_all_passed_empty_stack()` then advances to ACTION phase. The loot-step priority window is therefore correctly gated — all players can respond before the draw resolves and before ACTION begins.

---

## Turn Structure — Action Phase

**"Active player gets one loot play. May declare one attack, one purchase, or end turn while stack is empty."**
- ✅ `TurnFlags.loot_plays_used` and `loot_plays_allowed` track the quota. `attack_used` and `purchase_used` flags gate attack and purchase. `legality.py` enforces all three against the current stack and phase state.

**"Active player may also activate activated abilities or play a loot card at any time they have priority."**
- ✅ `ActivateCharacterAbility` and `PlayLoot` are legal whenever the priority holder has priority, regardless of stack state. `ActivateItem` is legal at any time during ACTION.
- ❌ **Bug**: `ActivateItem` commands are generated only for the active player's items (see Activated Abilities section). Non-active players cannot legally activate their own items even when they have priority.

**"Priority passes after any action declaration or activation."**
- ✅ Every command handler in the game loop resets priority to the active player after execution, which re-initiates the full priority rotation. Correct.

**"Both attack and purchase may be made in the same turn."**
- ✅ The flags are independent — `attack_used` does not block `purchase_used` and vice versa. Confirmed.

---

## Turn Structure — End Phase

**"End-of-turn triggered abilities trigger, then priority passes."**
- ❌ No end-of-turn triggered ability pass for items. The `recharge_on="end_of_turn"` items are recharged in `on_end_turn()`, but that is a recharge step, not a triggered-ability step. Any item with an "at end of turn, do X" ability would need to be handled as a triggered ability via the trigger-queue system (not yet built).

**"Active player discards to max hand size (10 by default)."**
- ✅ `on_end_turn()` does `del active.hand[10:]` — removes all cards beyond index 9. Correct.
- ⚠️ Player has no choice of which cards to discard when over the limit; the last cards in the list are kept. Per the rules, the player chooses which to discard. [Easy] — prompt the player to select which cards to drop, or for bots use a heuristic.

**"Turn ends. All objects with an HP stat heal to full, including dead players."**
- ✅ `on_end_turn()` iterates all players and monsters: `player.hp = player.max_hp`, `monster.current_hp = monster.base_hp`. Correct.
- ✅ `prevent_damage` cleared for all players and monsters.
- ✅ Monster per-turn trigger state (`evade_bonus`, `attack_bonus`, `prevent_death_used`) reset.

**"Abilities and effects that last till end of turn end."**
- ⚠️ The monster per-turn fields above are cleared. There is no general continuous-effect expiry system; any other "till end of turn" effect would need to be manually tracked (see Continuous Effects section).

**"An effect that ends the turn does not remove anything from the stack."**
- ⚠️ Currently, the only way to reach the end phase is via `EndTurn` command, which `legality.py` gates behind `stack.empty()`. An ability-triggered end-of-turn would bypass this gate — when the active player dies, `resolve_player_death()` force-pops the entire stack (`while not game.stack.empty(): item = game.stack.pop()`). This *removes* items from the stack rather than leaving them, which violates the rule. [Medium] — ability-triggered end-of-turn should transition to END phase while leaving stack contents intact; the stack should drain naturally through the normal priority/resolution loop.

---

## Round

**"A round lasts from the start of a player's turn to the start of their next one."**
- ❌ No explicit round counter or round-boundary event. `turn_number` increments on every player's turn, but no "round number" is tracked. No "start/end of round" hooks exist.
- ❌ Per-player round tracking ("from your last turn to your next") is absent. Abilities that say "once per round" cannot be expressed.
  [Easy] — add `round_number: int` to `GameState`; increment when the starting player's turn begins; emit `RoundStarted` event.

**"Extra turns / skipped turns do not affect round length."**
- ❌ Not enforced (no extra-turn or skip-turn mechanics exist yet). [N/A until those features are built.]

---

## Attacking

**"Declare attack during ACTION phase, stack empty."**
- ✅ `legality.py` gates `AttackMonster` behind `phase == ACTION`, `stack.empty()`, `not attack_used`, `combat is None`. Correct.

**"Priority passes before target is chosen."**
- ✅ `enter_combat()` is called after `AttackMonster` is processed; `AttackMonster` command triggers priority passing in the game loop before `enter_combat()` sets up the `CombatState`. Correct.

**"Can attack a monster in a slot or the top card of the monster deck."**
- ❌ Attacking the top of the monster deck is not implemented. `legality.py` only generates `AttackMonster(slot_index=idx)` commands for occupied slots. [Hard] — requires covered-in-slot support; see Game Zones section.

**"Force-attack effects: certain abilities force the player to attack a specific target."**
- ❌ No force-attack infrastructure. No field on `TurnFlags` or `GameState` stores a forced-attack target. [Medium] — add an optional `forced_attack_slot: Optional[int]` to `TurnFlags`; in `legality.py`, if set, emit only `AttackMonster(forced_attack_slot)`.

**"Triggered abilities that interact with attack declarations."**
- ❌ No pre-declaration or post-declaration triggered ability hooks. Declaring an attack does not fire any triggers (the only thing that happens is priority passing, then `enter_combat()`). [Complex] — depends on trigger-queue system.

**"Once attack has started, repeatedly roll D6. Roll ≥ evasion → hit; roll < evasion → miss."**
- ✅ `resolve_roll()` calls `game.rng.roll_d6()`, compares to `monster.evade + monster.evade_bonus`, applies hit or miss path. Correct.

**"Hit: deal combat damage equal to attacker's attack. Miss: monster deals combat damage equal to its attack."**
- ⚠️ Hit damage is applied directly inside `resolve_roll()` via `monster.take_damage(damage)` — not as a stack item. Players cannot respond before hit damage is marked.
- ✅ Miss damage is pushed to the stack as `CombatMissDamageEffect` — players can respond (Soul Heart, etc.) before it resolves. This asymmetry between hit and miss is a rules deviation; both should be stack items.

**"When attack ends (death or cancel), unresolved attack rolls and combat damage are removed from stack."**
- ✅ `CombatMissDamageEffect.validate()` checks `combat.is_active`; setting `game.combat.is_active = False` causes any pending miss damage to fizzle. Correct for miss damage.
- ❌ Attack rolls are not stack items; nothing to fizzle for them.

**"Non-attacking players can be instructed to make attack rolls by an ability."**
- ❌ Not implemented. No command or effect for "player X makes an attack roll outside of their attack declaration." [Medium] — add a `ForceAttackRollEffect(player_id, defender_slot)` that uses the specified player's attack stat but does not end the attack if they die.

**"Simultaneous lethal damage: monster dies first, then player."**
- ⚠️ In the current model, a hit that kills the monster resolves immediately in `resolve_roll()` and ends combat. Miss damage (which could kill the player) is on the stack and resolves afterward. The ordering is implicitly correct for this specific case. However, it is not explicitly modelled as a rule — if both could die from the same stack resolution simultaneously, the ordering is not enforced.

---

## Purchasing

**"Declare purchase during ACTION phase, stack empty."**
- ✅ `legality.py` gates `BuyShop` behind `phase == ACTION`, `stack.empty()`, `not purchase_used`. Correct.

**"Priority passes before target is chosen."**
- ✅ `BuyShop` triggers priority passing before `on_buy_shop()` runs. Correct.

**"Can purchase a shop item or the top of the treasure deck."**
- ❌ Purchasing the top of the treasure deck is not implemented. `legality.py` only generates `BuyShop(slot_index=idx)` for occupied shop slots. [Medium] — add `BuyDeck` command; implement blind draw from treasure deck top, deduct 10¢, call `fire_on_enters_play`.

**"Cost determined after target chosen. If can't pay, fail. Default cost is 10¢."**
- ✅ Cost check `active.cents >= TREASURE_COST` is in `legality.py` before emitting `BuyShop`. `TREASURE_COST = 10`. If the player doesn't have 10¢, no `BuyShop` command is generated.
- ❌ Cost-modifying abilities (e.g. "items cost 5¢ less this turn") are not modelled. [Medium] — replace `TREASURE_COST` with a `query_shop_cost(game, item) -> int` function that applies all active cost-modifying continuous effects.

**"Triggered abilities that interact with purchase declarations."**
- ❌ No purchase-declaration triggered ability hooks, analogous to the missing attack-declaration ones. [Complex] — same trigger-queue dependency.

---

## Refilling Slots

**"Each slot must always have at least one card in it. Refill with top card of its deck whenever a slot is empty."**
- ✅ `_do_resolve_monster_death()` immediately draws from `monster_deck` and calls `place_monster_card()` on the cleared slot.
- ✅ `on_buy_shop()` refills the purchased shop slot from `treasure_deck`.
- ⚠️ "Refill happens the next time any player would gain priority": the refill in `_do_resolve_monster_death()` is synchronous and immediate, not deferred to the next priority window. For the current card set this doesn't matter, but technically another triggered ability firing before the refill (step 4 in the rules death sequence) could observe an empty slot. [Medium] — defer refill to a post-death-resolution step rather than doing it inside `_do_resolve_monster_death()`.

**"When refilling a monster slot, keep resolving events until a monster ends up in the slot."**
- ⚠️ `place_monster_card()` handles events by wrapping them in `EventCardEffect` and pushing to the stack. When the `EventCardEffect` resolves, it clears the slot and discards the event — but it does NOT then draw another card to refill. The slot would be empty after the event resolves, and no automatic re-refill is triggered. A chain of consecutive events would leave the slot empty after the first one resolves.
  [Medium] — after `EventCardEffect.apply()` clears the slot, it should call refill logic (or signal the game loop to refill) rather than leaving the slot empty.

**"Active player refills slots even if dead."**
- ✅ `_do_resolve_monster_death()` always uses `game.state.active_player_id` as the reward recipient and does not check if they are alive. Slot is refilled regardless.

---

## Death — General

**"If HP reaches 0 (or HP stat is not a number), death is put on the stack at the next priority window."**
- ⚠️ Death is not a first-class stack item. Instead, death-check functions (`check_combat_defender_death`, `check_combat_attacker_death`, `check_all_monster_deaths_out_of_combat`) are called at specific points in the code rather than at a universal "next priority window" listener. A damage path that bypasses these checks would leave a 0-HP object in play without dying.
  [Hard] — proper implementation requires a universal HP-reaches-0 observer that queues deaths as stack items at the next priority window.

**"Eternal objects can't die."**
- ✅ `ItemInPlay.eternal = True` causes items to be skipped by the death-penalty destroy step. Eternal objects are also excluded from targeted destroy effects.
- ⚠️ "Game will not attempt to put death on the stack for Eternal objects at 0 HP": not explicitly checked, since items don't have HP stats in the current model anyway. If Eternal items ever gain HP stats (via Familiar keyword), this guard would need to be added. [Easy when relevant] — check `eternal` flag in the HP-reaches-0 observer before queuing death.

---

## Monster Death

**Rules sequence: (1) move to temp zone, (2) pre-reward death triggers, (3) grant rewards, (4) post-reward death triggers, (5) soul gained or discard, (6) refill slot.**
- ❌ **Order is wrong.** `_do_resolve_monster_death()` executes: discard card → clear slot → **refill slot** (step 6) → grant rewards (step 3). Refill happens before rewards, which contradicts the rules. An event from the refill could therefore resolve before the attacker has received their coins/loot/soul from the kill.
  [Easy] — reorder: grant rewards and soul first, then refill.

**"Pre-reward and post-reward triggered abilities trigger here."**
- ⚠️ `on_death` callback fires inside `_do_resolve_monster_death()` synchronously (it is actually called at the end of the function, after rewards and refill). It is not pushed onto the stack and no priority window is given. [Complex] — depends on the trigger-queue system.

**"Grant rewards: coins, loot, treasure, soul."**
- ✅ Coins, loot cards, and treasure cards are awarded in `_do_resolve_monster_death()`. Soul is appended to `player.souls` if `has_soul`. Win condition is checked after soul grant.

**"If monster can't be put in discard, put back in its slot."**
- ❌ No "can't be discarded" flag on monsters. No handling for this edge case. [Easy] — add `cannot_discard: bool` to `MonsterDef`; check it in `_do_resolve_monster_death()` before routing to discard.

---

## Player Death

**"Active player dies: stop declarations, cancel attacks, move to death steps."**
- ✅ `resolve_player_death()` clears `game.combat = None` (cancels the active attack). The turn continues; the player must issue `EndTurn` explicitly after paying the penalty.

**Death Penalty: (1) destroy non-eternal item, (2) discard loot, (3) lose 1¢, (4) deactivate ↷ items.**
- ⚠️ **Step 1 — Item choice**: the code always destroys `destroyable[0]` (the first non-eternal item in the list). Per the rules, the player *chooses* which non-eternal item to destroy. [Easy] — expose the choice as a player prompt; emit an `ChooseDeathPenaltyItem` command type or similar.
- ⚠️ **Step 2 — Loot choice**: the code always discards `hand.pop(0)` (the first card in the hand list). Per the rules, the player chooses. [Easy] — same fix.
- ✅ **Step 3 — Lose 1¢**: `player.cents = max(0, player.cents - 1)`. Correct; floored at 0.
- ❌ **Step 4 — Deactivate ↷ items — confirmed bug**: `resolve_player_death()` contains:
  ```python
  if player.character is not None and player.character.is_tapped:
      player.character.untap()
  ```
  This **untaps** (recharges) the character if it is already tapped. The rules require **deactivating** (tapping sideways) all ↷ items. The code should call `item.tap()` on all items with a ↷ ability, not `untap()`. Additionally it only processes the character and ignores all other ↷ items in `player.items`.
  [Easy] — replace with: `for item in [player.character] + player.items: if item has ↷ ability: item.tap()`.

**"Non-active player stops after the penalty step."**
- ✅ `resolve_player_death()` is currently only invoked from the combat path where the attacker (always the active player) dies. Non-active player death is not yet triggered by any code path, so this distinction is not tested in practice.

**"Cleanup Step: stack must fully resolve before END phase."**
- ❌ `resolve_player_death()` force-pops the entire stack with `while not game.stack.empty(): item = game.stack.pop()`. This discards stack items without resolving them, rather than allowing them to resolve naturally before the END phase begins. [Medium] — the cleanup step should let the normal priority/resolution loop drain the stack; the transition to END phase should be gated on the stack being empty and all players having passed.

**"A player can only die once per turn."**
- ⚠️ `TurnFlags.died_this_turn` is set to `True` in `resolve_player_death()`. However, `legality.py` does not check `died_this_turn` before generating `RollCombat` commands, and the death-check functions do not check it before queuing another death. A second death in the same turn could theoretically be processed. [Easy] — check `died_this_turn` in death-check paths and skip if already True for this turn.

**"Dead players cannot make attack rolls."**
- ✅ After `resolve_player_death()`, `game.combat` is set to `None`, so no further `RollCombat` commands are legal (combat is over). In the specific case of non-attacking-player attack rolls (not yet implemented), a dead-player guard would be needed.
