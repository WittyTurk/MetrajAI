# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from SRC.models.point import Point


@dataclass(slots=True)
class Window:

    # Identity
    id: int

    # Geometry
    position: Point
    width: float
    height: float
    rotation: float

    # Topology
    wall_id: int | None = None
    room_ids: list[int] = field(default_factory=list)

    # Semantic
    window_no: str | None = None
    window_type: str | None = None

    # Project
    level_id: int | None = None
    building_id: int | None = None

    # Status
    is_valid: bool = True

    # Metadata
    properties: dict[str, Any] = field(default_factory=dict)
