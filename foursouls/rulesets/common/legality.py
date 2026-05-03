from __future__ import annotations

from typing import TYPE_CHECKING, List

from foursouls.cards.loot import allows_monster_target, allows_stack_target, requires_target
from foursouls.cards.treasures import TREASURE_REGISTRY
from foursouls.model.commands import ActivateCharacterAbility, ActivateItem, AttackMonster, BuyShop, Command, EndTurn, PassPriority, PlayLoot, RollCombat
from foursouls.model.phase import Phase
from foursouls.model.target import MonsterTarget, PlayerTarget, StackItemTarget

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game

# Standard shop cost in cents (base game: one coin = 10 cents)
TREASURE_COST = 10


def legal_commands(game: Game) -> List[Command]:
    """
    Sprint 2 / Sprint 12 legality rules:
    - PassPriority: always legal.
    - EndTurn: legal only when phase is ACTION and the stack is empty.
    - PlayLoot(card_ref): one entry per card in the active player's hand when
        phase is ACTION, stack is empty, and loot quota not exhausted.
    - ActivateCharacterAbility: legal whenever the priority holder's character
        is untapped, regardless of phase or stack state (Sprint 12).
    """
    if game.game_over:
        return []

    state = game.state
    stack = game.stack

    cmds: List[Command] = [PassPriority()]

    # EndTurn is legal in ACTION (normal) or END (after active-player death)
    if state.phase in (Phase.ACTION, Phase.END) and stack.empty():
        cmds.append(EndTurn())

    # ActivateCharacterAbility: legal for the priority holder whenever their
    # character is untapped — no phase or stack restriction (Sprint 12, R12.2).
    priority_holder = state.get_player(game.priority.current())
    char = priority_holder.character
    if char is not None and not char.is_tapped:
        cmds.append(ActivateCharacterAbility())

    if state.phase == Phase.ACTION:
        active = state.get_player(state.active_player_id)
        flags = state.turn_flags
        holder_id = game.priority.current()

        # PlayLoot and ActivateItem are instant-speed: legal whenever the
        # priority holder has priority during ACTION, stack state irrelevant.

        def _loot_play_cmds(hand: list, card_ref: object) -> list:
            """Return PlayLoot commands for one card_ref, covering all valid targets."""
            from foursouls.model.refs import CardRef as _CardRef
            ref = card_ref  # type: ignore[assignment]
            card_id = ref.card_id
            plays: list = []
            if card_id is None or not requires_target(card_id):
                plays.append(PlayLoot(card_ref=ref))
                return plays
            # Player targets
            if not allows_stack_target(card_id):
                for pid in state.turn_order:
                    plays.append(PlayLoot(card_ref=ref, target=PlayerTarget(player_id=pid)))
            # Monster targets
            if allows_monster_target(card_id) and game.zones is not None:
                for idx in game.zones.monster_slots.filled_indices():
                    monster = game.zones.monster_slots.get(idx)
                    if monster is not None and not monster.is_event:
                        plays.append(PlayLoot(card_ref=ref, target=MonsterTarget(slot_index=idx)))
            # Stack item targets (Butter Bean)
            if allows_stack_target(card_id):
                for item in game.stack._items:
                    plays.append(PlayLoot(card_ref=ref, target=StackItemTarget(stack_id=item.stack_id)))
            return plays

        # Active player's on-turn loot plays.
        if flags.loot_plays_used < flags.loot_plays_allowed:
            for card_ref in active.hand:
                cmds.extend(_loot_play_cmds(active.hand, card_ref))

        # Off-turn loot plays granted to the priority holder (e.g. opponent
        # tapped their character on this player's turn).
        if holder_id != state.active_player_id:
            holder_extra = flags.extra_loot_plays.get(str(holder_id), 0)
            if holder_extra > 0:
                holder = state.get_player(holder_id)
                for card_ref in holder.hand:
                    cmds.extend(_loot_play_cmds(holder.hand, card_ref))

        # ActivateItem: instant-speed, legal regardless of stack state.
        if game.zones is not None:
            for item in active.items:
                if item.is_tapped or item.card_ref.card_id is None:
                    continue
                defn = TREASURE_REGISTRY.get(item.card_ref.card_id)
                if defn is None or defn.make_tap_effect is None:
                    continue
                iid = item.card_ref.instance_id
                ttype = defn.tap_target_type
                if ttype == "player_or_monster":
                    for pid in state.turn_order:
                        cmds.append(ActivateItem(instance_id=iid, target=PlayerTarget(player_id=pid)))
                    for idx in game.zones.monster_slots.filled_indices():
                        monster = game.zones.monster_slots.get(idx)
                        if monster is not None and not monster.is_event:
                            cmds.append(ActivateItem(instance_id=iid, target=MonsterTarget(slot_index=idx)))
                elif ttype == "player":
                    for pid in state.turn_order:
                        cmds.append(ActivateItem(instance_id=iid, target=PlayerTarget(player_id=pid)))
                else:
                    cmds.append(ActivateItem(instance_id=iid))

        # The remaining actions require a clear stack.
        if stack.empty():
            if not flags.purchase_used and game.zones is not None:
                for idx in game.zones.shop_slots.filled_indices():
                    if active.cents >= TREASURE_COST:
                        cmds.append(BuyShop(slot_index=idx))

            # AttackMonster: one entry per occupied non-event monster slot.
            # Also requires: attack not yet used this turn, no combat already active,
            # and the monster must be alive (0 HP monsters die automatically before
            # any player receives priority — they should never be attack targets).
            if not flags.attack_used and game.zones is not None and game.combat is None:
                for idx in game.zones.monster_slots.filled_indices():
                    monster = game.zones.monster_slots.get(idx)
                    if monster is not None and not monster.is_event and monster.is_alive():
                        cmds.append(AttackMonster(slot_index=idx))

            # RollCombat: legal only while combat is active.
            if game.combat is not None and game.combat.is_active:
                cmds.append(RollCombat())

    return cmds
