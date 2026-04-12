from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Dict, Optional

from foursouls.model.refs import CardId

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game
    from foursouls.model.effects import Effect
    from foursouls.model.target import AnyTarget


@dataclass(slots=True)
class TreasureDef:
    """Definition of a treasure card.

    Instances are singletons (one per card type); runtime state lives in
    ItemInPlay. All callable hooks are optional and default to None (no-op).

    recharge_on controls when tapped copies untap each turn:
      "start_of_turn"  — default
      "end_of_turn"    — e.g. The D6, Yum Heart, Sleight Of Hand, The Curse

    is_one_use=True: the item is destroyed when its tap effect resolves
      (e.g. Mama Mega).

    eternal=True: item cannot be destroyed or discarded (starting Eternals).

    is_guppy=True: counts toward the 2-Guppy threshold for Soul of Guppy.

    tap_target_type controls how legality emits ActivateItem commands:
      None              — no target; emit a single ActivateItem
      "player"          — emit one ActivateItem per player
      "player_or_monster" — emit one per player + one per occupied non-event slot

    make_tap_effect(target, game) → Effect: produces the Effect pushed onto
      the stack when the item is activated. None means the tap is a no-op stub.
    """

    card_id: CardId
    name: str
    recharge_on: str = "start_of_turn"
    is_one_use: bool = False
    eternal: bool = False
    is_guppy: bool = False

    # Tap effect description (plain text; used for display / testing).
    tap_effect_description: Optional[str] = None

    # Targeting contract for legality generation (see docstring above).
    tap_target_type: Optional[str] = field(default=None, compare=False)

    # Factory: (target, game) → Effect; None = no-op stub.
    make_tap_effect: Optional[Callable] = field(default=None, compare=False)

    # Lifecycle hooks — all are None by default (no effect).
    # on_enters_play(game, owner_id) — fires when this item enters play.
    on_enters_play: Optional[Callable] = field(default=None, compare=False)
    # on_start_of_turn(game) — fires at the start of each of the owner's turns.
    on_start_of_turn: Optional[Callable] = field(default=None, compare=False)
    # on_roll(roll, owner, game) — fires after any roll; used by Eye Of Greed.
    on_roll: Optional[Callable] = field(default=None, compare=False)
    # on_character_tap(game) — fires when the owner uses ActivateCharacterAbility.
    on_character_tap: Optional[Callable] = field(default=None, compare=False)

    # Starting counters written onto ItemInPlay at entry.
    starting_counters: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Card-ID constants
# ---------------------------------------------------------------------------

DRY_BABY        = CardId("DRY_BABY")
EYE_OF_GREED    = CardId("EYE_OF_GREED")
THE_DEAD_CAT    = CardId("THE_DEAD_CAT")
MAMA_MEGA       = CardId("MAMA_MEGA")
TECH_X          = CardId("TECH_X")
MAGIC_MUSHROOM  = CardId("MAGIC_MUSHROOM")
MEAT_BANG       = CardId("MEAT!")
LUCKY_FOOT      = CardId("LUCKY_FOOT")
LIL_BATTERY     = CardId("LIL_BATTERY")

# Starting Eternals
THE_D6          = CardId("THE_D6")
YUM_HEART       = CardId("YUM_HEART")
SLEIGHT_OF_HAND = CardId("SLEIGHT_OF_HAND")
THE_CURSE       = CardId("THE_CURSE")


# ---------------------------------------------------------------------------
# Card definitions
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Passive helpers (called from on_enters_play)
# ---------------------------------------------------------------------------

def _dry_baby_enter(game: Game, player_id: object) -> None:
    from foursouls.model.refs import PlayerId
    game.state.get_player(player_id).damage_cap = 1  # type: ignore[arg-type]


def _meat_enter(game: Game, player_id: object) -> None:
    from foursouls.model.refs import PlayerId
    game.state.get_player(player_id).attack_bonus += 1  # type: ignore[arg-type]


DRY_BABY_DEF = TreasureDef(
    card_id=DRY_BABY,
    name="Dry Baby",
    on_enters_play=_dry_baby_enter,
    tap_effect_description=None,  # passive; no tap effect
)

MEAT_BANG_DEF = TreasureDef(
    card_id=MEAT_BANG,
    name="Meat!",
    on_enters_play=_meat_enter,
    tap_effect_description=None,  # passive; no tap effect
)

THE_D6_DEF = TreasureDef(
    card_id=THE_D6,
    name="The D6",
    eternal=True,
    recharge_on="end_of_turn",
    make_tap_effect=None,   # stub — full reroll mechanic in Sprint 16
    tap_effect_description="Choose a dice roll. Its controller rerolls it. (Stub — Sprint 16)",
)

LUCKY_FOOT_DEF = TreasureDef(
    card_id=LUCKY_FOOT,
    name="Lucky Foot",
    make_tap_effect=None,   # stub — full non-attack-roll bonus in Sprint 16
    tap_effect_description="Add up to 2 to a non-attack roll. (Stub — Sprint 16)",
)


def _mama_mega_effect(target: object, game: Game) -> Effect:
    from foursouls.rulesets.common.effects import AoDamageEffect
    return AoDamageEffect(amount=3, monster_slots=game.zones.monster_slots)


MAMA_MEGA_DEF = TreasureDef(
    card_id=MAMA_MEGA,
    name="Mama Mega",
    is_one_use=True,
    tap_target_type=None,
    make_tap_effect=_mama_mega_effect,
    tap_effect_description="Destroy this. Deal 3 damage to each monster and player.",
)


def _yum_heart_effect(target: AnyTarget, game: Game) -> Effect:
    from foursouls.model.target import PlayerTarget, MonsterTarget
    from foursouls.rulesets.common.effects import PreventDamageEffect, PreventDamageToMonsterEffect
    if isinstance(target, PlayerTarget):
        return PreventDamageEffect(player_id=target.player_id, amount=1)
    elif isinstance(target, MonsterTarget):
        return PreventDamageToMonsterEffect(
            slot_index=target.slot_index,
            amount=1,
            monster_slots=game.zones.monster_slots,
        )
    raise ValueError(f"Unexpected target type for Yum Heart: {type(target)}")


YUM_HEART_DEF = TreasureDef(
    card_id=YUM_HEART,
    name="Yum Heart",
    eternal=True,
    recharge_on="end_of_turn",
    tap_target_type="player_or_monster",
    make_tap_effect=_yum_heart_effect,
    tap_effect_description=(
        "Choose a player or monster. Prevent the next 1 damage they would take this turn."
    ),
)


SLEIGHT_OF_HAND_DEF = TreasureDef(
    card_id=SLEIGHT_OF_HAND,
    name="Sleight Of Hand",
    eternal=True,
    recharge_on="end_of_turn",
    make_tap_effect=None,   # stub — DeckTarget + auto-shuffle in R11.4
    tap_effect_description=(
        "Look at the top 5 cards of a deck. Put them back in any order. "
        "(Stub — auto-shuffle Sprint 11; full reorder Sprint 16)"
    ),
)

THE_CURSE_DEF = TreasureDef(
    card_id=THE_CURSE,
    name="The Curse",
    eternal=True,
    recharge_on="end_of_turn",
    make_tap_effect=None,   # stub — DeckTarget + discard/restore in R11.4
    on_start_of_turn=None,  # stub — auto-discard in R11.4
    tap_effect_description=(
        "Put the top card of any discard on top of its deck. "
        "(Stub — DeckTarget system in R11.4)"
    ),
)


# ---------------------------------------------------------------------------
# Registry — CardId → TreasureDef lookup used by the engine
# ---------------------------------------------------------------------------

TREASURE_REGISTRY: Dict[CardId, TreasureDef] = {
    DRY_BABY:        DRY_BABY_DEF,
    MEAT_BANG:       MEAT_BANG_DEF,
    THE_D6:          THE_D6_DEF,
    LUCKY_FOOT:      LUCKY_FOOT_DEF,
    MAMA_MEGA:       MAMA_MEGA_DEF,
    YUM_HEART:       YUM_HEART_DEF,
    SLEIGHT_OF_HAND: SLEIGHT_OF_HAND_DEF,
    THE_CURSE:       THE_CURSE_DEF,
}
