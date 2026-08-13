# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass

from SRC.models.point import Point
from SRC.models.wall_component import Orientation


@dataclass
class WallAxis:

    id: int
    component_id: int
    orientation: Orientation
    thickness: float
    start: Point
    end: Point
    source_wall_ids: list[int]

    @property
    def length(self) -> float:

        return self.start.distance_to(self.end)

    def __repr__(self) -> str:

        return (
            "WallAxis("
            f"id={self.id}, "
            f"component_id={self.component_id}, "
            f"orientation='{self.orientation.value}', "
            f"thickness={self.thickness:.2f}, "
            f"start=({self.start.x:.2f}, {self.start.y:.2f}), "
            f"end=({self.end.x:.2f}, {self.end.y:.2f}), "
            f"length={self.length:.2f}, "
            f"source_wall_ids={self.source_wall_ids}"
            ")"
        )
