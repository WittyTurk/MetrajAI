# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Mahal:

    # Identity
    id: int

    # Semantic
    mahal_no: str
    mahal_name: str

    # Geometry
    expected_area: float | None = None

    # Project
    level_name: str | None = None
    building_name: str | None = None

    # Finishes
    floor_finish: str | None = None
    wall_finish: str | None = None
    ceiling_finish: str | None = None
    skirting: str | None = None

    # Metadata
    properties: dict[str, Any] = field(default_factory=dict)
