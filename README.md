# Four Souls Python Engine

A Python implementation of **The Binding of Isaac: Four Souls** focused on one long-term question:

> Can we demonstrate, with actual gameplay and statistics, that some cards are so strong that they produce a measurable advantage?

This project is not just a playable clone. It is a **rules-driven simulation environment** whose end goal is to support:

- accurate game execution,
- reproducible automated matches,
- AI / strategy bots,
- reinforcement learning experiments,
- and statistical analysis of card strength, balance, and meta impact.

---

## How to run

### Requirements

- Python 3.11 or later

### Install

```bash
pip install -e ".[dev]"
```

This installs the `foursouls` package in editable mode along with `pytest`.

### Run the tests

```bash
pytest
```

### Play interactively (CLI)

```bash
python -m foursouls.cli
```

You will be prompted for the number of players, their names, and an RNG seed. The board is rendered in the terminal after each action and you pick moves from a numbered menu.

### Start a game from code

```python
from foursouls.cli.app import build_demo_game, run

game = build_demo_game(["Alice", "Bob"], seed=42)
run(game)          # interactive loop
```

`build_demo_game` accepts any number of player name strings and an integer seed for full reproducibility.

### Available bots

Bots live in `agents/` and can be used to drive the game programmatically:

| Bot | File | Behaviour |
|-----|------|-----------|
| `combat_bot` | `agents/combat_bot.py` | Always attacks when possible |
| `economy_bot` | `agents/economy_bot.py` | Prioritises buying and looting |
| `pass_bot` | `agents/pass_bot.py` | Always passes priority (useful in tests) |

```python
from agents.combat_bot import choose_command

while not game.game_over:
    game.step(choose_command(game))
```

---

## Project vision

The final system should let us:

1. **Play the game manually** and verify that the engine behaves like the real rules.
2. **Add cards incrementally** without rewriting the engine every time.
3. **Run automated games** between bots or AI agents.
4. **Collect statistics** on outcomes, card performance, and decision quality.
5. **Test hypotheses** such as:
   - Are some cards overpowered?
   - Do certain openings create unfair win rates?
   - Does going first matter?
   - Which strategies outperform others over large samples?

In short, this repository aims to become both:

- a **playable Four Souls engine**, and
- a **research / simulation platform** for balance and strategy analysis.

---

## Current project priority

The current stage of the project is **infrastructure first**.

Before deep card coverage, AI, or large-scale simulations, we need a solid foundation:

- a deterministic rules engine,
- clear game state transitions,
- stack and priority handling,
- reproducible setup,
- a manually playable CLI,
- expressive events for debugging and UI,
- and enough tests to trust the engine.

Right now, the most important question is not:

> "Do we already support every card?"

It is:

> "Can developers confidently verify that the game behaves according to the rules?"

That is why the current work emphasizes engine structure, legality checks, event flow, and testability.

---

## Core design goals

### 1. Rules-first engine
The engine should model the actual game structure as closely as practical:
- phases,
- priority,
- the stack,
- combat timing,
- triggered / activated abilities,
- purchases,
- death,
- rewards,
- and victory conditions.

### 2. Deterministic and testable
A seeded RNG and explicit state transitions are essential.
We want developers to be able to reproduce games, replay bugs, and write reliable tests.

### 3. Extensible card support
The engine should not be hardcoded around a tiny starter set forever.
It should be possible to add more loot, treasure, monsters, bosses, and events over time without breaking the whole architecture.

### 4. Human-playable and machine-playable
The same engine should support:
- CLI/manual play,
- scripted tests,
- bots,
- simulations,
- and later, possibly GUI frontends.

### 5. Observable
The engine should emit rich domain events so developers can:
- understand what happened,
- debug state changes,
- drive a UI,
- and later implement triggers and analysis tooling.

---

## Broad scope of the project

This project has three layers of scope.

### Layer 1 — Rules engine
The rules engine is the core of everything else.

It is responsible for:
- game setup,
- turn flow,
- phase progression,
- command legality,
- stack resolution,
- combat resolution,
- purchases,
- death and cleanup,
- card movement between zones,
- and victory detection.

This layer should remain independent from any specific UI.

### Layer 2 — Playability and developer tooling
This layer exists so humans can inspect and validate the engine.

It includes:
- CLI play,
- readable board rendering,
- legal action menus,
- debug-friendly event logs,
- deterministic seeds,
- acceptance tests,
- and regression coverage.

This is the layer that lets contributors confirm:
> "Yes, the game is behaving correctly."

### Layer 3 — Simulation and analysis
Once the rules engine is stable enough, the project expands into research and evaluation.

This includes:
- simple strategy bots,
- stronger heuristic agents,
- reinforcement learning agents,
- tournament runners,
- batch simulations,
- telemetry,
- and statistics dashboards / exports.

This is the layer that lets us ask:
> "Is this card actually broken?"

---

## Broad rules model

This repository is not intended to replace the official rulebook, but developers need a shared mental model of the system the engine is trying to implement.

At a high level, Four Souls is modeled here as:

- a **turn-based multiplayer card game**,
- with **priority passing**,
- a **stack** for actions and effects,
- multiple **zones** (hands, decks, discard piles, board, shop, monster slots, etc.),
- and a game loop built around **setup**, **turn phases**, **actions**, **combat**, **death**, and **victory**.

### Broad gameplay structure

A player's turn broadly follows this kind of flow:

1. **Start Phase**
   - Start-of-turn effects occur.
   - The active player loots.
   - Priority and the stack may matter before the turn moves on.

2. **Action Phase**
   - Players may play loot cards.
   - Players may activate character and item abilities.
   - The active player may attack.
   - The active player may purchase from the shop.
   - Priority matters throughout.

3. **Combat / Stack interaction**
   - Attacks, rolls, damage, and deaths are not just "instant math."
   - They interact with stack timing and response windows.

4. **End Phase**
   - Cleanup and end-of-turn effects occur.
   - Healing / reset timing happens here according to the rules.
   - The next player becomes active.

### Main rules concepts developers should think in

#### Priority
Only the player with priority may currently act.
When all players pass in sequence:
- the top of the stack resolves, or
- the game advances if nothing is on the stack and the phase allows it.

#### Stack
Most meaningful actions and effects should be modeled in a way that supports:
- responses,
- resolution order,
- and triggered consequences.

#### Commands and legality
The UI should not invent what is allowed.
The engine should expose what actions are legal based on:
- phase,
- active player,
- priority holder,
- combat state,
- taps / activations used,
- stack state,
- and card-specific rules.

#### Zones
Cards and entities move between different areas:
- deck,
- hand,
- discard,
- shop,
- in-play items,
- monster slots,
- souls,
- and so on.

#### Deterministic randomness
Randomness is part of the game, but for testing and simulations it must be reproducible.

---

## What "rules accuracy" means in this project

Rules accuracy does **not** mean:

- every single card is already implemented,
- every edge case exists from day one,
- or the first playable version is full-fidelity.

Rules accuracy means the project is built so that:

1. the **core timing model** is correct,
2. the **state model** is explicit,
3. missing features can be added without undoing the architecture,
4. and developers can compare implementation behavior against the official rules.

The project can start with a narrow card set and still be "on the right track" if the underlying model is sound.

---

## Current development philosophy

This project is being built in vertical slices.

That means each sprint tries to deliver a playable, testable piece of the game rather than a huge incomplete abstraction layer.

Examples of slice-oriented progress:
- setup + turn flow,
- loot play + character abilities,
- shop,
- monsters + combat,
- CLI playability,
- event quality,
- then broader rule parity and more cards.

This approach helps us:
- validate architecture early,
- catch bad assumptions fast,
- and always keep the project in a runnable state.

---

## Long-term goals

The long-term end state is roughly:

### Fuller card coverage
Support a broad set of:
- loot,
- treasure,
- monsters,
- bosses,
- events,
- and other rule objects.

### Bot framework
Allow multiple styles of agents:
- random bots,
- simple scripted bots,
- heuristic strategy bots,
- and stronger search-based or learned agents.

### Reinforcement learning / training environment
Expose the engine in a way that makes it possible to train agents on:
- action selection,
- combat timing,
- resource usage,
- and broader strategic choices.

### Statistics and balance analysis
Support large batches of games and export data such as:
- win rates,
- card appearance vs win correlation,
- damage / reward efficiency,
- first-player advantage,
- matchup performance,
- and card-specific impact metrics.

This is the part that answers the original research question about "broken" cards.

---

## Non-goals for the current stage

At this stage, this project is **not** trying to prioritize:

- a polished production GUI,
- complete support for every expansion immediately,
- flashy presentation over correctness,
- or AI before the rules engine is trustworthy.

A bot that plays a wrong game is not useful.
A simulator with broken timing rules is not useful.
A statistics pipeline on top of inaccurate rules is not useful.

So the order matters:
**engine first, confidence second, scale third.**

---

## Contributor mindset

When contributing, prefer changes that improve one or more of the following:

- correctness,
- clarity,
- testability,
- determinism,
- observability,
- extensibility.

Be careful about changes that:
- hardcode behavior into the CLI,
- bypass legality checks,
- couple UI to engine internals,
- or solve one card in a way that makes future cards harder to model.

A good contribution is not just "it works once."
A good contribution makes the engine easier to trust and easier to grow.

---

## The practical question behind the project

This repo exists because "this card feels broken" is easy to say and hard to prove.

The project's real ambition is to make statements like these testable:

- "Card X increases win rate significantly."
- "Card Y produces unfair tempo swings compared to similar cards."
- "This opening configuration creates a measurable advantage."
- "This strategy dominates under realistic play."

To get there, we first need a game engine that developers can inspect, trust, and extend.

That is the current mission of the project.
