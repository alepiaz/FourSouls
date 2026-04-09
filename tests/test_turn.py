from foursouls.engine.rng import RNG
from foursouls.model.commands import EndTurn, PassPriority
from foursouls.model.game_state import GameState
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.setup import setup_game


def _make_cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _game_two_players():
    """Two-player game fully set up with zones; Loot1 already queued by setup_game."""
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    return setup_game(
        state,
        loot_cards=_make_cards("loot", 20),
        treasure_cards=_make_cards("treasure", 10),
        monster_cards=_make_cards("monster", 10),
        rng=RNG(seed=0),
    )


def test_start_phase_queues_loot1():
    g = _game_two_players()

    assert not g.stack.empty()
    assert g.stack.top().label == "Loot1"
    assert g.stack.top().controller_id == PlayerId("P1")
    assert g.state.phase == Phase.START


def test_after_loot1_resolves_and_all_passed_phase_becomes_action():
    g = _game_two_players()  # stack: [Loot1], phase: START

    hand_before = len(g.state.get_player(PlayerId("P1")).hand)

    # Both pass → Loot1 resolves (draws 1 card), stack becomes empty, phase auto-advances
    g.step(PassPriority())  # P1 passes
    g.step(PassPriority())  # P2 passes → Loot1 resolved → START→ACTION automatically
    assert g.stack.empty()
    assert g.state.phase == Phase.ACTION  # auto-advanced; no second pass cycle needed
    assert len(g.state.get_player(PlayerId("P1")).hand) == hand_before + 1


def _char(name: str) -> ItemInPlay:
    return ItemInPlay(card_ref=CardRef(InstanceId(name)))


def test_character_untaps_at_start_of_own_turn():
    """Character is tapped mid-turn, then untaps when that player's next turn begins."""
    g = _game_two_players()

    # Give P1 a tapped character
    p1 = g.state.get_player(PlayerId("P1"))
    p1.character = _char("char-p1")
    p1.character.tap()
    assert p1.character.is_tapped

    # Advance P1's turn all the way through and end it → P2's START phase begins
    g.step(PassPriority())
    g.step(PassPriority())  # Loot1 resolves → auto-advance to ACTION
    g.step(EndTurn())       # P2's turn starts; P1's char still tapped

    assert p1.character.is_tapped  # P1's char does NOT untap on P2's turn

    # Advance P2's turn and end it → P1's START phase begins → untap
    g.step(PassPriority())
    g.step(PassPriority())  # P2 Loot1 resolves → auto-advance to ACTION
    g.step(EndTurn())       # P1's turn starts → enter_start_phase untaps P1's char

    assert not p1.character.is_tapped  # now untapped


def test_character_with_no_character_does_not_crash():
    """Players without a character set sail through enter_start_phase fine."""
    g = _game_two_players()
    p1 = g.state.get_player(PlayerId("P1"))
    assert p1.character is None  # default
    # Stack already has Loot1 — just verify no exception was raised during setup
    assert not g.stack.empty()


def test_end_turn_advances_player_and_phase_start_and_queues_loot1():
    g = _game_two_players()

    # Advance through START phase so we can reach ACTION
    g.step(PassPriority())
    g.step(PassPriority())  # Loot1 resolves → auto-advance to ACTION
    assert g.state.phase == Phase.ACTION

    p1 = g.state.get_player(PlayerId("P1"))
    p2 = g.state.get_player(PlayerId("P2"))
    p1.hp = 1  # damage P1 to verify heal
    p2.hp = 1  # damage P2 to verify all players heal

    g.step(EndTurn())

    # Active player advanced to P2
    assert g.state.active_player_id == PlayerId("P2")
    # Phase reset to START
    assert g.state.phase == Phase.START
    # Turn number bumped
    assert g.state.turn_number == 2
    # All players healed to full (not just active player)
    assert p1.hp == p1.max_hp
    assert p2.hp == p2.max_hp
    # Loot1 queued for P2
    assert not g.stack.empty()
    assert g.stack.top().label == "Loot1"
    assert g.stack.top().controller_id == PlayerId("P2")


def test_monsters_heal_to_full_at_end_of_turn():
    """Monsters in slots heal back to base_hp at end of turn (e.g. after player dies mid-attack)."""
    g = _game_two_players()

    # Place a damaged monster in slot 0 (base_hp=3, took 2 damage → current_hp=1)
    monster = MonsterInPlay(
        card_ref=CardRef(InstanceId("monster-0")),
        base_hp=3,
        current_hp=1,
        evade=1,
        reward_cents=0,
        has_soul=False,
    )
    g.zones.monster_slots.set(0, monster)

    # Advance through START → ACTION → EndTurn
    g.step(PassPriority())
    g.step(PassPriority())  # Loot1 resolves → ACTION
    g.step(EndTurn())

    # Monster should have healed to base_hp
    assert g.zones.monster_slots.get(0).current_hp == 3
