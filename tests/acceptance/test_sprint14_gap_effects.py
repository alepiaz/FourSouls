from foursouls.cards.monsters import FLY
from foursouls.cli.app import build_demo_game
from foursouls.model.commands import AttackMonster, AttackMonsterDeck, EndTurn
from foursouls.model.item_in_play import ItemInPlay
from foursouls.model.phase import Phase
from foursouls.model.refs import CardRef, InstanceId
from foursouls.rulesets.common.combat import place_monster_card
from foursouls.rulesets.common.effects import DestroyItemEffect, ForceAttackEffect, HealEffect


def test_heal_caps_hp_and_fizzles_on_dead_player():
    game = build_demo_game(seed=7)
    player = game.state.get_player(game.state.active_player_id)
    effect = HealEffect(player.player_id, 5)
    assert effect.validate(game.state)
    effect.apply(game.state)
    assert player.hp == player.max_hp
    player.hp = 0
    assert not effect.validate(game.state)


def test_destroy_item_respects_eternals_and_moves_card_to_discard():
    game = build_demo_game(seed=7)
    player = game.state.get_player(game.state.active_player_id)
    ref = CardRef(InstanceId("test-item"))
    item = ItemInPlay(card_ref=ref, eternal=True)
    player.items.append(item)
    discard = game.zones.treasure_discard
    effect = DestroyItemEffect(player.player_id, ref, discard)
    assert not effect.validate(game.state)
    item.eternal = False
    assert effect.validate(game.state)
    effect.apply(game.state)
    assert item not in player.items
    assert discard.cards.count(ref) == 1
    assert not effect.validate(game.state)


def test_forced_attack_is_restricted_and_consumed_on_declaration():
    game = build_demo_game(seed=7)
    while not game.stack.empty():
        game.stack.pop()
    game.state.phase = Phase.ACTION
    ref = CardRef(InstanceId("forced-fly"), FLY)
    place_monster_card(game, 0, ref)
    flags = game.state.turn_flags
    flags.attack_used = True
    effect = ForceAttackEffect(0, ref, game.zones.monster_slots)
    assert effect.validate(game.state)
    effect.apply(game.state)
    commands = game.legal_commands()
    assert AttackMonster(0) in commands
    assert AttackMonster(1) not in commands
    assert AttackMonsterDeck() not in commands
    assert EndTurn() not in commands
    game.step(AttackMonster(0))
    assert flags.forced_attack_slot is None
    assert game.combat.monster_ref == ref
