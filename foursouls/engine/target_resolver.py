from __future__ import annotations

from dataclasses import dataclass

from foursouls.engine.events import (
    CombatRollResult,
    DamageDealt,
    ItemActivated,
    MonsterDied,
)
from foursouls.engine.zone_identity import ZoneIdentityRegistry
from foursouls.model.abilities import (
    AbilityContext,
    AbilityInstance,
    ActivePlayerSelector,
    AllMonstersSelector,
    ChosenItemSelector,
    ChosenPlayerSelector,
    ChosenSoulSelector,
    ControllerSelector,
    RandomOtherPlayerSelector,
    SourceSelector,
    TargetSelectorDefinition,
    TriggeringPlayerSelector,
    TriggerTargetSelector,
)
from foursouls.model.refs import PlayerId
from foursouls.model.target import (
    AnyTarget,
    ItemTarget,
    MonsterTarget,
    PlayerTarget,
    SoulTarget,
)


class TargetResolutionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TargetResolution:
    selected: tuple[AnyTarget, ...] = ()
    candidates: tuple[AnyTarget, ...] = ()
    chooser_id: PlayerId | None = None

    @property
    def requires_choice(self) -> bool:
        return self.chooser_id is not None


class TargetResolver:
    def __init__(self, zone_identities: ZoneIdentityRegistry) -> None:
        self.zone_identities = zone_identities

    def resolve(
        self,
        selector: TargetSelectorDefinition,
        ability: AbilityInstance,
        context: AbilityContext,
        game,
    ) -> TargetResolution:
        if isinstance(selector, SourceSelector):
            target = self.zone_identities.resolve(
                ability.source.zone_entry_id
            )
            if target is None:
                raise TargetResolutionError("ability source is no longer active")
            return TargetResolution(selected=(target,))

        if isinstance(selector, ControllerSelector):
            return TargetResolution(
                selected=(PlayerTarget(ability.controller_id),)
            )

        if isinstance(selector, ActivePlayerSelector):
            return TargetResolution(
                selected=(PlayerTarget(game.state.active_player_id),)
            )

        if isinstance(selector, TriggeringPlayerSelector):
            return TargetResolution(
                selected=(PlayerTarget(_triggering_player(context)),)
            )

        if isinstance(selector, TriggerTargetSelector):
            return TargetResolution(
                selected=(_trigger_target(context),)
            )

        if isinstance(selector, RandomOtherPlayerSelector):
            candidates = [
                PlayerTarget(player_id)
                for player_id in game.state.turn_order
                if player_id != ability.controller_id
            ]
            if not candidates:
                raise TargetResolutionError("no other player is available")
            return TargetResolution(
                selected=(game.rng.choice(candidates),)
            )

        if isinstance(selector, ChosenPlayerSelector):
            return TargetResolution(
                candidates=tuple(
                    PlayerTarget(player_id)
                    for player_id in game.state.turn_order
                ),
                chooser_id=ability.controller_id,
            )

        if isinstance(selector, ChosenItemSelector):
            candidates = tuple(
                ItemTarget(player_id, item.card_ref)
                for player_id in game.state.turn_order
                for item in game.state.get_player(player_id).items
                if not item.eternal
            )
            return TargetResolution(
                candidates=candidates,
                chooser_id=context.controller_id,
            )

        if isinstance(selector, ChosenSoulSelector):
            try:
                player_target = context.selected_targets[
                    selector.player_target_index
                ]
            except IndexError as exc:
                raise TargetResolutionError(
                    "chosen_soul requires a resolved player target"
                ) from exc
            if not isinstance(player_target, PlayerTarget):
                raise TargetResolutionError(
                    "chosen_soul player target is not a PlayerTarget"
                )
            player = game.state.get_player(player_target.player_id)
            return TargetResolution(
                candidates=tuple(
                    SoulTarget(player_target.player_id, card_ref)
                    for card_ref in player.souls
                ),
                chooser_id=player_target.player_id,
            )

        if isinstance(selector, AllMonstersSelector):
            if game.zones is None:
                raise TargetResolutionError("game zones are not initialized")
            targets = []
            for slot_index in game.zones.monster_slots.filled_indices():
                monster = game.zones.monster_slots.get(slot_index)
                if monster is not None and not monster.is_event:
                    targets.append(MonsterTarget(slot_index))
            return TargetResolution(selected=tuple(targets))

        raise TypeError(f"Unsupported selector: {type(selector).__name__}")


def _triggering_player(context: AbilityContext) -> PlayerId:
    event = context.triggering_event
    if isinstance(event, ItemActivated):
        return event.player_id
    if isinstance(event, CombatRollResult):
        return event.attacker_id
    if isinstance(event, MonsterDied):
        return event.attacker_id
    if isinstance(event, DamageDealt) and event.source_player_id is not None:
        return event.source_player_id
    raise TargetResolutionError(
        f"{type(event).__name__} has no unambiguous triggering player"
    )


def _trigger_target(context: AbilityContext) -> AnyTarget:
    event = context.triggering_event
    if isinstance(event, DamageDealt):
        if event.target_player_id is not None:
            return PlayerTarget(event.target_player_id)
        if event.target_monster_slot is not None:
            return MonsterTarget(event.target_monster_slot)
    raise TargetResolutionError(
        f"{type(event).__name__} has no supported target"
    )
