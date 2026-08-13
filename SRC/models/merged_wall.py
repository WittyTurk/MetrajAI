# -*- coding: utf-8 -*-

from dataclasses import dataclass
from math import atan2

from SRC.models.point import Point


@dataclass
class MergedWall:

    id: int
    start: Point
    end: Point
    
    thickness: float

    source_pair: object

    start_node: int | None = None
    end_node: int | None = None


    @property
    def length(self):

        return self.start.distance_to(
            self.end
        )

    @property
    def angle(self):

        return atan2(
            self.end.y - self.start.y,
            self.end.x - self.start.x
        )

    @property
    def is_horizontal(self):

        return abs(self.start.y - self.end.y) < 1.0

    @property
    def is_vertical(self):

        return abs(self.start.x - self.end.x) < 1.0

    @property
    def corners(self):

        if self.is_horizontal:

            t = self.thickness / 2

            return [

                Point(self.start.x, self.start.y - t),
                Point(self.end.x,   self.end.y   - t),
                Point(self.end.x,   self.end.y   + t),
                Point(self.start.x, self.start.y + t)

            ]

        if self.is_vertical:

            t = self.thickness / 2

            return [

                Point(self.start.x - t, self.start.y),
                Point(self.start.x + t, self.start.y),
                Point(self.end.x   + t, self.end.y),
                Point(self.end.x   - t, self.end.y)

            ]

        return []

    def __repr__(self):

        return (
            f"MergedWall("
            f"id={self.id}, "
            f"length={self.length:.2f}, "
            f"thickness={self.thickness:.2f})"
        )
