from __future__ import annotations

from foursouls.agents.human_cli import HumanCLI
from foursouls.engine.game_loop import Game
from foursouls.engine.rng import RNG
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import PlayerId
from foursouls.rulesets.common.setup import setup_game_state


def main() -> None:
    # Two players, one of them can be The Lost-like with 1 HP
    players = [
        PlayerState(player_id=PlayerId("P1"), max_hp=2, hp=2),
        PlayerState(player_id=PlayerId("P2"), max_hp=1, hp=1),
    ]

    gs = setup_game_state(
        players, seed=123, starting_hand_size=3, active_player_index=0
    )
    game = Game(gs, rng=RNG(seed=123))

    HumanCLI(game).run()


if __name__ == "__main__":
    main()
