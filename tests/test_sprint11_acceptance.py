"""
Sprint 11 acceptance tests — Treasure card effects + starting eternal items.

R11.2 — ActivateItem command; TreasureActivateEffect; Mama Mega and Yum Heart
         card definitions; end_of_turn / start_of_turn item recharge.
R11.3 — Starting Eternal items at setup; damage_cap (Dry Baby);
         on_enters_play passive hook (Meat!); The D6 / Lucky Foot stubs.
"""
from __future__ import annotations

import pytest

from foursouls.cards.characters import CAIN, EVE, ISAAC, MAGDALENE
from foursouls.cards.treasures import (
    DRY_BABY, LUCKY_FOOT, MAMA_MEGA, MEAT_BANG,
    SLEIGHT_OF_HAND, THE_CURSE, THE_D6, YUM_HEART,
)
from foursouls.engine.rng import RNG
from foursouls.model.commands import ActivateItem, EndTurn, PassPriority
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId
from foursouls.model.target import MonsterTarget, PlayerTarget
from foursouls.rulesets.common.setup import setup_game
from foursouls.model.game_state import GameState
from foursouls.model.player_state import PlayerState
from foursouls.engine.game_zones import GameZones
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.engine.game_loop import Game

from agents.pass_bot import choose_command as pass_command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ref(name: str, card_id: CardId | None = None) -> CardRef:
    return CardRef(InstanceId(name), card_id)


def _item(name: str, card_id: CardId, *, eternal: bool = False,
          recharge_on: str = "start_of_turn") -> ItemInPlay:
    return ItemInPlay(
        card_ref=_ref(name, card_id),
        eternal=eternal,
        recharge_on=recharge_on,
    )


def _make_cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _game_at_action(items_p1: list[ItemInPlay] = ()) -> Game:
    """Two-player game at ACTION phase; given items placed in P1's zone."""
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=6, hp=6)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=6, hp=6)

    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    g = setup_game(
        state,
        loot_cards=_make_cards("loot", 40),
        treasure_cards=_make_cards("treasure", 10),
        monster_cards=_make_cards("monster", 10),
        rng=RNG(seed=0),
    )
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    for it in items_p1:
        g.state.get_player(PlayerId("P1")).items.append(it)

    return g


def _resolve(g: Game) -> None:
    """Pass priority twice to resolve the top stack item."""
    g.step(PassPriority())
    g.step(PassPriority())


# ---------------------------------------------------------------------------
# R11.2 — ActivateItem legality
# ---------------------------------------------------------------------------

def test_activate_item_not_legal_without_tap_items():
    g = _game_at_action()
    cmds = g.legal_commands()
    assert not any(isinstance(c, ActivateItem) for c in cmds)


def test_activate_item_legal_for_mama_mega_no_target():
    mama = _item("mama", MAMA_MEGA)
    g = _game_at_action(items_p1=[mama])
    cmds = g.legal_commands()
    ai = [c for c in cmds if isinstance(c, ActivateItem)]
    assert len(ai) == 1
    assert ai[0].instance_id == InstanceId("mama")
    assert ai[0].target is None


def test_activate_item_legal_for_yum_heart_per_target():
    yum = _item("yum", YUM_HEART, eternal=True, recharge_on="end_of_turn")
    g = _game_at_action(items_p1=[yum])
    cmds = g.legal_commands()
    ai = [c for c in cmds if isinstance(c, ActivateItem)]

    player_targets = [c for c in ai if isinstance(c.target, PlayerTarget)]
    monster_targets = [c for c in ai if isinstance(c.target, MonsterTarget)]

    assert len(player_targets) == 2   # P1 and P2
    assert len(monster_targets) >= 1  # at least one monster slot occupied


def test_tapped_item_not_legal():
    mama = _item("mama-t", MAMA_MEGA)
    mama.tap()
    g = _game_at_action(items_p1=[mama])
    cmds = g.legal_commands()
    assert not any(isinstance(c, ActivateItem) for c in cmds)


# ---------------------------------------------------------------------------
# R11.2 — Mama Mega: one-use AoD
# ---------------------------------------------------------------------------

def test_mama_mega_deals_3_damage_to_all_players():
    mama = _item("mama-d", MAMA_MEGA)
    g = _game_at_action(items_p1=[mama])
    p1 = g.state.get_player(PlayerId("P1"))
    p2 = g.state.get_player(PlayerId("P2"))
    h1, h2 = p1.hp, p2.hp

    g.step(ActivateItem(instance_id=InstanceId("mama-d")))
    _resolve(g)

    assert p1.hp == h1 - 3
    assert p2.hp == h2 - 3


def test_mama_mega_deals_3_damage_to_all_monsters():
    mama = _item("mama-m", MAMA_MEGA)
    g = _game_at_action(items_p1=[mama])

    # Note all monster slots should be occupied from setup; confirm HP reduced
    slots = g.zones.monster_slots
    hp_before = {idx: slots.get(idx).current_hp for idx in slots.filled_indices()}

    g.step(ActivateItem(instance_id=InstanceId("mama-m")))
    _resolve(g)

    for idx, hp in hp_before.items():
        assert slots.get(idx).current_hp == max(0, hp - 3)


def test_mama_mega_is_destroyed_after_use():
    mama = _item("mama-x", MAMA_MEGA)
    g = _game_at_action(items_p1=[mama])
    p1 = g.state.get_player(PlayerId("P1"))

    g.step(ActivateItem(instance_id=InstanceId("mama-x")))
    _resolve(g)

    assert not any(i.card_ref.instance_id == InstanceId("mama-x") for i in p1.items)
    assert _ref("mama-x", MAMA_MEGA) in g.zones.treasure_discard.cards


def test_mama_mega_tapped_after_activation_then_destroyed():
    """Tapping happens before stack push; item is gone after resolution."""
    mama = _item("mama-tap", MAMA_MEGA)
    g = _game_at_action(items_p1=[mama])
    p1 = g.state.get_player(PlayerId("P1"))

    g.step(ActivateItem(instance_id=InstanceId("mama-tap")))
    # After the command: item is tapped and on the stack, not yet destroyed
    assert mama.is_tapped

    _resolve(g)
    # After resolution: item is gone (is_one_use)
    assert mama not in p1.items


# ---------------------------------------------------------------------------
# R11.2 — Yum Heart: targeted prevent-damage
# ---------------------------------------------------------------------------

def test_yum_heart_prevents_player_damage():
    yum = _item("yum-p", YUM_HEART, eternal=True, recharge_on="end_of_turn")
    from foursouls.cards.loot import BOMB_BANG
    bomb = _ref("bomb-y", BOMB_BANG)

    g = _game_at_action(items_p1=[yum])
    g.state.get_player(PlayerId("P1")).hand.append(bomb)
    g.state.turn_flags.loot_plays_allowed = 2

    p2 = g.state.get_player(PlayerId("P2"))
    hp_before = p2.hp

    # Activate Yum Heart targeting P2
    from foursouls.model.commands import PlayLoot
    g.step(ActivateItem(instance_id=InstanceId("yum-p"), target=PlayerTarget(PlayerId("P2"))))
    _resolve(g)
    assert p2.prevent_damage == 1

    # Bomb P2 — shield absorbs it
    g.step(PlayLoot(card_ref=bomb, target=PlayerTarget(PlayerId("P2"))))
    _resolve(g)

    assert p2.hp == hp_before
    assert p2.prevent_damage == 0


def test_yum_heart_prevents_monster_damage():
    yum = _item("yum-m", YUM_HEART, eternal=True, recharge_on="end_of_turn")
    from foursouls.cards.loot import BOMB_BANG
    bomb = _ref("bomb-ym", BOMB_BANG)

    g = _game_at_action(items_p1=[yum])
    g.state.get_player(PlayerId("P1")).hand.append(bomb)
    g.state.turn_flags.loot_plays_allowed = 2

    monster = g.zones.monster_slots.get(0)
    assert monster is not None
    hp_before = monster.current_hp

    from foursouls.model.commands import PlayLoot
    g.step(ActivateItem(instance_id=InstanceId("yum-m"), target=MonsterTarget(slot_index=0)))
    _resolve(g)
    assert monster.prevent_damage == 1

    g.step(PlayLoot(card_ref=bomb, target=MonsterTarget(slot_index=0)))
    _resolve(g)

    assert monster.current_hp == hp_before
    assert monster.prevent_damage == 0


def test_yum_heart_tapped_after_activation():
    yum = _item("yum-tap", YUM_HEART, eternal=True, recharge_on="end_of_turn")
    g = _game_at_action(items_p1=[yum])

    g.step(ActivateItem(instance_id=InstanceId("yum-tap"), target=PlayerTarget(PlayerId("P1"))))
    assert yum.is_tapped


# ---------------------------------------------------------------------------
# R11.2 — Recharge timing
# ---------------------------------------------------------------------------

def test_end_of_turn_item_recharges_at_end_of_turn():
    yum = _item("yum-r", YUM_HEART, eternal=True, recharge_on="end_of_turn")
    yum.tap()
    g = _game_at_action(items_p1=[yum])

    g.step(EndTurn())

    # After EndTurn the item should be untapped (owner's turn just ended)
    assert not yum.is_tapped


def test_start_of_turn_item_recharges_at_start_of_turn():
    """A start_of_turn item tapped during turn N is untapped at the START of turn N+2
    (when P1's turn comes around again). We test that it is untapped after two full
    EndTurns bring us back to P1's ACTION phase."""
    from foursouls.cards.treasures import MAMA_MEGA  # any start_of_turn card ID
    item = _item("s-item", MAMA_MEGA, recharge_on="start_of_turn")
    item.tap()
    g = _game_at_action(items_p1=[item])

    # End P1's turn → P2's turn
    g.step(EndTurn())
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    # Item still tapped (start_of_turn recharge fires when owner's turn starts)
    assert item.is_tapped

    # End P2's turn → back to P1's turn; item should now be untapped
    g.step(EndTurn())
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    assert not item.is_tapped


# ---------------------------------------------------------------------------
# R11.3 — Starting Eternal items
# ---------------------------------------------------------------------------

def _demo_game_at_action(player_ids=("P1", "P2")):
    """build_demo_game (real characters) advanced to ACTION phase."""
    from foursouls.cli.app import build_demo_game
    g = build_demo_game(list(player_ids), seed=0)
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))
    return g


def test_isaac_starts_with_the_d6():
    g = _demo_game_at_action()
    # P1 → Isaac (first in _CHAR_POOL)
    p1 = g.state.get_player(PlayerId("P1"))
    assert any(i.card_ref.card_id == THE_D6 for i in p1.items)


def test_magdalene_starts_with_yum_heart():
    g = _demo_game_at_action()
    # P2 → Magdalene
    p2 = g.state.get_player(PlayerId("P2"))
    assert any(i.card_ref.card_id == YUM_HEART for i in p2.items)


def test_starting_eternal_is_eternal_flag():
    g = _demo_game_at_action()
    p1 = g.state.get_player(PlayerId("P1"))
    d6 = next(i for i in p1.items if i.card_ref.card_id == THE_D6)
    assert d6.eternal is True


def test_starting_eternal_has_correct_recharge():
    g = _demo_game_at_action()
    p1 = g.state.get_player(PlayerId("P1"))
    d6 = next(i for i in p1.items if i.card_ref.card_id == THE_D6)
    assert d6.recharge_on == "end_of_turn"


def test_cain_starts_with_sleight_of_hand():
    from foursouls.cards.characters import CAIN, get_character_def
    from foursouls.cli.app import build_demo_game
    # Build a 3-player game; P3 → Cain (index 2 in pool)
    g = build_demo_game(["P1", "P2", "P3"], seed=0)
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))
    p3 = g.state.get_player(PlayerId("P3"))
    assert any(i.card_ref.card_id == SLEIGHT_OF_HAND for i in p3.items)


# ---------------------------------------------------------------------------
# R11.3 — damage_cap (Dry Baby)
# ---------------------------------------------------------------------------

def test_damage_cap_limits_hit_damage():
    g = _game_at_action()
    p1 = g.state.get_player(PlayerId("P1"))
    p1.damage_cap = 1
    hp_before = p1.hp

    from foursouls.cards.loot import GOLD_BOMB_BANG_BANG
    bomb = _ref("gbomb", GOLD_BOMB_BANG_BANG)
    g.state.get_player(PlayerId("P1")).hand.append(bomb)
    from foursouls.model.commands import PlayLoot
    g.step(PlayLoot(card_ref=bomb, target=PlayerTarget(PlayerId("P1"))))
    _resolve(g)

    # Gold Bomb!! deals 3, but cap=1 → only 1 damage taken
    assert p1.hp == hp_before - 1


def test_zero_damage_cap_means_no_cap():
    g = _game_at_action()
    p1 = g.state.get_player(PlayerId("P1"))
    p1.damage_cap = 0   # no cap
    hp_before = p1.hp

    from foursouls.cards.loot import GOLD_BOMB_BANG_BANG
    bomb = _ref("gbomb2", GOLD_BOMB_BANG_BANG)
    g.state.get_player(PlayerId("P1")).hand.append(bomb)
    from foursouls.model.commands import PlayLoot
    g.step(PlayLoot(card_ref=bomb, target=PlayerTarget(PlayerId("P1"))))
    _resolve(g)

    assert p1.hp == hp_before - 3


def test_dry_baby_bought_sets_damage_cap():
    g = _game_at_action()
    p1 = g.state.get_player(PlayerId("P1"))
    p1.cents = 100
    dry_ref = _ref("dry-0", DRY_BABY)
    g.zones.shop_slots.set(0, dry_ref)

    from foursouls.model.commands import BuyShop
    g.step(BuyShop(slot_index=0))

    assert p1.damage_cap == 1


# ---------------------------------------------------------------------------
# R11.3 — on_enters_play passive hook (Meat!)
# ---------------------------------------------------------------------------

def test_meat_bought_increments_attack_bonus():
    g = _game_at_action()
    p1 = g.state.get_player(PlayerId("P1"))
    bonus_before = p1.attack_bonus
    p1.cents = 100
    meat_ref = _ref("meat-0", MEAT_BANG)
    g.zones.shop_slots.set(0, meat_ref)

    from foursouls.model.commands import BuyShop
    g.step(BuyShop(slot_index=0))

    assert p1.attack_bonus == bonus_before + 1


def test_meat_stacks_on_second_purchase():
    g = _game_at_action()
    p1 = g.state.get_player(PlayerId("P1"))
    p1.cents = 100
    g.zones.shop_slots.set(0, _ref("meat-a", MEAT_BANG))
    g.zones.shop_slots.set(1, _ref("meat-b", MEAT_BANG))

    from foursouls.model.commands import BuyShop
    g.step(BuyShop(slot_index=0))
    g.state.turn_flags.purchase_used = False   # reset to allow second buy
    g.step(BuyShop(slot_index=1))

    assert p1.attack_bonus == 2
