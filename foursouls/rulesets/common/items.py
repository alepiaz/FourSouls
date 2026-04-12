from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from foursouls.engine.events import ItemActivated
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.refs import PlayerId
from foursouls.model.target import AnyTarget

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game
    from foursouls.model.refs import InstanceId


def fire_on_enters_play(game: Game, player_id: PlayerId, item: ItemInPlay) -> None:
    """Call TreasureDef.on_enters_play for the given item, if defined."""
    from foursouls.cards.treasures import TREASURE_REGISTRY
    card_id = item.card_ref.card_id
    if card_id is None:
        return
    defn = TREASURE_REGISTRY.get(card_id)
    if defn is not None and defn.on_enters_play is not None:
        defn.on_enters_play(game, player_id)


def fire_on_start_of_turn(game: Game) -> None:
    """Call TreasureDef.on_start_of_turn for each item the active player controls."""
    from foursouls.cards.treasures import TREASURE_REGISTRY
    active_id = game.state.active_player_id
    for item in game.state.get_player(active_id).items:
        card_id = item.card_ref.card_id
        if card_id is None:
            continue
        defn = TREASURE_REGISTRY.get(card_id)
        if defn is not None and defn.on_start_of_turn is not None:
            defn.on_start_of_turn(game)


def on_activate_item(game: Game, instance_id: InstanceId, target: Optional[AnyTarget]) -> None:
    """
    Process an ActivateItem command:
      1. Locate the item in the active player's items.
      2. Look up its TreasureDef in the registry.
      3. Tap the item and emit ItemActivated.
      4. Build the inner effect via TreasureDef.make_tap_effect.
      5. Wrap in TreasureActivateEffect (handles is_one_use destruction).
      6. Push onto the stack; reset priority to the active player.
    """
    from foursouls.cards.treasures import TREASURE_REGISTRY
    from foursouls.rulesets.common.effects import TreasureActivateEffect

    active_id = game.state.active_player_id
    player = game.state.get_player(active_id)

    item = next(
        (i for i in player.items if i.card_ref.instance_id == instance_id),
        None,
    )
    if item is None:
        return

    card_id = item.card_ref.card_id
    defn = TREASURE_REGISTRY.get(card_id) if card_id is not None else None
    if defn is None or defn.make_tap_effect is None:
        return

    item.tap()
    game.log.append(ItemActivated(player_id=active_id, source=f"item:{card_id}"))

    inner = defn.make_tap_effect(target, game)

    wrapper = TreasureActivateEffect(
        player_id=active_id,
        instance_id=instance_id,
        inner=inner,
        is_one_use=defn.is_one_use,
        treasure_discard=game.zones.treasure_discard,
        log=game.log,
    )

    game.push_to_stack(
        controller_id=active_id,
        source=f"item:{card_id}",
        effect=wrapper,
        label=defn.name,
    )
    game.priority.reset_to(active_id)
