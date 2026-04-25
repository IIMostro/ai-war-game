"""models.py — Domain data classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Faction:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class City:
    id: str
    name: str
    x: int
    y: int
    terrain: str
    owner_faction_id: str


@dataclass(slots=True)
class General:
    id: str
    name: str
    war: int
    cmd: int
    intel: int
    politics: int
    charm: int
    loyalty: int | None
    troops: int
    food: int
    position_city_id: str
    faction_id: str
    is_player: bool
    personality: dict[str, Any] = field(default_factory=dict)
