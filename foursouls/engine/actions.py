"""
Legal-action query API.

Usage::

    from foursouls.engine.actions import get_legal_actions

    actions = get_legal_actions(game)
    for a in actions:
        print(a.key, "-", a.description)

    # The user picks one; submit the ready-made command:
    game.step(actions[chosen_index].command)

The engine remains the single source of truth for what is legal.
``get_legal_actions`` delegates directly to ``game.legal_commands()`` and
adds display context — it never re-implements legality logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

from foursouls.model.commands import (
    ActivateCharacterAbility,
    AttackMonster,
    BuyShop,
    Command,
    EndTurn,
    PassPriority,
    PlayLoot,
    RollCombat,
)
from foursouls.rulesets.common.legality import TREASURE_COST

if TYPE_CHECKING:
    from foursouls.engine.game_loop import Game


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class LegalAction:
    """
    A fully-resolved legal action the active player may take right now.

    Fields
    ------
    key
        Short stable identifier for CLI selection, e.g. ``"pass"``,
        ``"play:LOOT_COIN_1:i3"``, ``"attack:0"``.
    kind
        The command type; mirrors ``command.kind``.
    description
        Human-readable sentence a UI can display verbatim.
    command
        The fully constructed command.  Submit directly to ``game.step()``.
    metadata
        Supplementary display data (card names, HP, costs …).  The CLI should
        render these; the engine does not guarantee which keys are present for
        every kind, but the documented keys below are always set when relevant.

        Common keys by kind:
        - ``PLAY_LOOT``   → card_id, card_name, instance_id
        - ``BUY_SHOP``    → slot_index, item_id, item_name, cost
        - ``ATTACK_MONSTER`` → slot_index, monster_id, monster_name,
                               monster_hp, monster_evade
        - ``ROLL_COMBAT`` → monster_id, monster_name, monster_hp,
                            monster_evade, attacker_hp
        - ``ACTIVATE_CHARACTER_ABILITY`` → character_card_id, character_name
    """
    key: str
    kind: str
    description: str
    command: Command
    metadata: Dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def get_legal_actions(game: Game) -> List[LegalAction]:
    """
    Return all legal actions for the current active player, in the order the
    engine generates them.

    Never re-implements legality — delegates entirely to
    ``game.legal_commands()`` then enriches each command with display context
    drawn from the current game state and zones.
    """
    result: List[LegalAction] = []
    for cmd in game.legal_commands():
        result.append(_build_action(game, cmd))
    return result


# ---------------------------------------------------------------------------
# Internal builders — one per command type
# ---------------------------------------------------------------------------

def _build_action(game: Game, cmd: Command) -> LegalAction:
    if isinstance(cmd, PassPriority):
        return _pass(game, cmd)
    if isinstance(cmd, EndTurn):
        return _end_turn(cmd)
    if isinstance(cmd, PlayLoot):
        return _play_loot(cmd)
    if isinstance(cmd, ActivateCharacterAbility):
        return _activate_character(game, cmd)
    if isinstance(cmd, BuyShop):
        return _buy_shop(game, cmd)
    if isinstance(cmd, AttackMonster):
        return _attack_monster(game, cmd)
    if isinstance(cmd, RollCombat):
        return _roll_combat(game, cmd)
    # Fallback for unknown future commands — still usable, just sparse
    return LegalAction(
        key=cmd.kind.lower(),
        kind=cmd.kind,
        description=cmd.kind.replace("_", " ").title(),
        command=cmd,
    )


def _pass(game: Game, cmd: PassPriority) -> LegalAction:
    from foursouls.model.phase import Phase
    if game.state.phase == Phase.START and not game.stack.empty():
        description = "Pass (let draw resolve)"
    elif not game.stack.empty():
        description = "Pass (let stack resolve)"
    else:
        description = "Pass priority"
    return LegalAction(
        key="pass",
        kind=cmd.kind,
        description=description,
        command=cmd,
    )


def _end_turn(cmd: EndTurn) -> LegalAction:
    return LegalAction(
        key="end_turn",
        kind=cmd.kind,
        description="End turn",
        command=cmd,
    )


def _play_loot(cmd: PlayLoot) -> LegalAction:
    from foursouls.cli.render import pretty_name
    card_id = str(cmd.card_ref.card_id) if cmd.card_ref.card_id else "unknown"
    instance_id = str(cmd.card_ref.instance_id)
    display_name = pretty_name(card_id)
    return LegalAction(
        key=f"play:{card_id}:{instance_id}",
        kind=cmd.kind,
        description=f"Play {display_name} from hand",
        command=cmd,
        metadata={
            "card_id": card_id,
            "card_name": display_name,
            "instance_id": instance_id,
        },
    )


def _activate_character(game: Game, cmd: ActivateCharacterAbility) -> LegalAction:
    from foursouls.cli.render import pretty_name
    acting_id = game.priority.current()
    character = game.state.get_player(acting_id).character
    char_card_id: Optional[str] = None
    if character is not None and character.card_ref.card_id is not None:
        char_card_id = str(character.card_ref.card_id)
    char_name = pretty_name(char_card_id)
    return LegalAction(
        key="activate_character",
        kind=cmd.kind,
        description=f"Tap {char_name} (+1 loot play this turn)",
        command=cmd,
        metadata={
            "character_card_id": char_card_id,
            "character_name": char_name,
        },
    )


def _buy_shop(game: Game, cmd: BuyShop) -> LegalAction:
    item_name = "unknown"
    item_id: Optional[str] = None
    if game.zones is not None:
        card_ref = game.zones.shop_slots.get(cmd.slot_index)
        if card_ref is not None and card_ref.card_id is not None:
            item_id = str(card_ref.card_id)
            item_name = item_id
    return LegalAction(
        key=f"buy:{cmd.slot_index}",
        kind=cmd.kind,
        description=f"Buy {item_name} from shop slot {cmd.slot_index} ({TREASURE_COST}\u00a2)",
        command=cmd,
        metadata={
            "slot_index": cmd.slot_index,
            "item_id": item_id,
            "item_name": item_name,
            "cost": TREASURE_COST,
        },
    )


def _attack_monster(game: Game, cmd: AttackMonster) -> LegalAction:
    monster_name = "unknown"
    monster_id: Optional[str] = None
    monster_hp = 0
    monster_evade = 0
    if game.zones is not None:
        monster = game.zones.monster_slots.get(cmd.slot_index)
        if monster is not None:
            if monster.card_ref.card_id is not None:
                monster_id = str(monster.card_ref.card_id)
                monster_name = monster_id
            monster_hp = monster.current_hp
            monster_evade = monster.evade
    return LegalAction(
        key=f"attack:{cmd.slot_index}",
        kind=cmd.kind,
        description=(
            f"Attack {monster_name} in slot {cmd.slot_index} "
            f"(HP: {monster_hp}, evade: {monster_evade})"
        ),
        command=cmd,
        metadata={
            "slot_index": cmd.slot_index,
            "monster_id": monster_id,
            "monster_name": monster_name,
            "monster_hp": monster_hp,
            "monster_evade": monster_evade,
        },
    )


def _roll_combat(game: Game, cmd: RollCombat) -> LegalAction:
    monster_name = "unknown"
    monster_id: Optional[str] = None
    monster_hp = 0
    monster_evade = 0
    attacker_hp = 0
    if game.combat is not None and game.zones is not None:
        monster = game.zones.monster_slots.get(game.combat.defender_slot)
        if monster is not None:
            if monster.card_ref.card_id is not None:
                monster_id = str(monster.card_ref.card_id)
                monster_name = monster_id
            monster_hp = monster.current_hp
            monster_evade = monster.evade
        attacker = game.state.get_player(game.combat.attacker_id)
        attacker_hp = attacker.hp
    return LegalAction(
        key="roll_combat",
        kind=cmd.kind,
        description=(
            f"Roll for combat vs {monster_name} "
            f"(monster HP: {monster_hp}, evade: {monster_evade}, "
            f"your HP: {attacker_hp})"
        ),
        command=cmd,
        metadata={
            "monster_id": monster_id,
            "monster_name": monster_name,
            "monster_hp": monster_hp,
            "monster_evade": monster_evade,
            "attacker_hp": attacker_hp,
        },
    )
