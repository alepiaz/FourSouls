"""
FourSouls CLI — game factory and interactive main loop.

Usage
-----
    python -m foursouls.cli            # interactive setup
    python -m foursouls.cli.app        # same

Programmatic usage::

    from foursouls.cli.app import build_demo_game, run
    game = build_demo_game(["Alice", "Bob"], seed=42)
    run(game)
"""
from __future__ import annotations

from typing import List, Optional

from foursouls.cards.characters import CAIN, EVE, ISAAC, MAGDALENE, get_character_def
from foursouls.cards.loot import BLANK_RUNE, BOMB_BANG, LOOT_COIN, SOUL_HEART
from foursouls.cards.monsters import CURSED_CHEST, FLY, GAPER, HEADLESS_HORSEMAN, HORF, MONSTRO, SPIDER, WE_NEED_TO_GO_DEEPER
from foursouls.cli.controller import (
    display_board,
    display_events,
    prompt_action,
    prompt_num_players,
    prompt_player_name,
    prompt_seed,
)
from foursouls.engine.events import GameWon
from foursouls.engine.game_loop import Game
from foursouls.model.commands import PassPriority
from foursouls.model.phase import Phase
from foursouls.engine.rng import RNG
from foursouls.model.game_state import GameState
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.setup import setup_game


# ─── Deck builders ────────────────────────────────────────────────────────────

def _loot_deck() -> List[CardRef]:
    """40-card loot deck: mostly coins, a few bombs."""
    pool = [
        LOOT_COIN, LOOT_COIN, LOOT_COIN,
        LOOT_COIN, LOOT_COIN,
        LOOT_COIN,
        BOMB_BANG,
        SOUL_HEART,
        BLANK_RUNE,
    ]
    cards: List[CardRef] = []
    iid = 0
    for _ in range(5):          # 5 copies of the 7-card pool = 35 cards + padding
        for cid in pool:
            cards.append(CardRef(InstanceId(f"loot-{iid}"), cid))
            iid += 1
    # pad to 40
    while len(cards) < 40:
        cards.append(CardRef(InstanceId(f"loot-{iid}"), LOOT_COIN))
        iid += 1
    return cards


def _treasure_deck() -> List[CardRef]:
    """12-card placeholder treasure deck (buy effects TBD)."""
    return [CardRef(InstanceId(f"treasure-{i}")) for i in range(12)]


def _monster_deck() -> List[CardRef]:
    """21-card monster deck — basic monsters, bosses (soul), and events."""
    pool = [
        (FLY,               6),
        (GAPER,             4),
        (SPIDER,            4),
        (HORF,              2),
        (MONSTRO,           1),
        (HEADLESS_HORSEMAN, 1),
        (CURSED_CHEST,           1),
        (WE_NEED_TO_GO_DEEPER,   1),
    ]
    cards: List[CardRef] = []
    iid = 0
    for cid, count in pool:
        for _ in range(count):
            cards.append(CardRef(InstanceId(f"monster-{iid}"), cid))
            iid += 1
    return cards


# ─── Game factory ─────────────────────────────────────────────────────────────

def build_demo_game(
    player_ids: Optional[List[str]] = None,
    *,
    seed: int = 0,
) -> Game:
    """
    Build a fully initialized game ready for the first step.

    Parameters
    ----------
    player_ids:
        Display names for each player.  Defaults to ``["P1", "P2"]``.
    seed:
        RNG seed for reproducibility.
    """
    if player_ids is None:
        player_ids = ["P1", "P2"]

    _CHAR_POOL = [ISAAC, MAGDALENE, CAIN, EVE]

    players = []
    for i, pid in enumerate(player_ids):
        char_card_id = _CHAR_POOL[i % len(_CHAR_POOL)]
        char_def = get_character_def(char_card_id)
        p = PlayerState(
            player_id=PlayerId(pid),
            max_hp=char_def.base_hp,
            hp=char_def.base_hp,
            attack=char_def.attack,
        )
        p.character = ItemInPlay(card_ref=CardRef(InstanceId(f"char-{i}"), char_card_id), eternal=True)
        players.append(p)
    state = GameState.from_players(players)

    return setup_game(
        state,
        loot_cards=_loot_deck(),
        treasure_cards=_treasure_deck(),
        monster_cards=_monster_deck(),
        rng=RNG(seed=seed),
        starting_hand_size=3,
        shop_size=2,
        monster_slot_count=2,
    )


# ─── Main game loop ───────────────────────────────────────────────────────────

def run(game: Optional[Game] = None) -> None:
    """
    Run the interactive CLI game loop.

    If *game* is None the user is prompted for setup and a demo game
    is constructed via :func:`build_demo_game`.
    """
    if game is None:
        _WIDTH = 72
        print("=" * _WIDTH)
        print("  Four Souls - CLI")
        print("=" * _WIDTH)
        print()

        n = prompt_num_players()
        player_ids: List[str] = []
        for i in range(n):
            player_ids.append(prompt_player_name(i, f"P{i + 1}"))

        seed = prompt_seed()
        print()

        game = build_demo_game(player_ids, seed=seed)

    winner: Optional[str] = None

    while winner is None and not game.game_over:
        actions = game.get_legal_actions()

        # Auto-pass when PassPriority is the only legal move, or during
        # START/END phases where player input is never meaningful.
        pass_action = next((a for a in actions if isinstance(a.command, PassPriority)), None)
        if pass_action is not None and (
            len(actions) == 1 or game.state.phase in (Phase.START, Phase.END)
        ):
            result = game.step(pass_action.command)
            if result.events:
                print()
                display_events(result.events)
                print()
            continue

        display_board(game, actions)

        chosen = prompt_action(actions)
        if chosen is None:
            print("\nQuit. Goodbye.")
            return

        acting_player_id = game.priority.current()
        result = game.step(chosen.command)

        # Check for game-over event before printing narrative
        for event in result.events:
            if isinstance(event, GameWon):
                winner = event.player_id
                break

        if result.events:
            print()
            display_events(result.events)
            print()

        # After a stack-pushing action (PlayLoot, ActivateCharacterAbility,
        # ActivateItem) the engine resets priority to the acting player. Auto-pass
        # for them so the opponent immediately receives the response window instead
        # of the acting player seeing a useless "Pass" prompt first.
        if (not isinstance(chosen.command, PassPriority)
                and not game.stack.empty()
                and game.priority.current() == acting_player_id):
            result2 = game.step(PassPriority())
            if result2.events:
                print()
                display_events(result2.events)
                print()

    _WIDTH = 72
    print("═" * _WIDTH)
    print(f"  GAME OVER — {winner} wins!")
    print("═" * _WIDTH)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    """Console-script entry point."""
    try:
        run()
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye.")


if __name__ == "__main__":
    main()
