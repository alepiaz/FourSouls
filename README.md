# Four Souls (Python) — Engine-first learning project

A small, test-driven, **engine-first** implementation of *The Binding of Isaac: Four Souls*, built to be **deterministic**, **scalable**, and ready to power a future GUI.

Right now this repo contains:
- a solid **Sprint 0 kernel** (stack + priority + effects + events + deterministic RNG)
- a **Sprint 1 playable CLI slice** (turn flow + "Loot 1" scheduling + draw-to-hand)

> Goal: keep the rules engine independent from any UI so we can plug in a proper board/video-game GUI later.

---

## Current gameplay slice (Sprint 1)

You can "play" a minimal loop:
1. Start of turn auto-schedules **LOOT_1** onto the stack
2. Players `pass` around → LOOT_1 resolves → active player draws 1 Loot into hand
3. Phase becomes `ACTION`
4. Active player can `end turn` (stack empty)
5. Next player turn begins and repeats

It's intentionally tiny: no playing loot cards yet, no combat, no shop, no monsters.

---

## Tech principles

- **Deterministic**: all randomness goes through a seeded `RNG`
- **SRP / OOP**: separate engine primitives from model data from rulesets
- **Test-driven**: most features come with pytest coverage
- **Scalable**: cards/effects are designed to become data-driven and UI-ready

---

## Requirements

- Python **3.11+**
- `pytest` (dev dependency)

---

## Install

From repo root:

```bash
pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

### Run the CLI demo

```bash
python run_cli.py
```

---

## CLI controls

- **p** → pass priority
- **e** → end turn (only when legal)
- **q** → quit

The UI prints:

- active player, phase, turn number
- priority holder
- stack size + top label
- loot deck/discard sizes
- each player hand contents (instance ids)

---

## Project structure

```
foursouls/
  engine/        # generic engine utilities (stack, priority, rng, zones, game loop)
  model/         # game state + domain types (effects, commands, turn state)
  rulesets/      # legality + turn automation + setup pipeline
  agents/        # human CLI / bots (UI clients)
tests/           # pytest suite
run_cli.py       # small interactive demo runner
```

---

## Key modules (what to read first)

### [foursouls/engine/game_loop.py](foursouls/engine/game_loop.py)

The kernel `Game.step()` loop (commands → events → stack resolution).

### [foursouls/engine/stack.py](foursouls/engine/stack.py) and [engine/priority.py](foursouls/engine/priority.py)

The timing core (LIFO + pass cycles).

### [foursouls/model/effects.py](foursouls/model/effects.py) and [model/effect_context.py](foursouls/model/effect_context.py)

Effects are validated/applied at resolution time and can use RNG.

### [foursouls/rulesets/common/turn.py](foursouls/rulesets/common/turn.py)

Sprint 1 turn automation (schedule LOOT_1; enter ACTION after it resolves).

### [foursouls/rulesets/common/setup.py](foursouls/rulesets/common/setup.py)

Deterministic setup with a tiny "real card" loot list (coins/bomb/dice).

---

## How the engine works (current)

1. Players take actions by submitting a `Command` (Sprint 1: `PASS`, `END_TURN`)

2. The game maintains a `Stack` of `StackItems` (label + controller + effect)

3. Players pass priority; once all pass, the top stack item resolves

4. Resolution calls:
   - `effect.validate(ctx)` then `effect.apply(ctx)` (or emits fizzle event)

5. Events are appended to an `EventLog` for debugging/testing

---

## Determinism

Determinism is guaranteed by:

- using `RNG(seed=...)` and never calling `random` directly
- shuffling decks via `DeckZone.shuffle(rng)`
- resolving effects through `EffectContext(state, rng)`

If you run `run_cli.py` twice with the same seed, you should see the same sequence of draws.

---

## Roadmap (high-level)

### Sprint 2 (next)

First real "card play" subset:

- Play Loot cards (coins/bomb/dice) with targeting
- Add discard behavior for played loot
- Start building a "target selection" system (UI-friendly)

### Sprint 3–6

- Monsters + attack flow (simplified then expanded)
- Shop slots, purchases, rewards
- Card registry (CardDef) + JSON content loading
- UI snapshot/query layer (GameSnapshot) for GUIs

### Sprint 9–10 (planned)

A real GUI with board + card images (engine remains the source of truth)

---

## Notes / disclaimers

This is a learning project. The real Four Souls rules contain many edge cases and timing nuances. The engine is being built to support those over time, but Sprint 1 is intentionally minimal.

---

## License

Pick a license once you're ready to publish/share (MIT is common for learning projects).
