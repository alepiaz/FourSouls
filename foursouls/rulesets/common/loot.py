from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from foursouls.cards.loot import make_loot_effect
from foursouls.engine.events import LootPlayed
from foursouls.model.refs import CardRef
from foursouls.model.target import AnyTarget
from foursouls.rulesets.common.effects import PlayLootEffect

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


def on_play_loot(game: Game, card_ref: CardRef, target: Optional[AnyTarget] = None) -> None:
    """
    Handle a PlayLoot command:
      1. Determine who is playing: priority holder for off-turn plays, active
         player otherwise.
      2. Remove the card from that player's hand (cost).
      3. Update the appropriate quota counter.
      4. Emit LootPlayed.
      5. Build the card's effect, wrapped in PlayLootEffect for discard.
      6. Push onto the stack.
      7. Reset priority to active player so a response window opens.
    """
    assert game.zones is not None, "on_play_loot requires game.zones"
    assert card_ref.card_id is not None, f"CardRef has no card_id: {card_ref}"

    active_id = game.state.active_player_id
    player_id = game.priority.current()
    player = game.state.get_player(player_id)

    player.hand.remove(card_ref)

    flags = game.state.turn_flags
    if player_id == active_id:
        flags.loot_plays_used += 1
    else:
        pid = str(player_id)
        flags.extra_loot_plays[pid] = max(0, flags.extra_loot_plays.get(pid, 0) - 1)

    card_name = str(card_ref.card_id)
    game.log.append(LootPlayed(
        player_id=player_id,
        card_id=card_ref.card_id,
        card_name=card_name,
    ))

    inner = make_loot_effect(
        card_ref.card_id,
        player_id,
        target=target,
        monster_slots=game.zones.monster_slots,
        rng=game.rng,
        loot_deck=game.zones.loot_deck,
        log=game.log,
        stack=game.stack,
    )
    effect = PlayLootEffect(
        card_ref=card_ref,
        inner=inner,
        loot_discard=game.zones.loot_discard,
        player_id=player_id,
        log=game.log,
    )

    game.push_to_stack(
        controller_id=player_id,
        source=card_ref,
        effect=effect,
        label=f"PlayLoot:{card_ref.card_id}",
    )
    game.priority.reset_to(active_id)
