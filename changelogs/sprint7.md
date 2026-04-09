# Sprint 7 — Correct Player Death Penalty

---

## 1) Sprint / commit context

**Sprint:** Sprint 7  
**What's done vs partial:**

Done:
- R7.1 — `eternal: bool = False` on `ItemInPlay`; character items in `build_demo_game` created with `eternal=True`; flag is orthogonal to `is_tapped`
- R7.2 — Four-step death penalty applied in `resolve_player_death`: (1) destroy first non-eternal item → `treasure_discard`; (2) discard first loot card → `loot_discard`; (3) lose 1¢ (floor 0); (4) untap character and all tapped ↷ items; new `DeathPenaltyPaid` event
- R7.3 — Active-player death advances phase ACTION → END: stack drained (items fizzled with `reason="active_player_death"`), `PhaseChanged(ACTION, END)` emitted, `game.state.phase = Phase.END`; `EndTurn` is now legal in `Phase.END` as well as `Phase.ACTION`; all offensive actions remain `ACTION`-only; `on_end_turn` captures `old_phase` before reset so `PhaseChanged` reflects the true pre-reset phase
- R7.4 — `died_this_turn: bool = False` on `TurnFlags`; set by `resolve_player_death`; cleared by `TurnFlags.reset()` on new turn; `resolve_roll` guards the death trigger with `and not game.state.turn_flags.died_this_turn` to prevent a second `PlayerDied` if hp is already 0

Partial / skipped:
- Nothing; all R7 releases complete

---

## 2) Files changed

**New files**

- `tests/test_r71_eternal.py` — 5 tests: `eternal` defaults False, can be set True, orthogonal to tap, `build_demo_game` characters are eternal, freely constructed item is not eternal
- `tests/test_r72_death_penalty.py` — 13 tests: event ordering (PlayerDied before DeathPenaltyPaid), each of the four steps (happy path + empty/zero edge case), eternal character not in destroyable pool, full four-step path together
- `tests/test_r73_active_death_end_phase.py` — 14 tests: phase is END after active-player death, `PhaseChanged(ACTION→END)` emitted, `EndTurn` legal in END, all offensive actions illegal in END, `EndTurn` from END advances turn, `PhaseChanged(END→START)` on EndTurn, turn number increments, full `combat_bot` death flow
- `tests/test_r74_died_this_turn.py` — 7 tests: default False, True after death, exactly one `PlayerDied` and `DeathPenaltyPaid`, guard suppresses second trigger, reset on new turn, full sprint-7 acceptance lifecycle

**Modified files**

- `foursouls/model/item_in_play.py` — `eternal: bool = False` field added to `ItemInPlay`
- `foursouls/model/phase.py` — `died_this_turn: bool = False` added to `TurnFlags`; cleared in `reset()`
- `foursouls/engine/events.py` — `DeathPenaltyPaid(player_id, item_destroyed, loot_discarded, cents_lost, items_deactivated)` event added
- `foursouls/rulesets/common/combat.py` — `resolve_player_death`: full four-step penalty, set `died_this_turn = True`, if active player drain stack + `PhaseChanged(ACTION→END)` + `phase = END`; `resolve_roll`: guard `and not game.state.turn_flags.died_this_turn`; imports extended (`DeathPenaltyPaid`, `EffectFizzled`, `PhaseChanged`, `Phase`)
- `foursouls/rulesets/common/legality.py` — `EndTurn` legal when `phase in (Phase.ACTION, Phase.END)` and stack empty; all other actions still require `Phase.ACTION`
- `foursouls/rulesets/common/turn.py` — `old_phase = state.phase` captured before `reset_for_new_turn`; `PhaseChanged(old_phase, Phase.START)` uses captured value so END→START is logged correctly
- `foursouls/cli/app.py` — character `ItemInPlay` created with `eternal=True`
- `tests/test_player_death.py` — `test_phase_unchanged_after_player_death` renamed to `test_phase_is_end_after_active_player_death`; assertion updated to `Phase.END`
- `tests/test_legality.py` — `test_end_turn_illegal_outside_action_phase` split into `test_end_turn_illegal_in_start_phase` and `test_end_turn_legal_in_end_phase`

---

## 3) Public API changes

```python
# New field on ItemInPlay:
ItemInPlay(card_ref, is_tapped=False, eternal=False)
item.eternal: bool   # True → cannot be destroyed by death penalty

# New field on TurnFlags:
turn_flags.died_this_turn: bool   # True once resolve_player_death fires this turn

# New event:
DeathPenaltyPaid(
    player_id: PlayerId,
    item_destroyed: Optional[CardRef],   # None if no destroyable items
    loot_discarded: Optional[CardRef],   # None if hand was empty
    cents_lost: int,                     # 0 if player had no coins
    items_deactivated: int,              # count of items untapped
)

# Phase after active-player death:
# game.state.phase == Phase.END   (was Phase.ACTION)
# EndTurn is legal in Phase.END
```

---

## 4) Behavioral rules implemented

- **Eternal items:** `ItemInPlay.eternal=True` marks items immune to the death penalty's destroy step. In the current model only the character card is eternal; all `player.items` (treasures bought from the shop) are non-eternal.
- **Death penalty (four steps):**
  1. Destroy first non-eternal item: `player.items.pop(0)` → `treasure_discard` (no-op if empty).
  2. Discard first loot from hand: `player.hand.pop(0)` → `loot_discard` (no-op if empty).
  3. Lose 1¢: `player.cents = max(0, player.cents - 1)` (no-op if broke).
  4. Untap character and all tapped ↷ items (character only in current model).
- **Active-player death → END phase:** after the penalty, if the dying player is the active player, any stack items are fizzled (`EffectFizzled(reason="active_player_death")`), `PhaseChanged(ACTION, END)` is emitted, and `game.state.phase` becomes `Phase.END`. Only `PassPriority` and `EndTurn` are legal from END phase. `EndTurn` in END phase advances the turn identically to `EndTurn` in ACTION phase.
- **One death per turn guard:** `TurnFlags.died_this_turn` prevents `resolve_player_death` from firing twice if hp is already 0 (e.g. if a second miss somehow triggers a re-check). The flag is cleared by `TurnFlags.reset()` at the start of each new turn.

---

## 5) Critical decisions

| Decision | Choice | Why |
|---|---|---|
| `eternal` on `ItemInPlay`, not on `CardRef` | Instance-level flag | Same card may be eternal as a starting item and non-eternal if obtained later (e.g. Dead Cat) |
| Only `player.items` in destroy pool | Exclude `player.character` entirely | Character sits in a separate field; it is always eternal; simpler than checking the flag at destroy time |
| Advance to END phase (not skip to EndTurn automatically) | Explicit END phase | Preserves the explicit `EndTurn` call-site, keeps legality checks clean, and leaves room for future "on-death triggers" to fire before the turn ends |
| `died_this_turn` on `TurnFlags` (not on `PlayerState`) | Turn-scoped, not player-scoped | Death is a per-turn event; `TurnFlags.reset()` already handles all turn-boundary cleanup |
| Stack drain on active-player death | Fizzle all items | Correct rules behaviour; stack in the current model is always empty at this point, but the drain is defensive for future sprints that put things on the stack during combat |

---

## 6) Tests added/updated

**New:**
- `tests/test_r71_eternal.py` — 5 tests
- `tests/test_r72_death_penalty.py` — 13 tests
- `tests/test_r73_active_death_end_phase.py` — 14 tests
- `tests/test_r74_died_this_turn.py` — 7 tests

**Updated:**
- `tests/test_player_death.py` — one assertion updated (phase after death)
- `tests/test_legality.py` — one test split into two

---

## 7) Problems / open questions

- **Death penalty chooses first item, not player-chosen:** the rules say "1 chosen non-eternal item". The current implementation always destroys `player.items[0]`. Choice mechanics require a targeting/selection system not yet in scope.
- **Only one ↷ item today:** step 4 only untaps the character. When treasure items with tap abilities are added (Sprint 11), the untap loop will need to cover `player.items` with `ItemInPlay` wrappers as well. Currently treasures are bare `CardRef` objects.
- **`AttackDeclared` still dead code** (carried from Sprint 5).
- **Treasure items still inert** (carried from Sprint 5).
- **Character HP not differentiated** (carried from Sprint 5).
