# -*- coding: utf-8 -*-

from dataclasses import dataclass, field

from SRC.models.point import Point


@dataclass
class Node:

    id: int

    point: Point

    connected_walls: list = field(default_factory=list)

    def __repr__(self):

        return (
            f"Node("
            f"id={self.id}, "
            f"x={self.point.x:.2f}, "
            f"y={self.point.y:.2f}, "
            f"walls={len(self.connected_walls)})"
        )
