from __future__ import annotations

from foursouls.model.refs import CardId, PlayerId
from foursouls.model.effects import Effect
from foursouls.rulesets.common.effects import DealDamageEffect, GainCentsEffect

# ── Card ID constants ─────────────────────────────────────────────────────────

LOOT_COIN_1 = CardId("LOOT_COIN_1")
LOOT_COIN_2 = CardId("LOOT_COIN_2")
LOOT_COIN_3 = CardId("LOOT_COIN_3")
BOMB = CardId("BOMB")

_COIN_IDS = {LOOT_COIN_1, LOOT_COIN_2, LOOT_COIN_3}

# ── Effect factory ────────────────────────────────────────────────────────────

def make_loot_effect(card_id: CardId, controller_id: PlayerId) -> Effect:
    """Return the resolved effect for a loot card played by controller_id."""
    if card_id in _COIN_IDS:
        return GainCentsEffect(player_id=controller_id, amount=1)
    if card_id == BOMB:
        return DealDamageEffect(player_id=controller_id, amount=1)
    raise ValueError(f"Unknown loot card_id: {card_id!r}")
