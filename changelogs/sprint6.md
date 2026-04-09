# Sprint 6 — Win Condition & Game Termination

---

## 1) Sprint / commit context

**Sprint:** Sprint 6  
**What's done vs partial:**

Done:
- R6.1 — Heal timing: all players **and all monsters** heal to full at end of every turn (moved from Sprint 5 partial to confirmed spec)
- R6.2 — `game_over: bool = False` flag on `Game`; `legal_commands()` returns `[]` immediately when set; `game.step()` raises `ValueError` for any command; `get_legal_actions()` returns `[]`
- R6.3 — `game_over = True` triggered by soul win condition in `resolve_monster_death`; `GameWon` event emitted with `player_id` and `soul_count`
- R6.4 — CLI loop guard: `while winner is None and not game.game_over`; game exits cleanly without prompting on an empty action list; `test_sprint6_acceptance.py` drives `combat_bot` to 4 souls

Partial / skipped:
- Nothing; all R6 releases complete

---

## 2) Files changed

**New files**

- `tests/test_game_over.py` — 6 tests: `legal_commands() == []` when `game_over`, `get_legal_actions() == []`, `step()` raises `ValueError`, killing 4th soul sets `game_over`, killing non-winning soul does not, killing non-soul monster never sets `game_over`
- `tests/test_sprint6_acceptance.py` — full acceptance: `combat_bot` pre-loaded with 3 souls kills a guaranteed soul monster → `game_over=True`, `get_legal_actions()==[]`, exactly one `GameWon` event with correct `player_id` and `soul_count`

**Modified files**

- `foursouls/engine/game_loop.py` — `game_over: bool = False` field on `Game`; `legal_commands()` short-circuits to `[]` when set; `step()` raises `ValueError("Illegal command: ...")` before dispatching when `game_over`
- `foursouls/rulesets/common/combat.py` — after `resolve_monster_death`, if `len(attacker.souls) >= SOULS_TO_WIN`: emit `GameWon(player_id, soul_count)`, set `game.game_over = True`
- `foursouls/cli/app.py` — loop condition changed from `while winner is None:` to `while winner is None and not game.game_over:`

---

## 3) Public API changes

```python
# New field on Game:
game.game_over: bool   # False until a player reaches SOULS_TO_WIN souls

# Behaviour when game_over is True:
game.legal_commands()      # → []
game.get_legal_actions()   # → []
game.step(any_cmd)         # → raises ValueError

# New event:
GameWon(player_id: PlayerId, soul_count: int)
```

---

## 4) Behavioral rules implemented

- **Game-over lock:** once `game.game_over = True`, no further commands are accepted. The engine raises `ValueError`; the CLI loop exits naturally.
- **Win condition:** killing a soul monster that pushes the attacker's soul count to ≥ 4 ends the game immediately in `resolve_monster_death`. `GameWon` is emitted before the priority reset.
- **CLI exit:** the CLI no longer calls `prompt_action([])` after a game-winning kill. The `game.game_over` guard in the while condition catches the case even when `winner` is not yet set from the event stream.

---

## 5) Critical decisions

| Decision | Choice | Why |
|---|---|---|
| `game_over` flag (not exception or sentinel) | Simple `bool` field on `Game` | Readable in tests; easy CLI guard; consistent with how `combat` and `zones` are nullable flags |
| `step()` raises `ValueError` when over | Hard error rather than no-op | Prevents silent bugs in bots that don't check the flag |
| `GameWon` emitted before `game_over = True` | Event first, then flag | Event consumers (CLI, tests) can act on the event in the same `StepResult` that flips the flag |

---

## 6) Tests added/updated

**New:**
- `tests/test_game_over.py` — 6 tests (see §2)
- `tests/test_sprint6_acceptance.py` — 1 acceptance test (see §2)

**Updated:**
- `foursouls/cli/app.py` — loop guard only; no test changes required

---

## 7) Problems / open questions

- **`AttackDeclared` still dead code** (carried from Sprint 5).
- **Treasure items still inert** (carried from Sprint 5).
- **Character HP not differentiated** (carried from Sprint 5).
- **Death penalty is a stub:** `resolve_player_death` ends combat and resets priority but does not apply item loss / loot discard / cent loss. Addressed in Sprint 7.
