"""
Controller — user input / prompt layer for the FourSouls CLI.

Responsibilities
----------------
- Print the board and event narrative (delegates formatting to render.py).
- Prompt the user for input and parse it into a LegalAction.
- Prompt for game-setup parameters (player names, RNG seed).

A future GUI can replace this module while keeping render.py and the
engine action API untouched.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from foursouls.cli.render import render_board, render_events

if TYPE_CHECKING:
    from foursouls.engine.actions import LegalAction
    from foursouls.engine.events import Event
    from foursouls.engine.game_loop import Game


# ─── Display ─────────────────────────────────────────────────────────────────

def display_board(game: "Game", actions: "Sequence[LegalAction]") -> None:
    """Print the full board to stdout."""
    print(render_board(game, actions))


def display_events(events: "Sequence[Event]") -> None:
    """Print the event narrative produced by a step."""
    text = render_events(events)
    if text:
        print(text)


# ─── Input parsing ────────────────────────────────────────────────────────────

def prompt_action(actions: "Sequence[LegalAction]") -> Optional["LegalAction"]:
    """
    Prompt the user to pick an action.

    Accepts:
    - A numeric index  (e.g. ``0``, ``3``)
    - A stable action key  (e.g. ``pass``, ``attack:0``)
    - ``q`` / ``quit`` / ``exit``  → returns None (caller should quit)

    Loops until a valid selection is made.
    """
    while True:
        try:
            raw = input("> ").strip()
        except EOFError:
            return None

        if raw.lower() in ("q", "quit", "exit"):
            return None

        # Numeric index
        if raw.isdigit():
            idx = int(raw)
            if 0 <= idx < len(actions):
                return actions[idx]
            print(f"  Invalid — enter 0–{len(actions) - 1}, an action key, or 'q'.")
            continue

        # Stable key match
        for a in actions:
            if raw == a.key:
                return a

        print(f"  Unknown input '{raw}'. Enter a number, action key, or 'q'.")


# ─── Setup prompts ────────────────────────────────────────────────────────────

def prompt_num_players(min_: int = 1, max_: int = 4) -> int:
    """Ask how many players will play (validated)."""
    while True:
        raw = input(f"Number of players ({min_}–{max_}): ").strip()
        if raw.isdigit():
            n = int(raw)
            if min_ <= n <= max_:
                return n
        print(f"  Please enter a number between {min_} and {max_}.")


def prompt_player_name(index: int, default: str) -> str:
    """Ask for a player name, accepting the default on blank input."""
    raw = input(f"  Player {index + 1} name [{default}]: ").strip()
    return raw if raw else default


def prompt_seed() -> int:
    """Ask for an RNG seed (blank → 0)."""
    raw = input("RNG seed (blank = 0): ").strip()
    if raw.lstrip("-").isdigit():
        return int(raw)
    return 0
