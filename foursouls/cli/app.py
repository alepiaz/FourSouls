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
from foursouls.cards.loot import (
    BLANK_RUNE, BOMB_BANG, BUTTER_BEAN, FOUR_CENTS, GOLD_BOMB_BANG_BANG,
    LOOT_COIN, NICKEL, SOUL_HEART, THREE_CENTS, TWO_CENTS,
)
from foursouls.cards.monsters import (
    ATTACK_FLY, BIG_SPIDER, BONY, BOOM_FLY, CARRION_QUEEN, CLOTTY, CURSED_CHEST,
    DINGA, FLY, GAPER, HEADLESS_HORSEMAN, HORF, MEGA_FATTY, MONSTRO, MULLIBOIL,
    SPIDER, WE_NEED_TO_GO_DEEPER,
)
from foursouls.cards.treasures import DRY_BABY, MAMA_MEGA, MEAT_BANG
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

def _make_deck(prefix: str, pool: list[tuple]) -> List[CardRef]:
    """Build distinct runtime cards from an explicit demo distribution."""
    return [
        CardRef(InstanceId(f"{prefix}-{index}"), card_id)
        for index, card_id in enumerate(
            card_id for card_id, count in pool for _ in range(count)
        )
    ]


def _loot_deck() -> List[CardRef]:
    """40-card demo deck covering all implemented loot definitions."""
    return _make_deck("loot", [
        (LOOT_COIN, 12), (TWO_CENTS, 6), (THREE_CENTS, 4),
        (FOUR_CENTS, 3), (NICKEL, 2), (BOMB_BANG, 4),
        (GOLD_BOMB_BANG_BANG, 1), (SOUL_HEART, 3),
        (BLANK_RUNE, 2), (BUTTER_BEAN, 3),
    ])


def _treasure_deck() -> List[CardRef]:
    """Demo treasures with functional effects; starting eternals stay separate."""
    return _make_deck("treasure", [(DRY_BABY, 4), (MEAT_BANG, 4), (MAMA_MEGA, 4)])


def _monster_deck() -> List[CardRef]:
    """Demo pool, not an official deck distribution; enough souls for victory."""
    return _make_deck("monster", [
        (FLY, 3), (BONY, 1), (GAPER, 3), (SPIDER, 3), (HORF, 2),
        (DINGA, 2), (ATTACK_FLY, 2), (BOOM_FLY, 2),
        (CLOTTY, 2), (MULLIBOIL, 2), (BIG_SPIDER, 2),
        (MONSTRO, 2), (MEGA_FATTY, 1), (CARRION_QUEEN, 3), (HEADLESS_HORSEMAN, 3),
        (CURSED_CHEST, 1), (WE_NEED_TO_GO_DEEPER, 1),
    ])


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
