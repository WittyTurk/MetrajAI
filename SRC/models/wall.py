# -*- coding: utf-8 -*-

from dataclasses import dataclass
from SRC.models.point import Point
from math import atan2


@dataclass(slots=True)
class Wall:

    id: int

    start: Point
    end: Point

    layer: str = ""
    entity_type: str = ""
    source_handle: str = ""

    # Duvar kalınlığı (mm)
    thickness: float = 0.0

    @property
    def length(self):
        return self.start.distance_to(self.end)

    @property
    def angle(self):
        return atan2(
            self.end.y - self.start.y,
            self.end.x - self.start.x
        )

    @property
    def midpoint(self):
        return Point(
            (self.start.x + self.end.x) / 2,
            (self.start.y + self.end.y) / 2
        )

    @property
    def is_horizontal(self):
        return abs(self.start.y - self.end.y) < 1.0

    @property
    def is_vertical(self):
        return abs(self.start.x - self.end.x) < 1.0

    @property
    def x_range(self):
        return (
            min(self.start.x, self.end.x),
            max(self.start.x, self.end.x)
        )

    @property
    def y_range(self):
        return (
            min(self.start.y, self.end.y),
            max(self.start.y, self.end.y)
        )

    def __repr__(self):
        return (
            f"Wall("
            f"id={self.id}, "
            f"start=({self.start.x:.1f}, {self.start.y:.1f}), "
            f"end=({self.end.x:.1f}, {self.end.y:.1f}), "
            f"length={self.length:.1f}, "
            f"thickness={self.thickness:.1f})"
        )