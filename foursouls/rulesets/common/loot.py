from __future__ import annotations

from typing import TYPE_CHECKING

from foursouls.cards.loot import make_loot_effect
from foursouls.engine.events import LootPlayed
from foursouls.model.refs import CardRef
from foursouls.rulesets.common.effects import PlayLootEffect

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


def on_play_loot(game: Game, card_ref: CardRef) -> None:
    """
    Handle a PlayLoot command:
      1. Remove the card from the active player's hand (cost).
      2. Increment loot_plays_used.
      3. Emit LootPlayed.
      4. Build the card's effect, wrapped in PlayLootEffect for discard.
      5. Push onto the stack.
      6. Reset priority so a response window opens.
    """
    assert game.zones is not None, "on_play_loot requires game.zones"
    assert card_ref.card_id is not None, f"CardRef has no card_id: {card_ref}"

    active_id = game.state.active_player_id
    active = game.state.get_player(active_id)

    active.hand.remove(card_ref)
    game.state.turn_flags.loot_plays_used += 1

    card_name = str(card_ref.card_id)
    game.log.append(LootPlayed(
        player_id=active_id,
        card_id=card_ref.card_id,
        card_name=card_name,
    ))

    inner = make_loot_effect(card_ref.card_id, active_id)
    effect = PlayLootEffect(
        card_ref=card_ref,
        inner=inner,
        loot_discard=game.zones.loot_discard,
        player_id=active_id,
        log=game.log,
    )

    game.push_to_stack(
        controller_id=active_id,
        source=card_ref,
        effect=effect,
        label=f"PlayLoot:{card_ref.card_id}",
    )
    game.priority.reset_to(active_id)
