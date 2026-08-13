from __future__ import annotations

from dataclasses import dataclass
from math import hypot


@dataclass(slots=True, frozen=True)
class Point:
    x: float
    y: float

    def distance_to(self, other: "Point") -> float:
        return hypot(
            self.x - other.x,
            self.y - other.y,
        )