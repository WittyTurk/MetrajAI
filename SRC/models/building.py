# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Building:

    # Identity
    id: int
    name: str | None = None

    # Geometry
    room_ids: list[int] = field(default_factory=list)
    wall_ids: list[int] = field(default_factory=list)
    door_ids: list[int] = field(default_factory=list)
    window_ids: list[int] = field(default_factory=list)

    # Project
    level_ids: list[int] = field(default_factory=list)

    # Semantic
    properties: dict[str, Any] = field(default_factory=dict)

    # Status
    is_valid: bool = True
