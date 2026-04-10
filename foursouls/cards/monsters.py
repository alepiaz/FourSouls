from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, TYPE_CHECKING

from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.refs import CardId, CardRef

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game
    from foursouls.model.effects import Effect

# ── Card ID constants ─────────────────────────────────────────────────────────

FLY    = CardId("FLY")
GAPER  = CardId("GAPER")
SPIDER = CardId("SPIDER")
HORF   = CardId("HORF")

# Boss card IDs
MONSTRO           = CardId("MONSTRO")            # Base Game V2
HEADLESS_HORSEMAN = CardId("HEADLESS_HORSEMAN")  # Four Souls+ V2

# Event card IDs
FEAST     = CardId("FEAST")      # positive: active player gains 5¢
PLAGUE    = CardId("PLAGUE")     # negative: active player takes 2 damage
WANDERING = CardId("WANDERING")  # neutral:  active player draws 1 loot

# ── Blueprint ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class MonsterDef:
    card_id: CardId
    base_hp: int
    evade: int
    attack: int
    has_soul: bool
    reward_coin: int = 0
    reward_loot: int = 0      # loot cards drawn by attacker on kill (e.g. Spider)
    reward_treasure: int = 0  # treasure cards drawn by attacker on kill (e.g. Headless Horseman)
    is_boss: bool = False
    is_event: bool = False
    # Callable[[Game], Effect] — not part of equality or hash
    event_effect: object = field(default=None, compare=False, hash=False)


# ── Event effect factories ─────────────────────────────────────────────────────

def _feast_effect(game: "Game") -> "Effect":
    from foursouls.rulesets.common.effects import GainCentsEffect
    return GainCentsEffect(player_id=game.state.active_player_id, amount=5)


def _plague_effect(game: "Game") -> "Effect":
    from foursouls.rulesets.common.effects import DealDamageEffect
    return DealDamageEffect(player_id=game.state.active_player_id, amount=2)


def _wandering_effect(game: "Game") -> "Effect":
    from foursouls.rulesets.common.effects import DrawLoot1Effect
    return DrawLoot1Effect(
        player_id=game.state.active_player_id,
        loot_deck=game.zones.loot_deck,
        log=game.log,
    )


# ── Registry ──────────────────────────────────────────────────────────────────

_REGISTRY: Dict[CardId, MonsterDef] = {
    FLY:    MonsterDef(card_id=FLY,    base_hp=1, evade=2, attack=1, reward_coin=1, has_soul=False),
    GAPER:  MonsterDef(card_id=GAPER,  base_hp=2, evade=4, attack=1, reward_coin=3, has_soul=False),
    SPIDER: MonsterDef(card_id=SPIDER, base_hp=1, evade=4, attack=1, reward_coin=0, has_soul=False, reward_loot=1),
    HORF:   MonsterDef(card_id=HORF,   base_hp=1, evade=4, attack=1, reward_coin=3, has_soul=False),
    # Bosses
    MONSTRO: MonsterDef(
        card_id=MONSTRO, base_hp=4, evade=4, attack=1, reward_coin=6,
        has_soul=True, is_boss=True,
    ),
    HEADLESS_HORSEMAN: MonsterDef(
        card_id=HEADLESS_HORSEMAN, base_hp=3, evade=3, attack=2, reward_coin=0,
        has_soul=True, reward_treasure=1, is_boss=True,
        # Ability (Sprint 13): first time this would die each turn, prevent death,
        # heal 2 HP, gain +1 DC and -1 ATK until end of turn.
    ),
    # Events (no stat block: base_hp/evade/attack are ignored)
    FEAST:     MonsterDef(card_id=FEAST,     base_hp=0, evade=0, attack=0, reward_coin=0, has_soul=False, is_event=True, event_effect=_feast_effect),
    PLAGUE:    MonsterDef(card_id=PLAGUE,    base_hp=0, evade=0, attack=0, reward_coin=0, has_soul=False, is_event=True, event_effect=_plague_effect),
    WANDERING: MonsterDef(card_id=WANDERING, base_hp=0, evade=0, attack=0, reward_coin=0, has_soul=False, is_event=True, event_effect=_wandering_effect),
}

# Used when a CardRef has no card_id or an unrecognised one (e.g. test stubs).
_DEFAULT = MonsterDef(
    card_id=CardId("__default__"),
    base_hp=1,
    evade=1,
    attack=1,
    reward_coin=0,
    has_soul=False,
)

# ── Lookup ────────────────────────────────────────────────────────────────────

def get_monster_def(card_id: Optional[CardId]) -> MonsterDef:
    """Return the MonsterDef for a card_id, or _DEFAULT if unknown/None."""
    if card_id is None:
        return _DEFAULT
    return _REGISTRY.get(card_id, _DEFAULT)


# ── Factory ───────────────────────────────────────────────────────────────────

def make_monster_in_play(card_ref: CardRef) -> MonsterInPlay:
    """Instantiate runtime monster state from a CardRef using the registry."""
    defn = get_monster_def(card_ref.card_id)
    return MonsterInPlay(
        card_ref=card_ref,
        base_hp=defn.base_hp,
        current_hp=defn.base_hp,
        evade=defn.evade,
        reward_coin=defn.reward_coin,
        has_soul=defn.has_soul,
        attack=defn.attack,
        reward_loot=defn.reward_loot,
        reward_treasure=defn.reward_treasure,
        is_boss=defn.is_boss,
        is_event=defn.is_event,
    )
