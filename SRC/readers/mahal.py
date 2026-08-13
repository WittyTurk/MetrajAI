# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Mahal:
    """
    Mahal (oda / mekan).

    Kaynak:
      - Excel/CSV mahal listesi  → expected_area, kaplamalar
      - DXF mimari çizim         → measured_area (poligon), mahal_no text
    """

    id: int
    mahal_no: str
    mahal_name: str

    expected_area: float | None = None
    measured_area: float | None = None

    level_name: str | None = None
    building_name: str | None = None

    floor_finish: str | None = None
    wall_finish: str | None = None
    ceiling_finish: str | None = None
    skirting: str | None = None

    source: str = "list"
    layer: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    @property
    def area_m2(self) -> float | None:
        if self.measured_area is not None:
            return self.measured_area
        return self.expected_area