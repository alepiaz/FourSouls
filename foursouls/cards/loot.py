from __future__ import annotations

from typing import Any, Optional

from foursouls.model.refs import CardId, PlayerId
from foursouls.model.effects import Effect
from foursouls.model.target import AnyTarget, MonsterTarget, PlayerTarget, StackItemTarget
from foursouls.rulesets.common.effects import (
    AllPlayersDrawLootEffect,
    AllPlayersGainCentsEffect,
    AllPlayersTakeDamageEffect,
    CancelStackItemEffect,
    DealDamageEffect,
    DealDamageToMonsterEffect,
    GainCentsEffect,
    LootRollEffect,
    PreventDamageEffect,
    PreventDamageToMonsterEffect,
)

# ── Card ID constants ─────────────────────────────────────────────────────────

LOOT_COIN_1 = CardId("LOOT_COIN_1")
LOOT_COIN_2 = CardId("LOOT_COIN_2")
LOOT_COIN_3 = CardId("LOOT_COIN_3")
BOMB_BANG = CardId("BOMB!")
GOLD_BOMB_BANG_BANG = CardId("GOLD_BOMB!!")
SOUL_HEART = CardId("SOUL_HEART")
BLANK_RUNE = CardId("BLANK_RUNE")
BUTTER_BEAN = CardId("BUTTER_BEAN")

_COIN_IDS = {LOOT_COIN_1, LOOT_COIN_2, LOOT_COIN_3}
_BOMB_DAMAGE = {BOMB_BANG: 1, GOLD_BOMB_BANG_BANG: 3}
# Cards that require a target
_TARGETED_LOOT_IDS = {BOMB_BANG, GOLD_BOMB_BANG_BANG, SOUL_HEART, BUTTER_BEAN}
# Subset of targeted cards that can aim at a monster slot
_MONSTER_TARGETABLE = {BOMB_BANG, GOLD_BOMB_BANG_BANG, SOUL_HEART}
# Cards that target a stack item (for the cancel mechanic)
_STACK_TARGET_LOOT_IDS = {BUTTER_BEAN}


def requires_target(card_id: CardId) -> bool:
    return card_id in _TARGETED_LOOT_IDS


def allows_monster_target(card_id: CardId) -> bool:
    return card_id in _MONSTER_TARGETABLE


def allows_stack_target(card_id: CardId) -> bool:
    return card_id in _STACK_TARGET_LOOT_IDS


# ── Effect factory ────────────────────────────────────────────────────────────

def make_loot_effect(
    card_id: CardId,
    controller_id: PlayerId,
    *,
    target: Optional[AnyTarget] = None,
    monster_slots: Any = None,
    rng: Any = None,
    loot_deck: Any = None,
    log: Any = None,
    stack: Any = None,
) -> Effect:
    """Return the resolved effect for a loot card played by controller_id."""
    if card_id in _COIN_IDS:
        return GainCentsEffect(player_id=controller_id, amount=1)
    if card_id == BLANK_RUNE:
        if rng is None:
            raise ValueError("BLANK_RUNE requires rng")
        if loot_deck is None:
            raise ValueError("BLANK_RUNE requires loot_deck")
        branches = {
            1: AllPlayersGainCentsEffect(amount=1),
            2: AllPlayersDrawLootEffect(count=2, loot_deck=loot_deck, log=log),
            3: AllPlayersTakeDamageEffect(amount=3),
            4: AllPlayersGainCentsEffect(amount=4),
            5: AllPlayersDrawLootEffect(count=5, loot_deck=loot_deck, log=log),
            6: AllPlayersGainCentsEffect(amount=6),
        }
        return LootRollEffect(branches=branches, rng=rng)
    if card_id == SOUL_HEART:
        if isinstance(target, PlayerTarget):
            return PreventDamageEffect(player_id=target.player_id, amount=1)
        if isinstance(target, MonsterTarget):
            if monster_slots is None:
                raise ValueError(f"{card_id!r} + MonsterTarget requires monster_slots")
            return PreventDamageToMonsterEffect(
                slot_index=target.slot_index, amount=1, monster_slots=monster_slots
            )
        raise ValueError(f"{card_id!r} requires a PlayerTarget or MonsterTarget")
    if card_id in _BOMB_DAMAGE:
        amount = _BOMB_DAMAGE[card_id]
        if target is None:
            raise ValueError(f"{card_id!r} requires a target")
        if isinstance(target, PlayerTarget):
            return DealDamageEffect(player_id=target.player_id, amount=amount, damage_type="ability")
        else:  # MonsterTarget
            if monster_slots is None:
                raise ValueError(f"{card_id!r} with MonsterTarget requires monster_slots")
            return DealDamageToMonsterEffect(
                slot_index=target.slot_index,
                amount=amount,
                monster_slots=monster_slots,
            )
    if card_id == BUTTER_BEAN:
        if not isinstance(target, StackItemTarget):
            raise ValueError(f"{card_id!r} requires a StackItemTarget")
        if stack is None:
            raise ValueError(f"{card_id!r} requires stack")
        return CancelStackItemEffect(target_stack_id=target.stack_id, stack=stack, log=log)
    raise ValueError(f"Unknown loot card_id: {card_id!r}")
