from __future__ import annotations

from dataclasses import dataclass, field

from foursouls.model.abilities import AbilitySource
from foursouls.model.refs import CardRef, InstanceId
from foursouls.model.target import AnyTarget


@dataclass(slots=True)
class ZoneIdentityRegistry:
    _generation_by_instance: dict[InstanceId, int] = field(default_factory=dict)
    _active_targets: dict[str, AnyTarget] = field(default_factory=dict)
    _active_by_instance: dict[InstanceId, str] = field(default_factory=dict)

    def enter(
        self,
        card_ref: CardRef,
        *,
        zone: str,
        target: AnyTarget,
    ) -> AbilitySource:
        if card_ref.instance_id in self._active_by_instance:
            raise ValueError(
                f"card instance {card_ref.instance_id!r} is already in an active zone"
            )

        generation = self._generation_by_instance.get(card_ref.instance_id, 0) + 1
        self._generation_by_instance[card_ref.instance_id] = generation
        zone_entry_id = f"{card_ref.instance_id}:{zone}:{generation}"
        self._active_targets[zone_entry_id] = target
        self._active_by_instance[card_ref.instance_id] = zone_entry_id
        return AbilitySource(
            card_ref=card_ref,
            zone=zone,
            zone_entry_id=zone_entry_id,
        )

    def leave(self, zone_entry_id: str) -> bool:
        target = self._active_targets.pop(zone_entry_id, None)
        if target is None:
            return False

        for instance_id, active_id in tuple(self._active_by_instance.items()):
            if active_id == zone_entry_id:
                del self._active_by_instance[instance_id]
                break
        return True

    def resolve(self, zone_entry_id: str) -> AnyTarget | None:
        return self._active_targets.get(zone_entry_id)

    def is_active(self, zone_entry_id: str) -> bool:
        return zone_entry_id in self._active_targets

    @property
    def active_zone_entry_ids(self) -> frozenset[str]:
        return frozenset(self._active_targets)
