# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CostItem:

    # Identity
    id: int

    # Source
    quantity_item_id: int

    # Semantic
    category: str = ""
    description: str = ""

    # Pricing
    unit: str = ""
    quantity: float = 0.0
    unit_price: float = 0.0

    # Cost
    total_cost: float = 0.0

    # Project
    price_book: str | None = None
    price_year: int | None = None

    # Metadata
    properties: dict[str, Any] = field(default_factory=dict)

    # Status
    is_valid: bool = True
