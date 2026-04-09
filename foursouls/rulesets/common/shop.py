from __future__ import annotations

from typing import TYPE_CHECKING

from foursouls.engine.events import CoinsSpent, ShopBought
from foursouls.rulesets.common.legality import TREASURE_COST

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


def on_buy_shop(game: Game, slot_index: int) -> None:
    """
    Handle a BuyShop command:
      1. Take the treasure card from the chosen shop slot.
      2. Deduct TREASURE_COST cents from the active player.
      3. Move the card to the active player's treasure area.
      4. Mark purchase as used for this turn.
      5. Refill the emptied slot from the treasure deck (if non-empty).
      6. Emit CoinsSpent then ShopBought.

    This is an immediate action — no stack push, no priority window.
    """
    assert game.zones is not None, "on_buy_shop requires game.zones"

    active_id = game.state.active_player_id
    active = game.state.get_player(active_id)

    card_ref = game.zones.shop_slots.get(slot_index)
    assert card_ref is not None, f"Slot {slot_index} is empty — legality should have prevented this"

    game.zones.shop_slots.clear(slot_index)
    active.cents -= TREASURE_COST
    active.gain_treasure(card_ref)
    game.state.turn_flags.purchase_used = True

    if not game.zones.treasure_deck.empty():
        game.zones.shop_slots.set(slot_index, game.zones.treasure_deck.draw(1)[0])

    item_name = str(card_ref.card_id or "unknown")

    game.log.append(CoinsSpent(
        player_id=active_id,
        amount=TREASURE_COST,
        reason="shop_buy",
    ))
    game.log.append(ShopBought(
        player_id=active_id,
        card_ref=card_ref,
        item_name=item_name,
        slot_index=slot_index,
        cost=TREASURE_COST,
    ))
