"""
R7.2 — Death penalty applied in resolve_player_death; DeathPenaltyPaid event.

Official rules penalty (applied automatically in priority order):
  1. Destroy 1 non-eternal item  → first non-eternal ItemInPlay in player.items, if any
  2. Discard 1 loot card          → first CardRef in player.hand, if any
  3. Lose 1¢                      → floor 0
  4. Deactivate all ↷ items       → untap character (only ↷ item in current model)

Each step degrades gracefully when there is nothing to consume (empty list / 0¢ /
untapped character).  Tests cover the full-penalty path and each empty-input edge case.
"""
from __future__ import annotations

from foursouls.engine.events import DeathPenaltyPaid, PlayerDied
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import AttackMonster, RollCombat
from foursouls.model.game_state import GameState
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ref(name: str) -> CardRef:
    return CardRef(InstanceId(name))


def _monster(evade: int = 7, hp: int = 5) -> MonsterInPlay:
    """evade=7 → always miss → player takes damage."""
    return MonsterInPlay(
        card_ref=_ref("m-0"),
        base_hp=hp,
        current_hp=hp,
        evade=evade,
        reward_coin=0,
        has_soul=False,
    )


def _game(
    *,
    player_hp: int = 1,
    cents: int = 0,
    items: list[CardRef | ItemInPlay] | None = None,
    hand: list[CardRef] | None = None,
    character_tapped: bool = False,
) -> Game:
    """
    Return a Game in ACTION phase, with combat declared against slot 0.
    evade=7 → first roll is always a miss → player_hp=1 → player dies.
    """
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=player_hp, hp=player_hp)
    p1.cents = cents
    if items is not None:
        for it in items:
            p1.items.append(it if isinstance(it, ItemInPlay) else ItemInPlay(card_ref=it))
    if hand is not None:
        p1.hand.extend(hand)

    char = ItemInPlay(card_ref=_ref("char-0"), eternal=True)
    if character_tapped:
        char.tap()
    p1.character = char

    gs = GameState.from_players([p1], active_player_id=PlayerId("P1"))
    gs.phase = Phase.ACTION

    ms: SlotsZone[MonsterInPlay] = SlotsZone(size=1)
    ms.set(0, _monster())

    zones = GameZones(
        loot_deck=DeckZone(),
        loot_discard=DiscardZone(),
        treasure_deck=DeckZone(),
        treasure_discard=DiscardZone(),
        monster_deck=DeckZone(),
        monster_discard=DiscardZone(),
        shop_slots=SlotsZone(size=1),
        monster_slots=ms,
    )
    g = Game(state=gs, zones=zones, rng=RNG(seed=0))
    g.step(AttackMonster(slot_index=0))
    return g


def _die(g: Game):
    """Roll once → miss → player_hp=1 → death. Returns the StepResult."""
    return g.step(RollCombat())


# ---------------------------------------------------------------------------
# Event ordering: PlayerDied then DeathPenaltyPaid
# ---------------------------------------------------------------------------

def test_both_events_emitted():
    result = _die(_game())
    assert any(isinstance(e, PlayerDied) for e in result.events)
    assert any(isinstance(e, DeathPenaltyPaid) for e in result.events)


def test_player_died_before_penalty():
    result = _die(_game())
    names = [type(e).__name__ for e in result.events]
    assert names.index("PlayerDied") < names.index("DeathPenaltyPaid")


# ---------------------------------------------------------------------------
# Step 1 — destroy non-eternal item
# ---------------------------------------------------------------------------

def test_item_destroyed_when_player_has_items():
    item_ref = _ref("treasure-0")
    g = _game(items=[item_ref])
    p1 = g.state.get_player(PlayerId("P1"))

    result = _die(g)

    ev = next(e for e in result.events if isinstance(e, DeathPenaltyPaid))
    assert ev.item_destroyed == item_ref
    assert not any(i.card_ref == item_ref for i in p1.items)
    assert item_ref in g.zones.treasure_discard.cards


def test_first_item_destroyed_when_multiple():
    first = _ref("treasure-0")
    second = _ref("treasure-1")
    g = _game(items=[first, second])
    p1 = g.state.get_player(PlayerId("P1"))

    _die(g)

    assert not any(i.card_ref == first for i in p1.items)
    assert any(i.card_ref == second for i in p1.items)   # only first is destroyed


def test_item_destroyed_none_when_no_items():
    result = _die(_game(items=[]))
    ev = next(e for e in result.events if isinstance(e, DeathPenaltyPaid))
    assert ev.item_destroyed is None


def test_eternal_character_not_in_destroyable_pool():
    """The character (eternal=True) lives in player.character, not player.items;
    it must never be destroyed by the death penalty."""
    g = _game(items=[])   # no non-eternal items
    p1 = g.state.get_player(PlayerId("P1"))
    char_before = p1.character

    _die(g)

    assert p1.character is char_before   # character untouched


# ---------------------------------------------------------------------------
# Step 2 — discard loot from hand
# ---------------------------------------------------------------------------

def test_loot_discarded_when_hand_nonempty():
    loot_ref = _ref("loot-0")
    g = _game(hand=[loot_ref])
    p1 = g.state.get_player(PlayerId("P1"))

    result = _die(g)

    ev = next(e for e in result.events if isinstance(e, DeathPenaltyPaid))
    assert ev.loot_discarded == loot_ref
    assert loot_ref not in p1.hand
    assert loot_ref in g.zones.loot_discard.cards


def test_loot_discarded_none_when_hand_empty():
    result = _die(_game(hand=[]))
    ev = next(e for e in result.events if isinstance(e, DeathPenaltyPaid))
    assert ev.loot_discarded is None


# ---------------------------------------------------------------------------
# Step 3 — lose 1¢
# ---------------------------------------------------------------------------

def test_loses_one_cent():
    g = _game(cents=5)
    p1 = g.state.get_player(PlayerId("P1"))

    result = _die(g)

    ev = next(e for e in result.events if isinstance(e, DeathPenaltyPaid))
    assert ev.cents_lost == 1
    assert p1.cents == 4


def test_cents_floored_at_zero():
    g = _game(cents=0)
    p1 = g.state.get_player(PlayerId("P1"))

    result = _die(g)

    ev = next(e for e in result.events if isinstance(e, DeathPenaltyPaid))
    assert ev.cents_lost == 0
    assert p1.cents == 0


# ---------------------------------------------------------------------------
# Step 4 — deactivate (untap) ↷ items
# ---------------------------------------------------------------------------

def test_tapped_character_untapped_on_death():
    g = _game(character_tapped=True)
    p1 = g.state.get_player(PlayerId("P1"))

    result = _die(g)

    ev = next(e for e in result.events if isinstance(e, DeathPenaltyPaid))
    assert ev.items_deactivated == 1
    assert not p1.character.is_tapped


def test_untapped_character_not_counted():
    g = _game(character_tapped=False)

    result = _die(g)

    ev = next(e for e in result.events if isinstance(e, DeathPenaltyPaid))
    assert ev.items_deactivated == 0


# ---------------------------------------------------------------------------
# Full-penalty path
# ---------------------------------------------------------------------------

def test_full_penalty_all_four_steps():
    item_ref = _ref("treasure-0")
    loot_ref = _ref("loot-0")
    g = _game(
        cents=3,
        items=[item_ref],
        hand=[loot_ref],
        character_tapped=True,
    )
    p1 = g.state.get_player(PlayerId("P1"))

    result = _die(g)

    ev = next(e for e in result.events if isinstance(e, DeathPenaltyPaid))
    assert ev.item_destroyed == item_ref
    assert ev.loot_discarded == loot_ref
    assert ev.cents_lost == 1
    assert ev.items_deactivated == 1

    assert not any(i.card_ref == item_ref for i in p1.items)
    assert loot_ref not in p1.hand
    assert p1.cents == 2
    assert not p1.character.is_tapped
