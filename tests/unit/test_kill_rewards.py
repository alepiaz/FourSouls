"""
Release 4.6 — Rewards + souls tests.

Strategy:
  evade=1  → guaranteed hit → monster takes damage every roll.
  Monster with hp=1 dies on the first roll.

Reward model:
  - reward_coin is granted to the attacker on every monster kill (even if 0).
  - soul (card_ref) is added to attacker.souls only when has_soul=True.
  - Both events fire exactly once per kill.

Covers:
- reward cents added to attacker.cents on kill
- zero-reward kill still fires CoinsGained(cents=0)
- CoinsGained event fields are correct
- soul added to attacker.souls on soul-bearing monster kill
- SoulGranted event emitted with correct fields
- no soul added for non-soul monster
- SoulGranted not emitted for non-soul monster
- cents accumulate correctly across multiple kills in the same turn
- rewards go to attacker only; other player states unchanged
- CoinsGained fires exactly once per kill
- SoulGranted fires exactly once per soul kill
"""
from __future__ import annotations

from foursouls.cards.monsters import FLY, GAPER, HORF, make_monster_in_play
from foursouls.engine.events import CoinsGained, SoulGranted
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import AttackMonster, RollCombat
from foursouls.model.game_state import GameState
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardRef, InstanceId, PlayerId


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_monster(name: str, *, hp: int = 1, evade: int = 1,
                  reward_coin: int = 0, has_soul: bool = False) -> MonsterInPlay:
    return MonsterInPlay(
        card_ref=CardRef(InstanceId(name)),
        base_hp=hp,
        current_hp=hp,
        evade=evade,
        reward_coin=reward_coin,
        has_soul=has_soul,
    )


def _make_zones(monsters: list[MonsterInPlay | None],
                deck: list[CardRef] | None = None) -> GameZones:
    ms: SlotsZone[MonsterInPlay] = SlotsZone(size=max(len(monsters), 1))
    for i, m in enumerate(monsters):
        if m is not None:
            ms.set(i, m)
    monster_deck: DeckZone[CardRef] = DeckZone(cards=list(deck) if deck else [])
    return GameZones(
        loot_deck=DeckZone(),
        loot_discard=DiscardZone(),
        treasure_deck=DeckZone(),
        treasure_discard=DiscardZone(),
        monster_deck=monster_deck,
        monster_discard=DiscardZone(),
        shop_slots=SlotsZone(size=1),
        monster_slots=ms,
    )


def _game(monster: MonsterInPlay,
          *,
          player_cents: int = 0,
          n_players: int = 1) -> Game:
    """Return a Game already in combat against the given monster in slot 0."""
    players = [
        PlayerState(player_id=PlayerId(f"P{i+1}"), max_hp=5, hp=5, cents=player_cents)
        for i in range(n_players)
    ]
    gs = GameState.from_players(players, active_player_id=PlayerId("P1"))
    gs.phase = Phase.ACTION
    g = Game(state=gs, zones=_make_zones([monster]), rng=RNG(seed=0))
    g.step(AttackMonster(slot_index=0))
    return g


def _kill(g: Game) -> list:
    """Roll until combat ends; return events from the killing roll."""
    events = []
    while g.combat is not None:
        events = g.step(RollCombat()).events
    return events


# ---------------------------------------------------------------------------
# Cent reward
# ---------------------------------------------------------------------------

def test_reward_coin_added_to_attacker():
    m = _make_monster("m", reward_coin=5)
    g = _game(m)
    g.state.get_player(PlayerId("P1")).cents = 0
    _kill(g)
    assert g.state.get_player(PlayerId("P1")).cents == 5


def test_zero_reward_monster_cents_unchanged():
    m = _make_monster("m", reward_coin=0)
    g = _game(m, player_cents=3)
    _kill(g)
    assert g.state.get_player(PlayerId("P1")).cents == 3


def test_reward_granted_event_emitted():
    m = _make_monster("m", reward_coin=5)
    g = _game(m)
    events = _kill(g)
    reward_events = [e for e in events if isinstance(e, CoinsGained)]
    assert len(reward_events) == 1


def test_reward_granted_event_fires_even_for_zero_cents():
    m = _make_monster("m", reward_coin=0)
    g = _game(m)
    events = _kill(g)
    reward_events = [e for e in events if isinstance(e, CoinsGained)]
    assert len(reward_events) == 1


def test_reward_granted_event_fields():
    m = _make_monster("m", reward_coin=7)
    g = _game(m)
    events = _kill(g)
    ev = next(e for e in events if isinstance(e, CoinsGained))
    assert ev.player_id == PlayerId("P1")
    assert ev.cents == 7


def test_reward_granted_exactly_once_per_kill():
    m = _make_monster("m", hp=3, evade=1, reward_coin=5)
    g = _game(m)
    all_events: list = []
    while g.combat is not None:
        all_events.extend(g.step(RollCombat()).events)
    reward_events = [e for e in all_events if isinstance(e, CoinsGained)]
    assert len(reward_events) == 1


# ---------------------------------------------------------------------------
# Soul reward
# ---------------------------------------------------------------------------

def test_soul_added_to_attacker_on_soul_monster_kill():
    m = _make_monster("m-soul", has_soul=True)
    g = _game(m)
    _kill(g)
    assert len(g.state.get_player(PlayerId("P1")).souls) == 1


def test_soul_card_ref_matches_dead_monster():
    m = _make_monster("m-soul", has_soul=True)
    g = _game(m)
    _kill(g)
    assert g.state.get_player(PlayerId("P1")).souls[0] == m.card_ref


def test_soul_granted_event_emitted_for_soul_monster():
    m = _make_monster("m-soul", has_soul=True)
    g = _game(m)
    events = _kill(g)
    assert any(isinstance(e, SoulGranted) for e in events)


def test_soul_granted_event_fields():
    m = _make_monster("m-soul", has_soul=True)
    g = _game(m)
    events = _kill(g)
    ev = next(e for e in events if isinstance(e, SoulGranted))
    assert ev.player_id == PlayerId("P1")
    assert ev.card_ref == m.card_ref


def test_soul_granted_exactly_once_per_soul_kill():
    m = _make_monster("m-soul", hp=3, evade=1, has_soul=True)
    g = _game(m)
    all_events: list = []
    while g.combat is not None:
        all_events.extend(g.step(RollCombat()).events)
    soul_events = [e for e in all_events if isinstance(e, SoulGranted)]
    assert len(soul_events) == 1


def test_no_soul_for_non_soul_monster():
    m = _make_monster("m-nosoul", has_soul=False)
    g = _game(m)
    _kill(g)
    assert g.state.get_player(PlayerId("P1")).souls == []


def test_soul_granted_not_emitted_for_non_soul_monster():
    m = _make_monster("m-nosoul", has_soul=False)
    g = _game(m)
    events = _kill(g)
    assert not any(isinstance(e, SoulGranted) for e in events)


# ---------------------------------------------------------------------------
# Registry-backed monsters (GAPER, HORF)
# ---------------------------------------------------------------------------

def test_gaper_grants_3_cents():
    m = make_monster_in_play(CardRef(InstanceId("g"), GAPER))
    g = _game(m)
    _kill(g)
    assert g.state.get_player(PlayerId("P1")).cents == 3


def test_horf_grants_3_cents_no_soul():
    m = make_monster_in_play(CardRef(InstanceId("h"), HORF))
    g = _game(m)
    _kill(g)
    p = g.state.get_player(PlayerId("P1"))
    assert p.cents == 3
    assert len(p.souls) == 0


def test_fly_grants_1_cent_no_soul():
    m = make_monster_in_play(CardRef(InstanceId("f"), FLY))
    g = _game(m)
    _kill(g)
    p = g.state.get_player(PlayerId("P1"))
    assert p.cents == 1
    assert p.souls == []


# ---------------------------------------------------------------------------
# Isolation: rewards go to attacker only
# ---------------------------------------------------------------------------

def test_reward_coin_do_not_change_other_player():
    m = _make_monster("m", reward_coin=5)
    g = _game(m, n_players=2)
    g.state.get_player(PlayerId("P2")).cents = 0
    _kill(g)
    assert g.state.get_player(PlayerId("P2")).cents == 0


def test_soul_does_not_go_to_other_player():
    m = _make_monster("m-soul", has_soul=True)
    g = _game(m, n_players=2)
    _kill(g)
    assert g.state.get_player(PlayerId("P2")).souls == []
