from __future__ import annotations

from typing import TYPE_CHECKING, List

from foursouls.model.commands import ActivateCharacterAbility, BuyShop, Command, EndTurn, PassPriority, PlayLoot
from foursouls.model.phase import Phase

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game

# Standard shop cost in cents (base game: one coin = 10 cents)
TREASURE_COST = 10


def legal_commands(game: Game) -> List[Command]:
    """
    Sprint 2 legality rules:
    - PassPriority: always legal.
    - EndTurn: legal only when phase is ACTION and the stack is empty.
    - PlayLoot(card_ref): one entry per card in the active player's hand when
        phase is ACTION, stack is empty, and loot quota not exhausted.
    - ActivateCharacterAbility: legal when phase is ACTION, stack is empty,
        and the active player's character exists and is not tapped.
    """
    state = game.state
    stack = game.stack

    cmds: List[Command] = [PassPriority()]

    if state.phase == Phase.ACTION and stack.empty():
        cmds.append(EndTurn())

        active = state.get_player(state.active_player_id)
        flags = state.turn_flags

        if flags.loot_plays_used < flags.loot_plays_allowed:
            for card_ref in active.hand:
                cmds.append(PlayLoot(card_ref=card_ref))

        char = active.character
        if char is not None and not char.is_tapped:
            cmds.append(ActivateCharacterAbility())

        if not flags.purchase_used and game.zones is not None:
            for idx in game.zones.shop_slots.filled_indices():
                if active.cents >= TREASURE_COST:
                    cmds.append(BuyShop(slot_index=idx))

    return cmds
