"""
Sprint 14 acceptance tests — Butter Bean cancel + combat miss damage on stack.

R14.1 — Combat miss damage is pushed onto the stack instead of applied
         synchronously in resolve_roll().  CombatMissDamageEffect fizzles if
         combat ends before it resolves (e.g. a Bomb kills the monster first).

R14.2 — Soul Heart can target a monster slot, granting it 1 prevent_damage.
         DealDamageToMonsterEffect (Bomb) consumes prevent_damage first.

R14.3 — BUTTER_BEAN loot card + CancelStackItemEffect: targets a StackItemTarget
         (a live stack item by ID) and removes it from the stack without resolving.

The five tests exercise every stopping point in the following action sequence:

  A (1/2 HP) vs Fly (1 HP, evade=7 — guaranteed miss, attack=1)
    RollCombat → miss → CombatMissDamageEffect(A, 1) on stack
    A plays Bomb  → Fly         (test 2: Bomb kills Fly; miss damage fizzles → A lives)
    B taps + SH → Fly           (test 3: SH absorbs Bomb; miss damage kills A)
    A taps + BB → SH            (test 4: BB cancels SH; Bomb kills Fly; miss damage fizzles)
    C taps + BB → BB_A          (test 5: BB_C cancels BB_A; SH restored; miss damage kills A)
"""
from __future__ import annotations

from foursouls.cards.loot import BOMB_BANG, BUTTER_BEAN, SOUL_HEART
from foursouls.engine.events import EffectFizzled, StackItemCancelled
from foursouls.engine.game_loop import Game
from foursouls.engine.game_zones import GameZones
from foursouls.engine.rng import RNG
from foursouls.engine.zones import DeckZone, DiscardZone, SlotsZone
from foursouls.model.commands import (
    ActivateCharacterAbility,
    AttackMonster,
    PassPriority,
    PlayLoot,
    RollCombat,
)
from foursouls.model.game_state import GameState
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.monster_in_play import MonsterInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId
from foursouls.model.target import MonsterTarget, PlayerTarget, StackItemTarget


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

P1 = PlayerId("P1")
P2 = PlayerId("P2")
P3 = PlayerId("P3")


def _ref(name: str, card_id: CardId | None = None) -> CardRef:
    return CardRef(InstanceId(name), card_id)


def _char(name: str) -> ItemInPlay:
    """Untapped character item."""
    return ItemInPlay(card_ref=CardRef(InstanceId(name)))


def _fly(name: str = "fly") -> MonsterInPlay:
    """1 HP, evade=7 (impossible to hit), attack=1 on miss."""
    return MonsterInPlay(
        card_ref=_ref(name),
        base_hp=1,
        current_hp=1,
        evade=7,       # any d6 roll (1–6) is a miss
        attack=1,
        reward_coin=0,
        has_soul=False,
    )


def _make_zones(fly: MonsterInPlay) -> GameZones:
    ms: SlotsZone[MonsterInPlay] = SlotsZone(size=2)
    ms.set(0, fly)
    return GameZones(
        loot_deck=DeckZone(),
        loot_discard=DiscardZone(),
        treasure_deck=DeckZone(),
        treasure_discard=DiscardZone(),
        monster_deck=DeckZone(),
        monster_discard=DiscardZone(),
        shop_slots=SlotsZone(size=2),
        monster_slots=ms,
    )


def _base_game() -> tuple[Game, MonsterInPlay]:
    """
    3-player game in ACTION phase; A has 1/2 HP and is the active player.
    All players have untapped characters.
    Returns (game, fly_reference).
    The fly is already in slot 0.
    """
    p1 = PlayerState(player_id=P1, max_hp=2, hp=1)
    p2 = PlayerState(player_id=P2, max_hp=6, hp=6)
    p3 = PlayerState(player_id=P3, max_hp=6, hp=6)
    p1.character = _char("char-p1")
    p2.character = _char("char-p2")
    p3.character = _char("char-p3")

    state = GameState.from_players([p1, p2, p3], active_player_id=P1)
    state.phase = Phase.ACTION

    fly = _fly()
    g = Game(state=state, zones=_make_zones(fly), rng=RNG(seed=0))

    # Grant P1 1 loot play (needed for Bomb and Butter Bean plays)
    g.state.turn_flags.loot_plays_allowed = 1

    return g, fly


def _resolve3(g: Game) -> list:
    """Pass priority for all three players, resolving the top stack item."""
    all_events: list = []
    for _ in range(3):
        r = g.step(PassPriority())
        all_events.extend(r.events)
    return all_events


def _attack_and_roll(g: Game) -> None:
    """Declare attack on slot 0, then roll (guaranteed miss)."""
    g.step(AttackMonster(slot_index=0))
    g.step(RollCombat())
    # After roll: CombatMissDamageEffect is now on the stack; priority at P1.


# ---------------------------------------------------------------------------
# Test 1 — No response: miss damage resolves and kills A
# ---------------------------------------------------------------------------

def test_miss_damage_applies_if_no_response():
    """CombatMissDamageEffect resolves normally when no one responds."""
    g, fly = _base_game()
    p1 = g.state.get_player(P1)

    _attack_and_roll(g)

    # Stack: [CombatMissDamageEffect(A, 1)]
    # All three players pass → effect resolves → A takes 1 damage → A at 0 HP
    _resolve3(g)

    assert p1.hp == 0, f"A should be dead (hp=0), got {p1.hp}"
    assert g.combat is None, "Combat should have cleared when A died"


# ---------------------------------------------------------------------------
# Test 2 — Bomb kills Fly first; miss damage fizzles; A survives
# ---------------------------------------------------------------------------

def test_bomb_kills_fly_and_miss_damage_fizzles():
    """
    A plays Bomb on Fly.  When Bomb resolves, Fly dies and combat ends
    (CombatState.is_active = False).  The CombatMissDamageEffect below it
    on the stack then fizzles — A takes no damage and lives.
    """
    g, fly = _base_game()
    p1 = g.state.get_player(P1)
    bomb = _ref("bomb-a", BOMB_BANG)
    p1.hand.append(bomb)

    _attack_and_roll(g)

    # Stack: [CombatMissDamageEffect]
    # A plays Bomb → Fly.  Stack: [CombatMissDamage, Bomb→Fly]
    g.step(PlayLoot(card_ref=bomb, target=MonsterTarget(slot_index=0)))

    # All pass → Bomb resolves: Fly at 0 HP → combat ends (is_active=False)
    _resolve3(g)

    assert g.combat is None, "Fly should have died; combat cleared"
    assert g.zones.monster_slots.get(0) is None, "Fly's slot should be empty (empty deck)"

    # All pass → CombatMissDamageEffect.validate() → False → fizzled
    fizzle_events = _resolve3(g)

    assert p1.hp == 1, f"A should be alive (hp=1), got {p1.hp}"
    assert any(isinstance(e, EffectFizzled) for e in fizzle_events), (
        "CombatMissDamageEffect should have fizzled"
    )


# ---------------------------------------------------------------------------
# Test 3 — B's Soul Heart shields Fly; Bomb absorbed; miss damage kills A
# ---------------------------------------------------------------------------

def test_soul_heart_on_fly_absorbs_bomb_then_miss_damage_kills_a():
    """
    B taps their character to gain an extra loot play, then plays Soul Heart
    targeting the Fly (adding 1 prevent_damage to the monster).
    The Bomb damage is absorbed, Fly survives.  The miss damage then lands on A.
    """
    g, fly = _base_game()
    p1 = g.state.get_player(P1)
    p2 = g.state.get_player(P2)

    bomb = _ref("bomb-b", BOMB_BANG)
    soul_heart = _ref("sh-b", SOUL_HEART)
    p1.hand.append(bomb)
    p2.hand.append(soul_heart)

    _attack_and_roll(g)

    # A plays Bomb targeting Fly.  Stack: [CombatMissDamage, Bomb→Fly]
    g.step(PlayLoot(card_ref=bomb, target=MonsterTarget(slot_index=0)))

    # A passes → B has priority
    g.step(PassPriority())

    # B taps character → GrantExtraLootPlay(B) on stack
    g.step(ActivateCharacterAbility())
    # All three pass → GrantExtraLootPlay(B) resolves; B gets 1 extra loot play
    _resolve3(g)

    # B plays Soul Heart targeting the Fly.  Stack: [CombatMissDamage, Bomb→Fly, SH→Fly]
    # (A has priority after SH is pushed — priority resets to active player)
    g.step(PassPriority())   # A passes → B has priority
    g.step(PlayLoot(card_ref=soul_heart, target=MonsterTarget(slot_index=0)))

    # All pass → SH(Fly) resolves: Fly.prevent_damage = 1
    _resolve3(g)
    assert fly.prevent_damage == 1

    # All pass → Bomb(Fly) resolves: 1 damage absorbed → Fly at 1 HP
    _resolve3(g)
    assert fly.current_hp == 1, "Fly should survive (Bomb absorbed by Soul Heart)"
    assert fly.prevent_damage == 0

    # All pass → CombatMissDamageEffect resolves: A takes 1 damage → dies
    _resolve3(g)

    assert p1.hp == 0, f"A should be dead, got hp={p1.hp}"
    assert g.combat is None, "Combat cleared when A died"


# ---------------------------------------------------------------------------
# Test 4 — A's Butter Bean cancels SH; Bomb kills Fly; miss damage fizzles
# ---------------------------------------------------------------------------

def test_butter_bean_cancels_soul_heart_then_bomb_kills_fly():
    """
    After B plays SH on Fly, A taps their character and plays Butter Bean
    targeting B's Soul Heart.  BB removes SH from the stack.
    Bomb then kills Fly; CombatMissDamageEffect fizzles; A lives.
    """
    g, fly = _base_game()
    p1 = g.state.get_player(P1)
    p2 = g.state.get_player(P2)

    bomb = _ref("bomb-c", BOMB_BANG)
    soul_heart = _ref("sh-c", SOUL_HEART)
    butter_bean_a = _ref("bb-a", BUTTER_BEAN)
    p1.hand.extend([bomb, butter_bean_a])
    p2.hand.append(soul_heart)

    _attack_and_roll(g)

    # A plays Bomb.  Stack: [CombatMissDamage, Bomb]
    g.step(PlayLoot(card_ref=bomb, target=MonsterTarget(slot_index=0)))

    # A passes → B gets extra loot, plays SH → Stack: [CombatMissDamage, Bomb, SH(Fly)]
    g.step(PassPriority())
    g.step(ActivateCharacterAbility())  # B taps
    _resolve3(g)                         # GrantExtraLoot(B) resolves

    g.step(PassPriority())   # A passes → B has priority
    g.step(PlayLoot(card_ref=soul_heart, target=MonsterTarget(slot_index=0)))
    sh_stack_id = g.stack.top().stack_id   # capture SH's stack ID before responding

    # A taps → gets extra loot.  Stack: [CombatMissDamage, Bomb, SH, GrantExtraLoot(A)]
    g.step(ActivateCharacterAbility())
    _resolve3(g)   # GrantExtraLoot(A) resolves; A gets 1 extra loot play

    # A plays Butter Bean targeting SH.  Stack: [CombatMissDamage, Bomb, SH, BB_A]
    g.step(PlayLoot(card_ref=butter_bean_a, target=StackItemTarget(stack_id=sh_stack_id)))

    # All pass → BB_A resolves: SH cancelled and removed from stack
    cancel_events = _resolve3(g)
    assert any(isinstance(e, StackItemCancelled) for e in cancel_events), (
        "BB should have emitted StackItemCancelled"
    )
    assert not g.stack.contains(sh_stack_id), "SH should no longer be on the stack"

    # All pass → Bomb resolves: Fly at 0 HP → combat ends
    _resolve3(g)
    assert g.combat is None

    # All pass → CombatMissDamageEffect fizzles
    fizzle_events = _resolve3(g)
    assert any(isinstance(e, EffectFizzled) for e in fizzle_events)

    assert p1.hp == 1, f"A should be alive, got hp={p1.hp}"


# ---------------------------------------------------------------------------
# Test 5 — C's Butter Bean cancels A's BB; SH restored; miss damage kills A
# ---------------------------------------------------------------------------

def test_counter_butter_bean_restores_soul_heart_and_a_dies():
    """
    C taps and plays Butter Bean cancelling A's Butter Bean.
    B's SH on Fly is no longer cancelled, so it resolves: Fly.prevent_damage=1.
    The Bomb damage is absorbed; Fly survives.
    CombatMissDamageEffect then applies: A takes 1 damage and dies.
    """
    g, fly = _base_game()
    p1 = g.state.get_player(P1)
    p2 = g.state.get_player(P2)
    p3 = g.state.get_player(P3)

    bomb = _ref("bomb-d", BOMB_BANG)
    soul_heart = _ref("sh-d", SOUL_HEART)
    butter_bean_a = _ref("bb-d1", BUTTER_BEAN)
    butter_bean_c = _ref("bb-d2", BUTTER_BEAN)
    p1.hand.extend([bomb, butter_bean_a])
    p2.hand.append(soul_heart)
    p3.hand.append(butter_bean_c)

    _attack_and_roll(g)

    # A plays Bomb
    g.step(PlayLoot(card_ref=bomb, target=MonsterTarget(slot_index=0)))

    # B taps + SH → Fly
    g.step(PassPriority())               # A → B
    g.step(ActivateCharacterAbility())   # B taps
    _resolve3(g)                          # GrantExtraLoot(B) resolves
    g.step(PassPriority())               # A → B
    g.step(PlayLoot(card_ref=soul_heart, target=MonsterTarget(slot_index=0)))
    sh_stack_id = g.stack.top().stack_id

    # A taps + BB → SH
    g.step(ActivateCharacterAbility())   # A taps
    _resolve3(g)                          # GrantExtraLoot(A) resolves
    g.step(PlayLoot(card_ref=butter_bean_a, target=StackItemTarget(stack_id=sh_stack_id)))
    bb_a_stack_id = g.stack.top().stack_id

    # A passes, B passes → C has priority
    g.step(PassPriority())   # A → B
    g.step(PassPriority())   # B → C

    # C taps + BB → BB_A
    g.step(ActivateCharacterAbility())   # C taps
    _resolve3(g)                          # GrantExtraLoot(C) resolves
    g.step(PassPriority())               # A → B
    g.step(PassPriority())               # B → C
    g.step(PlayLoot(card_ref=butter_bean_c, target=StackItemTarget(stack_id=bb_a_stack_id)))

    # --- All players pass: resolve top → bottom ---

    # BB_C resolves: BB_A removed from stack
    cancel1 = _resolve3(g)
    assert any(isinstance(e, StackItemCancelled) for e in cancel1), (
        "BB_C should have cancelled BB_A"
    )
    assert not g.stack.contains(bb_a_stack_id), "BB_A should be gone"

    # SH(Fly) resolves: Fly gains 1 prevent_damage
    _resolve3(g)
    assert fly.prevent_damage == 1, "Soul Heart should have shielded the Fly"

    # Bomb(Fly) resolves: absorbed by prevent_damage
    _resolve3(g)
    assert fly.current_hp == 1, "Fly should survive (Bomb absorbed)"

    # CombatMissDamageEffect resolves: A takes 1 damage
    _resolve3(g)

    assert p1.hp == 0, f"A should be dead (hp=0), got {p1.hp}"
    assert g.zones.monster_slots.get(0) is fly, "Fly should still be in slot 0"
