# -*- coding: utf-8 -*-
"""
Geometry3

Topology Node
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Node:
    """
    Topology graph node.

    Bir node;

    - bir koordinatı temsil eder
    - bir veya daha fazla edge'e bağlı olabilir
    - bir junction olabilir
    - daha sonra room oluştururken kullanılacaktır.
    """

    id: int

    x: float
    y: float

    edges: list[int] = field(default_factory=list)
    walls: list[int] = field(default_factory=list)
    rooms: list[int] = field(default_factory=list)

    # ---------------------------------------------------------

    @property
    def point(self):

        return (self.x, self.y)

    # ---------------------------------------------------------

    @property
    def degree(self):

        return len(self.edges)

    # ---------------------------------------------------------

    def add_edge(self, edge_id: int):

        if edge_id not in self.edges:
            self.edges.append(edge_id)

    # ---------------------------------------------------------

    def add_wall(self, wall_id: int):

        if wall_id not in self.walls:
            self.walls.append(wall_id)

    # ---------------------------------------------------------

    def add_room(self, room_id: int):

        if room_id not in self.rooms:
            self.rooms.append(room_id)

    # ---------------------------------------------------------

    def distance_to(self, other: "Node"):

        dx = self.x - other.x
        dy = self.y - other.y

        return (dx * dx + dy * dy) ** 0.5

    # ---------------------------------------------------------

    def is_same(self, other: "Node", tolerance=1e-6):

        return self.distance_to(other) <= tolerance

    # ---------------------------------------------------------

    def __repr__(self):

        return (
            f"Node("
            f"id={self.id}, "
            f"x={self.x:.3f}, "
            f"y={self.y:.3f}, "
            f"degree={self.degree})"
        )
