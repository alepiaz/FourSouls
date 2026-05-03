"""
Sprint 7 acceptance — correct player death penalty.
Covers R7.1 (eternal flag), R7.2 (death penalty), R7.3 (active-player death →
END phase), and R7.4 (died_this_turn guard).
"""
from __future__ import annotations

import agents.combat_bot as combat_bot
from agents.pass_bot import choose_command as pass_command
from foursouls.cli.app import build_demo_game
from foursouls.engine.events import DeathPenaltyPaid, PhaseChanged, PlayerDied
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import (
    AttackMonster,
    BuyShop,
    EndTurn,
    PassPriority,
    PlayLoot,
    RollCombat,
)
from foursouls.model.game_state import GameState
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.legality import legal_commands
from foursouls.rulesets.common.setup import setup_game


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _ref(name: str) -> CardRef:
    return CardRef(InstanceId(name))


def _miss_monster(hp: int = 5) -> MonsterInPlay:
    """evade=7 → always miss → player takes damage every roll."""
    return MonsterInPlay(
        card_ref=_ref("m-0"),
        base_hp=hp,
        current_hp=hp,
        evade=7,
        reward_coin=0,
        has_soul=False,
    )


def _game(
    *,
    player_hp: int = 1,
    cents: int = 0,
    items: list | None = None,
    hand: list[CardRef] | None = None,
    character_tapped: bool = False,
    n_players: int = 1,
) -> Game:
    """
    Return a Game in ACTION phase with combat declared against slot 0.
    evade=7 → first roll is always a miss; player_hp=1 → player dies.
    """
    players = [
        PlayerState(player_id=PlayerId(f"P{i+1}"), max_hp=player_hp, hp=player_hp)
        for i in range(n_players)
    ]
    p1 = players[0]
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

    state = GameState.from_players(players, active_player_id=PlayerId("P1"))
    state.phase = Phase.ACTION

    ms: SlotsZone[MonsterInPlay] = SlotsZone(size=1)
    ms.set(0, _miss_monster())

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
    g = Game(state=state, zones=zones, rng=RNG(seed=0))
    g.step(AttackMonster(slot_index=0))
    return g


def _die(g: Game):
    """Roll once → miss → player_hp=1 → death.
    Passes priority for every player until CombatMissDamageEffect resolves."""
    roll = g.step(RollCombat())
    all_events = list(roll.events)
    for _ in range(len(g.state.turn_order)):
        result = g.step(PassPriority())
        all_events.extend(result.events)

    class _Combined:
        events = all_events

    return _Combined()


# ---------------------------------------------------------------------------
# R7.1 — Eternal flag on ItemInPlay; starting items are eternal
# ---------------------------------------------------------------------------

def test_eternal_defaults_to_false():
    item = ItemInPlay(card_ref=CardRef(InstanceId("x")))
    assert item.eternal is False


def test_eternal_can_be_set_true():
    item = ItemInPlay(card_ref=CardRef(InstanceId("x")), eternal=True)
    assert item.eternal is True


def test_eternal_is_orthogonal_to_tapped():
    item = ItemInPlay(card_ref=CardRef(InstanceId("x")), eternal=True)
    assert not item.is_tapped
    item.tap()
    assert item.is_tapped
    assert item.eternal is True  # tap does not change eternal


def test_build_demo_game_characters_are_eternal():
    g = build_demo_game(["Alice", "Bob"], seed=0)
    for pid in g.state.turn_order:
        char = g.state.get_player(pid).character
        assert char is not None, f"{pid} has no character"
        assert char.eternal is True, f"{pid}'s character is not eternal"


def test_non_starting_item_is_not_eternal():
    item = ItemInPlay(card_ref=CardRef(InstanceId("treasure-0")))
    assert item.eternal is False


# ---------------------------------------------------------------------------
# R7.2 — Death penalty applied in resolve_player_death; DeathPenaltyPaid event
# ---------------------------------------------------------------------------

def test_both_events_emitted():
    result = _die(_game())
    assert any(isinstance(e, PlayerDied) for e in result.events)
    assert any(isinstance(e, DeathPenaltyPaid) for e in result.events)


def test_player_died_before_penalty():
    result = _die(_game())
    names = [type(e).__name__ for e in result.events]
    assert names.index("PlayerDied") < names.index("DeathPenaltyPaid")


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
    assert any(i.card_ref == second for i in p1.items)


def test_item_destroyed_none_when_no_items():
    result = _die(_game(items=[]))
    ev = next(e for e in result.events if isinstance(e, DeathPenaltyPaid))
    assert ev.item_destroyed is None


def test_eternal_character_not_in_destroyable_pool():
    """The character (eternal=True) must never be destroyed by the death penalty."""
    g = _game(items=[])
    p1 = g.state.get_player(PlayerId("P1"))
    char_before = p1.character

    _die(g)

    assert p1.character is char_before


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


# ---------------------------------------------------------------------------
# R7.3 — Active-player death: cancel combat → advance to END phase
# ---------------------------------------------------------------------------

def test_phase_is_end_after_active_player_death():
    g = _game()
    _die(g)
    assert g.state.phase == Phase.END


def test_phase_changed_event_action_to_end():
    result = _die(_game())
    phase_events = [e for e in result.events if isinstance(e, PhaseChanged)]
    assert any(e.old_phase == Phase.ACTION and e.new_phase == Phase.END
               for e in phase_events)


def test_end_turn_legal_in_end_phase():
    g = _game()
    _die(g)
    assert EndTurn() in legal_commands(g)


def test_pass_priority_legal_in_end_phase():
    g = _game()
    _die(g)
    assert PassPriority() in legal_commands(g)


def test_attack_illegal_in_end_phase():
    g = _game()
    _die(g)
    cmds = legal_commands(g)
    assert not any(isinstance(c, AttackMonster) for c in cmds)


def test_roll_combat_illegal_in_end_phase():
    g = _game()
    _die(g)
    assert RollCombat() not in legal_commands(g)


def test_play_loot_illegal_in_end_phase():
    g = _game()
    p1 = g.state.get_player(PlayerId("P1"))
    p1.hand.append(_ref("loot-x"))
    _die(g)
    cmds = legal_commands(g)
    assert not any(isinstance(c, PlayLoot) for c in cmds)


def test_buy_shop_illegal_in_end_phase():
    g = _game()
    p1 = g.state.get_player(PlayerId("P1"))
    p1.cents = 100
    g.zones.shop_slots.set(0, _ref("treasure-x"))
    _die(g)
    cmds = legal_commands(g)
    assert not any(isinstance(c, BuyShop) for c in cmds)


def test_end_turn_from_end_phase_advances_turn():
    g = _game(n_players=2)
    _die(g)
    assert g.state.phase == Phase.END

    g.step(EndTurn())

    assert g.state.active_player_id == PlayerId("P2")


def test_phase_changed_end_to_start_on_end_turn():
    g = _game(n_players=2)
    _die(g)

    result = g.step(EndTurn())

    phase_evts = [e for e in result.events if isinstance(e, PhaseChanged)]
    assert any(e.old_phase == Phase.END and e.new_phase == Phase.START
               for e in phase_evts)


def test_turn_number_increments_after_end_phase_end_turn():
    g = _game(n_players=2)
    turn_before = g.state.turn_number
    _die(g)
    g.step(EndTurn())

    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    assert g.state.turn_number == turn_before + 1


def test_combat_bot_drives_active_death_full_flow():
    """
    setup_game → ACTION → P1 dies (hp=1, evade=7) → END phase →
    combat_bot issues EndTurn → P2 active → P2's turn completes →
    P1's second turn: attack_used=False, hp healed to max.
    """
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=1, hp=1)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=4, hp=4)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))

    monster_cards = [_ref(f"m-{i}") for i in range(4)]
    loot_cards = [_ref(f"loot-{i}") for i in range(20)]
    treasure_cards = [_ref(f"treasure-{i}") for i in range(6)]

    g = setup_game(
        state,
        loot_cards=loot_cards,
        treasure_cards=treasure_cards,
        monster_cards=monster_cards,
        rng=RNG(seed=0),
        monster_slot_count=1,
    )
    g.zones.monster_slots.set(0, _miss_monster())

    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    turn_before = g.state.turn_number
    for _ in range(20):
        if g.state.turn_number != turn_before:
            break
        g.step(combat_bot.choose_command(g))
    else:
        raise AssertionError("P1's turn did not end")

    assert g.state.active_player_id == PlayerId("P2")

    while g.state.active_player_id == PlayerId("P2"):
        g.step(pass_command(g))

    assert g.state.active_player_id == PlayerId("P1")
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    assert g.state.get_player(PlayerId("P1")).hp == 1
    assert not g.state.turn_flags.attack_used


# ---------------------------------------------------------------------------
# R7.4 — died_this_turn guard; a player can only die once per turn
# ---------------------------------------------------------------------------

def test_died_this_turn_defaults_false():
    g = _game()
    assert g.state.turn_flags.died_this_turn is False


def test_died_this_turn_true_after_death():
    g = _game(player_hp=1)
    g.step(RollCombat())
    g.step(PassPriority())
    assert g.state.turn_flags.died_this_turn is True


def test_exactly_one_player_died_event():
    g = _game(player_hp=1)
    roll = g.step(RollCombat())
    resolve = g.step(PassPriority())
    events = roll.events + resolve.events
    assert len([e for e in events if isinstance(e, PlayerDied)]) == 1


def test_exactly_one_death_penalty_event():
    g = _game(player_hp=1)
    roll = g.step(RollCombat())
    resolve = g.step(PassPriority())
    events = roll.events + resolve.events
    assert len([e for e in events if isinstance(e, DeathPenaltyPaid)]) == 1


def test_guard_suppresses_second_death_trigger():
    """
    Pre-set died_this_turn=True; a second miss must not fire PlayerDied.
    """
    g = _game(player_hp=2)
    g.step(RollCombat())
    g.step(PassPriority())   # hp 2→1
    assert g.state.get_player(PlayerId("P1")).hp == 1
    assert g.combat is not None

    g.state.turn_flags.died_this_turn = True
    g.state.get_player(PlayerId("P1")).hp = 0

    result = g.step(RollCombat())
    assert not any(isinstance(e, PlayerDied) for e in result.events)
    assert not any(isinstance(e, DeathPenaltyPaid) for e in result.events)


def test_died_this_turn_resets_on_new_turn():
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=1, hp=1)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=4, hp=4)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))

    g = setup_game(
        state,
        loot_cards=[_ref(f"loot-{i}") for i in range(20)],
        treasure_cards=[_ref(f"treasure-{i}") for i in range(6)],
        monster_cards=[_ref(f"m-{i}") for i in range(4)],
        rng=RNG(seed=0),
        monster_slot_count=1,
    )
    g.zones.monster_slots.set(0, _miss_monster())

    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())
    g.step(PassPriority())   # P1 passes
    g.step(PassPriority())   # P2 passes → effect resolves → P1 dies
    assert g.state.turn_flags.died_this_turn is True

    g.step(pass_command(g))
    turn_before = g.state.turn_number
    for _ in range(10):
        if g.state.active_player_id == PlayerId("P2"):
            break
        g.step(combat_bot.choose_command(g))

    assert g.state.active_player_id == PlayerId("P2")
    assert g.state.turn_flags.died_this_turn is False


def test_sprint7_acceptance_died_this_turn_lifecycle():
    """
    Full Sprint 7 acceptance:
      setup → P1 (hp=1) attacks guaranteed-miss monster →
      P1 dies → died_this_turn=True, phase=END →
      combat_bot issues EndTurn →
      P2's turn: died_this_turn=False →
      P2 passes → P1's second turn: died_this_turn=False, hp healed.
    """
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=1, hp=1)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=4, hp=4)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))

    g = setup_game(
        state,
        loot_cards=[_ref(f"loot-{i}") for i in range(20)],
        treasure_cards=[_ref(f"treasure-{i}") for i in range(6)],
        monster_cards=[_ref(f"m-{i}") for i in range(4)],
        rng=RNG(seed=0),
        monster_slot_count=1,
    )
    g.zones.monster_slots.set(0, _miss_monster())

    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())
    g.step(PassPriority())   # P1 passes
    g.step(PassPriority())   # P2 passes → effect resolves → P1 dies

    assert g.state.get_player(PlayerId("P1")).hp == 0
    assert g.state.turn_flags.died_this_turn is True
    assert g.state.phase == Phase.END

    turn_start = g.state.turn_number
    for _ in range(10):
        if g.state.turn_number != turn_start:
            break
        g.step(combat_bot.choose_command(g))

    assert g.state.active_player_id == PlayerId("P2")
    assert g.state.turn_flags.died_this_turn is False

    while g.state.active_player_id == PlayerId("P2"):
        g.step(pass_command(g))

    assert g.state.active_player_id == PlayerId("P1")
    while g.state.phase != Phase.ACTION:
        g.step(pass_command(g))

    assert g.state.get_player(PlayerId("P1")).hp == 1
    assert g.state.turn_flags.died_this_turn is False
    assert not g.state.turn_flags.attack_used
