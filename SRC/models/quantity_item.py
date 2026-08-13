# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class QuantityItem:

    # Identity
    id: int

    # Source
    room_id: int | None = None
    wall_id: int | None = None
    door_id: int | None = None
    window_id: int | None = None

    # Semantic
    category: str = ""
    description: str = ""

    # Quantity
    quantity: float = 0.0
    unit: str = ""

    # Metadata
    properties: dict[str, Any] = field(default_factory=dict)

    # Status
    is_valid: bool = True
