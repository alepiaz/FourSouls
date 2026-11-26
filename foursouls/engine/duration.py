from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MonsterStatDuration:
    zone_entry_id: str
    monster: object
    attack_delta: int
    evade_delta: int
    expires_turn: int


@dataclass(slots=True)
class DurationManager:
    _monster_stats: list[MonsterStatDuration] = field(default_factory=list)

    def register_monster_stats(
        self,
        *,
        zone_entry_id: str,
        monster: object,
        attack_delta: int,
        evade_delta: int,
        expires_turn: int,
    ) -> None:
        self._monster_stats.append(
            MonsterStatDuration(
                zone_entry_id=zone_entry_id,
                monster=monster,
                attack_delta=attack_delta,
                evade_delta=evade_delta,
                expires_turn=expires_turn,
            )
        )

    def expire_end_of_turn(self, turn_number: int) -> int:
        expiring = [
            item
            for item in self._monster_stats
            if item.expires_turn <= turn_number
        ]
        self._monster_stats = [
            item
            for item in self._monster_stats
            if item.expires_turn > turn_number
        ]
        for item in expiring:
            item.monster.attack_bonus -= item.attack_delta
            item.monster.evade_bonus -= item.evade_delta
        return len(expiring)

    def expire_zone_entry(self, zone_entry_id: str) -> int:
        expiring = [
            item
            for item in self._monster_stats
            if item.zone_entry_id == zone_entry_id
        ]
        self._monster_stats = [
            item
            for item in self._monster_stats
            if item.zone_entry_id != zone_entry_id
        ]
        for item in expiring:
            item.monster.attack_bonus -= item.attack_delta
            item.monster.evade_bonus -= item.evade_delta
        return len(expiring)

    def active_count(self) -> int:
        return len(self._monster_stats)
