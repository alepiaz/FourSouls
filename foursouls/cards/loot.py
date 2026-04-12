from __future__ import annotations

from typing import Any, Optional

from foursouls.model.refs import CardId, PlayerId
from foursouls.model.effects import Effect
from foursouls.model.target import AnyTarget, MonsterTarget, PlayerTarget
from foursouls.rulesets.common.effects import (
    AllPlayersDrawLootEffect,
    AllPlayersGainCentsEffect,
    AllPlayersTakeDamageEffect,
    DealDamageEffect,
    DealDamageToMonsterEffect,
    GainCentsEffect,
    LootRollEffect,
    PreventDamageEffect,
)

# ── Card ID constants ─────────────────────────────────────────────────────────

LOOT_COIN_1 = CardId("LOOT_COIN_1")
LOOT_COIN_2 = CardId("LOOT_COIN_2")
LOOT_COIN_3 = CardId("LOOT_COIN_3")
BOMB_BANG = CardId("BOMB!")
GOLD_BOMB_BANG_BANG = CardId("GOLD_BOMB!!")
SOUL_HEART = CardId("SOUL_HEART")
BLANK_RUNE = CardId("BLANK_RUNE")

_COIN_IDS = {LOOT_COIN_1, LOOT_COIN_2, LOOT_COIN_3}
_BOMB_DAMAGE = {BOMB_BANG: 1, GOLD_BOMB_BANG_BANG: 3}
# Cards that require a target; bombs accept player or monster, Soul Heart player only
_TARGETED_LOOT_IDS = {BOMB_BANG, GOLD_BOMB_BANG_BANG, SOUL_HEART}
_MONSTER_TARGETABLE = {BOMB_BANG, GOLD_BOMB_BANG_BANG}


def requires_target(card_id: CardId) -> bool:
    return card_id in _TARGETED_LOOT_IDS


def allows_monster_target(card_id: CardId) -> bool:
    return card_id in _MONSTER_TARGETABLE


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
        if target is None or not isinstance(target, PlayerTarget):
            raise ValueError(f"{card_id!r} requires a PlayerTarget")
        return PreventDamageEffect(player_id=target.player_id, amount=1)
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
    raise ValueError(f"Unknown loot card_id: {card_id!r}")
