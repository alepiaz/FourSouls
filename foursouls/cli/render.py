"""
Pure display functions for the FourSouls CLI.

No I/O — every public function returns a string.  The controller layer is
responsible for printing and for gathering user input.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from foursouls.engine.actions import LegalAction
    from foursouls.engine.events import Event
    from foursouls.engine.game_loop import Game

_WIDTH = 72


# ─── Card name pretty-printing ───────────────────────────────────────────────

_CARD_NAMES: dict[str, str] = {
    # Loot
    "LOOT_COIN_1": "Loot Coin",
    "LOOT_COIN_2": "2 Loot Coins",
    "LOOT_COIN_3": "3 Loot Coins",
    "BOMB!":       "Bomb!",
    "GOLD_BOMB!!": "Gold Bomb!!",
    "SOUL_HEART":  "Soul Heart",
    "BLANK_RUNE":  "Blank Rune",
    # Event cards
    "CURSED_CHEST":         "Cursed Chest",
    "WE_NEED_TO_GO_DEEPER": "We Need To Go Deeper!",
    # Monsters
    "FLY":         "Fly",
    "GAPER":       "Gaper",
    "SPIDER":      "Spider",
    "HORF":        "Horf",
    # Characters
    "ISAAC":       "Isaac",
    "MAGDALENE":   "Magdalene",
    "CAIN":        "Cain",
    "EVE":         "Eve",
}


def pretty_name(card_id_str: Optional[str]) -> str:
    """Convert a raw CardId string to a human-readable display name."""
    if not card_id_str:
        return "?"
    return _CARD_NAMES.get(card_id_str, card_id_str.replace("_", " ").title())


# ─── Layout helpers ───────────────────────────────────────────────────────────

def _sep(char: str = "-") -> str:
    return char * _WIDTH


# ─── Board sections ───────────────────────────────────────────────────────────

def render_header(game: "Game") -> str:
    """One-line turn/phase/priority summary."""
    active   = game.state.active_player_id
    priority = game.priority.current()
    phase    = game.state.phase.value
    turn     = game.state.turn_number
    return (
        f"Turn {turn}  |  Phase: {phase:<6}  |  "
        f"Active: {active}  |  Priority: {priority}"
    )


def render_player_row(game: "Game", player_id: str) -> str:
    """Compact one-line summary for a single player."""
    player = game.state.get_player(player_id)
    souls  = len(player.souls)
    marker = ">" if player_id == game.state.active_player_id else " "

    char_part = ""
    if player.character is not None:
        cid       = player.character.card_ref.card_id
        char_name = pretty_name(str(cid) if cid else None)
        tap_state = " [TAPPED]" if player.character.is_tapped else " [tap: +1 loot]"
        char_part = f"  Char: {char_name}{tap_state}"

    item_names = [
        pretty_name(str(r.card_ref.card_id) if r.card_ref.card_id else None)
        for r in player.items
    ]
    items_part = ("  Items: " + ", ".join(item_names)) if item_names else ""

    return (
        f"{marker} {player_id:<6}"
        f"HP: {player.hp}/{player.max_hp}  "
        f"Coins: {player.cents}c  "
        f"Souls: {souls}  "
        f"Hand: {len(player.hand)}"
        f"{char_part}{items_part}"
    )


def render_hand(game: "Game") -> str:
    """Active player's hand as a single line with loot-plays remaining."""
    player = game.state.get_player(game.state.active_player_id)
    flags  = game.state.turn_flags
    plays_left = flags.loot_plays_allowed - flags.loot_plays_used
    play_label = f"  ({plays_left} loot play{'s' if plays_left != 1 else ''} remaining)"
    if not player.hand:
        return f"Hand: (empty){play_label}"
    cards = "  ".join(
        f"[{i}] {pretty_name(str(r.card_id) if r.card_id else None)}"
        for i, r in enumerate(player.hand)
    )
    return f"Hand: {cards}{play_label}"


def render_monsters(game: "Game") -> str:
    """Monster zone — one line per slot."""
    if game.zones is None:
        return "Monsters: (no zones)"
    lines = ["Monsters:"]
    for idx in range(game.zones.monster_slots.size):
        m = game.zones.monster_slots.get(idx)
        if m is None:
            lines.append(f"  [{idx}] ---")
        else:
            name   = pretty_name(str(m.card_ref.card_id) if m.card_ref.card_id else None)
            soul   = "  [soul]" if m.has_soul else ""
            reward = f"  +{m.reward_coin}c" if m.reward_coin else ""
            lines.append(
                f"  [{idx}] {name:<12} HP {m.current_hp}/{m.base_hp}"
                f"  Evade {m.evade}{reward}{soul}"
            )
    return "\n".join(lines)


def render_shop(game: "Game") -> str:
    """Shop zone — one line per slot."""
    if game.zones is None:
        return "Shop: (no zones)"
    from foursouls.rulesets.common.legality import TREASURE_COST
    lines = ["Shop:"]
    for idx in range(game.zones.shop_slots.size):
        card = game.zones.shop_slots.get(idx)
        if card is None:
            lines.append(f"  [{idx}] ---")
        else:
            name = pretty_name(str(card.card_id) if card.card_id else None)
            lines.append(f"  [{idx}] {name}  ({TREASURE_COST}c)")
    return "\n".join(lines)


def render_combat(game: "Game") -> str:
    """Active combat callout, or empty string when not in combat."""
    if game.combat is None:
        return ""
    c = game.combat
    if game.zones is not None:
        m = game.zones.monster_slots.get(c.defender_slot)
    else:
        m = None
    monster_name = pretty_name(
        str(m.card_ref.card_id) if m and m.card_ref.card_id else None
    )
    hp_str = f"  HP {m.current_hp}/{m.base_hp}" if m else ""
    return (
        f"  !! COMBAT: {c.attacker_id} vs {monster_name}"
        f" (slot {c.defender_slot}){hp_str}"
    )


def render_stack(game: "Game") -> str:
    """Stack state summary."""
    if game.stack.empty():
        return "Stack: (empty)"
    top   = game.stack.top()
    label = (top.label if top and top.label else "effect")
    return f"Stack: {len(game.stack)} item(s), top: {label}"


def render_actions(actions: "Sequence[LegalAction]") -> str:
    """Numbered action menu."""
    lines = ["Actions:"]
    for i, a in enumerate(actions):
        lines.append(f"  [{i}] {a.description}")
    lines.append("  [q] Quit")
    return "\n".join(lines)


# ─── Event narrative ─────────────────────────────────────────────────────────

def render_event(event: "Event") -> str:
    """Format one engine event as a short narrative line."""
    from foursouls.engine.events import (
        AllPlayersPassed,
        AttackDeclared,
        CardDrawn,
        CardDiscarded,
        CoinsGained,
        CoinsSpent,
        CombatEntered,
        CombatRollResult,
        DamageDealt,
        EffectFizzled,
        GameWon,
        ItemActivated,
        LootPlayed,
        MonsterDied,
        PhaseChanged,
        PlayerDied,
        PriorityPassed,
        ShopBought,
        SoulGranted,
        StackItemPushed,
        StackItemResolved,
        TurnEnded,
        TurnStarted,
    )
    e = event

    if isinstance(e, TurnStarted):
        return f"  > Turn {e.turn_number} begins for {e.player_id}"
    if isinstance(e, TurnEnded):
        return f"  > {e.player_id} ends their turn"
    if isinstance(e, PhaseChanged):
        return f"  > Phase: {e.old_phase.value} -> {e.new_phase.value}"
    if isinstance(e, PriorityPassed):
        return f"  > {e.player_id} passes priority"
    if isinstance(e, AllPlayersPassed):
        return "  > All players passed"
    if isinstance(e, StackItemPushed):
        label = e.label or "effect"
        return f"  > [{label}] pushed to stack"
    if isinstance(e, StackItemResolved):
        label = e.label or "effect"
        if label == "GrantExtraLootPlay":
            return "  > +1 loot play granted"
        return f"  > [{label}] resolves"
    if isinstance(e, EffectFizzled):
        label = e.label or "effect"
        return f"  > [{label}] fizzles ({e.reason})"
    if isinstance(e, LootPlayed):
        return f"  > {e.player_id} plays {e.card_name}"
    if isinstance(e, CardDrawn):
        return f"  > {e.player_id} draws a card"
    if isinstance(e, CardDiscarded):
        return f"  > {e.player_id} discards {e.card_name}"
    if isinstance(e, CoinsGained):
        return f"  > {e.player_id} gains {e.cents}c"
    if isinstance(e, CoinsSpent):
        return f"  > {e.player_id} spends {e.amount}c"
    if isinstance(e, ShopBought):
        return f"  > {e.player_id} buys {e.item_name} ({e.cost}c)"
    if isinstance(e, ItemActivated):
        if e.source == "character:tap_ability":
            return f"  > {e.player_id} taps character (+1 loot play queued)"
        return f"  > {e.player_id} activates ability"
    if isinstance(e, AttackDeclared):
        return f"  > {e.player_id} attacks {e.monster_name}!"
    if isinstance(e, CombatEntered):
        return (
            f"  > Combat: {e.attacker_id} vs {e.monster_name}"
            f" (HP {e.monster_hp}, evade {e.monster_evade})"
        )
    if isinstance(e, CombatRollResult):
        result = "HIT!" if e.is_hit else "miss"
        return f"  > Rolled {e.roll} vs evade {e.evade} -- {result}"
    if isinstance(e, DamageDealt):
        if e.target_player_id:
            return f"  > {e.target_player_id} takes {e.amount} damage"
        if e.target_monster_slot is not None:
            return f"  > Monster (slot {e.target_monster_slot}) takes {e.amount} damage"
        return f"  > {e.amount} damage dealt"
    if isinstance(e, MonsterDied):
        soul_str   = "  [soul claimed!]" if e.had_soul else ""
        reward_str = f"  +{e.reward_coin}c" if e.reward_coin else ""
        return f"  > {e.monster_name} dies!{reward_str}{soul_str}"
    if isinstance(e, SoulGranted):
        return f"  > {e.player_id} claims a soul!"
    if isinstance(e, PlayerDied):
        return f"  > {e.player_id} is killed by {e.monster_name}!"
    if isinstance(e, GameWon):
        return f"  *** {e.player_id} WINS with {e.soul_count} soul(s)! ***"

    # Fallback for any event type not explicitly handled
    return f"  > {e.name}"


def render_events(events: "Sequence[Event]") -> str:
    """Format a sequence of events as a multi-line narrative."""
    if not events:
        return ""
    return "\n".join(render_event(e) for e in events)


# ─── Full board ───────────────────────────────────────────────────────────────

def render_board(game: "Game", actions: "Sequence[LegalAction]") -> str:
    """Assemble the complete board display as a single string."""
    lines: list[str] = []

    lines.append(_sep("="))
    lines.append(render_header(game))
    lines.append(_sep())

    for pid in game.state.turn_order:
        lines.append(render_player_row(game, pid))

    lines.append("")
    lines.append(render_hand(game))

    lines.append("")
    lines.append(render_monsters(game))

    lines.append("")
    lines.append(render_shop(game))

    combat_str = render_combat(game)
    if combat_str:
        lines.append("")
        lines.append(combat_str)

    lines.append("")
    lines.append(render_stack(game))

    lines.append("")
    lines.append(_sep("-"))
    lines.append(render_actions(actions))
    lines.append(_sep("-"))

    return "\n".join(lines)
