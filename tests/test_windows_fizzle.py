"""
S2.6 — tests for response windows, fizzle path, tap costs, and extra-loot integration.

Covers four areas that are distinct from the per-feature unit tests already in
test_loot_play.py and test_activated_abilities.py:

  1. Response window around loot: priority flow, stack gating, resolve timing.
  2. Fizzle path: PlayLootEffect delegates validate to inner; EffectFizzled fires,
     card stays in limbo, no state mutation.
  3. End-to-end extra-loot: activate ability → full response cycle → play two
     separate loot cards → quota exhausted.
  4. Tap-cost guarantees: cost is paid at activation time; the effect resolving
     (or not) cannot undo the tap.
"""
from agents.pass_bot import choose_command
from foursouls.cards.loot import BOMB_BANG, LOOT_COIN_1, LOOT_COIN_2
from foursouls.model.target import PlayerTarget
from foursouls.engine.events import EffectFizzled, StackItemResolved
from foursouls.engine.rng import RNG
from foursouls.model.commands import (
    ActivateCharacterAbility,
    EndTurn,
    PassPriority,
    PlayLoot,
)
from foursouls.model.effects import AlwaysFizzleEffect
from foursouls.model.game_state import GameState
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.phase import Phase
from foursouls.model.player_state import PlayerState
from foursouls.model.refs import CardId, CardRef, InstanceId, PlayerId
from foursouls.rulesets.common.effects import PlayLootEffect
from foursouls.rulesets.common.setup import setup_game


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ref(name: str, card_id: CardId) -> CardRef:
    return CardRef(InstanceId(name), card_id)


def _char(name: str) -> ItemInPlay:
    return ItemInPlay(card_ref=CardRef(InstanceId(name)))


def _make_cards(prefix: str, n: int) -> list[CardRef]:
    return [CardRef(InstanceId(f"{prefix}-{i}")) for i in range(n)]


def _game_at_action(*, with_character: bool = False, extra_hand: list[CardRef] = ()):
    p1 = PlayerState(player_id=PlayerId("P1"), max_hp=3, hp=3)
    p2 = PlayerState(player_id=PlayerId("P2"), max_hp=3, hp=3)
    if with_character:
        p1.character = _char("char-p1")
    state = GameState.from_players([p1, p2], active_player_id=PlayerId("P1"))
    g = setup_game(
        state,
        loot_cards=_make_cards("loot", 40),
        treasure_cards=_make_cards("treasure", 10),
        monster_cards=_make_cards("monster", 10),
        rng=RNG(seed=0),
    )
    while g.state.phase != Phase.ACTION:
        g.step(choose_command(g))
    for card in extra_hand:
        g.state.get_player(PlayerId("P1")).hand.append(card)
    return g


# ── 1. Response window ────────────────────────────────────────────────────────

class TestResponseWindow:

    def test_loot_on_stack_blocks_end_turn(self):
        """EndTurn must not be legal while a loot effect is on the stack."""
        coin = _ref("coin-w1", LOOT_COIN_1)
        g = _game_at_action(extra_hand=[coin])

        g.step(PlayLoot(card_ref=coin))

        assert not g.stack.empty()
        cmds = g.legal_commands()
        assert not any(isinstance(c, EndTurn) for c in cmds)

    def test_loot_stays_on_stack_after_one_pass(self):
        """Stack is not drained until ALL players have passed."""
        coin = _ref("coin-w2", LOOT_COIN_1)
        g = _game_at_action(extra_hand=[coin])

        g.step(PlayLoot(card_ref=coin))
        g.step(PassPriority())  # P1 passes — only one of two

        assert not g.stack.empty()

    def test_loot_resolves_after_full_pass_cycle(self):
        """Effect resolves when P1 and P2 have both passed."""
        coin = _ref("coin-w3", LOOT_COIN_1)
        g = _game_at_action(extra_hand=[coin])
        p1 = g.state.get_player(PlayerId("P1"))

        g.step(PlayLoot(card_ref=coin))
        g.step(PassPriority())  # P1
        events = g.step(PassPriority()).events  # P2 → all passed → resolves

        assert g.stack.empty()
        assert p1.cents == 1
        assert any(isinstance(e, StackItemResolved) for e in events)

    def test_priority_owner_after_play_is_active_player(self):
        """After PlayLoot, priority resets to the active player (P1)."""
        coin = _ref("coin-w4", LOOT_COIN_1)
        g = _game_at_action(extra_hand=[coin])

        g.step(PlayLoot(card_ref=coin))

        assert g.priority.current() == PlayerId("P1")

    def test_stack_item_label_identifies_played_card(self):
        coin = _ref("coin-w5", LOOT_COIN_1)
        g = _game_at_action(extra_hand=[coin])

        g.step(PlayLoot(card_ref=coin))

        assert g.stack.top().label == f"PlayLoot:{LOOT_COIN_1}"

    def test_response_window_bomb_resolves_after_full_cycle(self):
        """Bomb follows same pass-to-resolve pattern as coins."""
        bomb = _ref("bomb-w1", BOMB_BANG)
        g = _game_at_action(extra_hand=[bomb])
        p1 = g.state.get_player(PlayerId("P1"))
        hp_before = p1.hp

        g.step(PlayLoot(card_ref=bomb, target=PlayerTarget(PlayerId("P1"))))
        g.step(PassPriority())  # P1
        g.step(PassPriority())  # P2 → resolves

        assert p1.hp == hp_before - 1


# ── 2. Fizzle path ────────────────────────────────────────────────────────────

class TestFizzle:

    def _push_fizzling_loot(self, g, card_ref: CardRef):
        """
        Simulate a loot play whose inner effect always fizzles.
        Mirrors what on_play_loot does, but substitutes AlwaysFizzleEffect
        as the inner — representing a loot that targets an invalid game object
        (e.g., Bomb targeting a monster that was already removed from play).
        """
        active_id = g.state.active_player_id
        g.state.get_player(active_id).hand.remove(card_ref)
        g.state.turn_flags.loot_plays_used += 1
        effect = PlayLootEffect(
            card_ref=card_ref,
            inner=AlwaysFizzleEffect(),
            loot_discard=g.zones.loot_discard,
        )
        g.push_to_stack(
            controller_id=active_id,
            source=card_ref,
            effect=effect,
            label=f"PlayLoot:{card_ref.card_id}",
        )
        g.priority.reset_to(active_id)

    def test_fizzle_emits_effect_fizzled_event(self):
        coin = _ref("coin-fz1", LOOT_COIN_1)
        g = _game_at_action(extra_hand=[coin])

        self._push_fizzling_loot(g, coin)
        g.step(PassPriority())
        events = g.step(PassPriority()).events

        assert any(isinstance(e, EffectFizzled) for e in events)

    def test_fizzle_does_not_discard_card(self):
        """When inner fizzles, PlayLootEffect.apply is never called — card stays in limbo."""
        coin = _ref("coin-fz2", LOOT_COIN_1)
        g = _game_at_action(extra_hand=[coin])
        discard_before = len(g.zones.loot_discard.cards)

        self._push_fizzling_loot(g, coin)
        g.step(PassPriority())
        g.step(PassPriority())

        assert len(g.zones.loot_discard.cards) == discard_before  # card in limbo

    def test_fizzle_does_not_mutate_state(self):
        """State is unchanged when a loot effect fizzles."""
        coin = _ref("coin-fz3", LOOT_COIN_1)
        g = _game_at_action(extra_hand=[coin])
        p1 = g.state.get_player(PlayerId("P1"))
        cents_before = p1.cents

        self._push_fizzling_loot(g, coin)
        g.step(PassPriority())
        g.step(PassPriority())

        assert p1.cents == cents_before  # GainCentsEffect never ran

    def test_fizzle_uses_quota_slot(self):
        """The play quota is consumed at play time, not resolution — fizzle burns a slot."""
        coin = _ref("coin-fz4", LOOT_COIN_1)
        g = _game_at_action(extra_hand=[coin])

        self._push_fizzling_loot(g, coin)
        g.step(PassPriority())
        g.step(PassPriority())

        assert g.state.turn_flags.loot_plays_used == 1
        assert not any(isinstance(c, PlayLoot) for c in g.legal_commands())


# ── 3. End-to-end extra-loot integration ─────────────────────────────────────

class TestExtraLootIntegration:

    def test_activate_then_play_two_coins_grants_two_cents(self):
        coin1 = _ref("coin-el1", LOOT_COIN_1)
        coin2 = _ref("coin-el2", LOOT_COIN_2)
        g = _game_at_action(with_character=True, extra_hand=[coin1, coin2])
        p1 = g.state.get_player(PlayerId("P1"))

        # Activate character → grants +1 play
        g.step(ActivateCharacterAbility())
        g.step(PassPriority())  # P1
        g.step(PassPriority())  # P2 → GrantExtraLootPlay resolves
        assert g.state.turn_flags.loot_plays_allowed == 2

        # Play first coin
        g.step(PlayLoot(card_ref=coin1))
        g.step(PassPriority())
        g.step(PassPriority())
        assert p1.cents == 1
        assert g.state.turn_flags.loot_plays_used == 1

        # Play second coin
        g.step(PlayLoot(card_ref=coin2))
        g.step(PassPriority())
        g.step(PassPriority())
        assert p1.cents == 2
        assert g.state.turn_flags.loot_plays_used == 2

    def test_third_play_illegal_after_two_uses(self):
        coin1 = _ref("coin-el3", LOOT_COIN_1)
        coin2 = _ref("coin-el4", LOOT_COIN_2)
        coin3 = _ref("coin-el5", LOOT_COIN_1)
        g = _game_at_action(with_character=True, extra_hand=[coin1, coin2, coin3])

        g.step(ActivateCharacterAbility())
        g.step(PassPriority())
        g.step(PassPriority())

        g.step(PlayLoot(card_ref=coin1))
        g.step(PassPriority())
        g.step(PassPriority())

        g.step(PlayLoot(card_ref=coin2))
        g.step(PassPriority())
        g.step(PassPriority())

        # Quota exhausted — third play must be illegal
        cmds = g.legal_commands()
        assert not any(isinstance(c, PlayLoot) for c in cmds)

    def test_quota_resets_each_turn(self):
        """After EndTurn, loot_plays_used resets to 0 and allowed back to 1."""
        coin = _ref("coin-el6", LOOT_COIN_1)
        g = _game_at_action(with_character=True, extra_hand=[coin])

        # Use the default play
        g.step(PlayLoot(card_ref=coin))
        g.step(PassPriority())
        g.step(PassPriority())
        assert g.state.turn_flags.loot_plays_used == 1

        g.step(EndTurn())

        # Now it's P2's turn; on P2's turn the flags are reset
        assert g.state.turn_flags.loot_plays_used == 0
        assert g.state.turn_flags.loot_plays_allowed == 1


# ── 4. Tap-cost guarantees ────────────────────────────────────────────────────

class TestTapCost:

    def test_character_tapped_before_effect_resolves(self):
        """The tap is paid when ActivateCharacterAbility is submitted,
        not when the GrantExtraLootPlay effect resolves."""
        g = _game_at_action(with_character=True)
        char = g.state.get_player(PlayerId("P1")).character

        g.step(ActivateCharacterAbility())

        # Effect is on the stack — not resolved yet
        assert not g.stack.empty()
        # But the cost was already paid
        assert char.is_tapped

    def test_tapped_character_blocks_reactivation_while_effect_unresolved(self):
        """Cannot activate again even before the effect resolves."""
        g = _game_at_action(with_character=True)

        g.step(ActivateCharacterAbility())
        # Stack has GrantExtraLootPlay; character is tapped
        cmds = g.legal_commands()
        assert ActivateCharacterAbility() not in cmds

    def test_tapped_character_blocks_reactivation_after_resolution(self):
        """Cannot activate again after resolution — still tapped until next turn."""
        g = _game_at_action(with_character=True)

        g.step(ActivateCharacterAbility())
        g.step(PassPriority())
        g.step(PassPriority())  # resolves

        cmds = g.legal_commands()
        assert ActivateCharacterAbility() not in cmds

    def test_character_untaps_on_next_own_turn_after_activation(self):
        """After EndTurn, through P2's turn, back to P1 — character recharges."""
        g = _game_at_action(with_character=True)
        char = g.state.get_player(PlayerId("P1")).character

        g.step(ActivateCharacterAbility())
        g.step(PassPriority())
        g.step(PassPriority())  # resolve
        g.step(EndTurn())  # P2's turn begins

        # Still tapped — it's not P1's turn yet
        assert char.is_tapped

        # Drive through P2's full turn back to P1's START phase
        while g.state.active_player_id == PlayerId("P2"):
            g.step(choose_command(g))

        # Character untaps as soon as P1's turn begins (enter_start_phase)
        assert not char.is_tapped

        # Advance through P1's START phase (Loot1 resolves) into ACTION
        while g.state.phase != Phase.ACTION:
            g.step(choose_command(g))

        assert ActivateCharacterAbility() in g.legal_commands()
