# -*- coding: utf-8 -*-
"""
Geometry3

Topology Vertex
"""

from __future__ import annotations

from dataclasses import dataclass, field

@dataclass(slots=True)
class Vertex:
    """
    Topological vertex.

    Bir Vertex;

    - tek bir koordinatı temsil eder
    - birden fazla HalfEdge'e bağlı olabilir
    - daha sonra Face oluştururken kullanılacaktır.
    """

    id: int

    x: float
    y: float

    incident_edges: list[int] = field(default_factory=list)

    # ---------------------------------------------------------

    @property
    def point(self):

        return (self.x, self.y)

    # ---------------------------------------------------------

    @property
    def degree(self):

        return len(self.incident_edges)

    # ---------------------------------------------------------

    def add_incident_edge(self, edge_id: int):

        if edge_id not in self.incident_edges:
            self.incident_edges.append(edge_id)

    # ---------------------------------------------------------

    def remove_incident_edge(self, edge_id: int):

        if edge_id in self.incident_edges:
            self.incident_edges.remove(edge_id)

    # ---------------------------------------------------------

    def distance_to(self, other: "Vertex") -> float:

        dx = self.x - other.x
        dy = self.y - other.y

        return (dx * dx + dy * dy) ** 0.5

    # ---------------------------------------------------------

    def is_same(self, other: "Vertex", tolerance: float = 1e-6) -> bool:

        return self.distance_to(other) <= tolerance

    # ---------------------------------------------------------

    def as_tuple(self):

        return (
            self.x,
            self.y
        )

    # ---------------------------------------------------------

    def __hash__(self):

        return hash(
            (
                round(self.x, 6),
                round(self.y, 6)
            )
        )

    # ---------------------------------------------------------

    def __repr__(self):

        return (
            f"Vertex("
            f"id={self.id}, "
            f"x={self.x:.3f}, "
            f"y={self.y:.3f}, "
            f"degree={self.degree})"
        )
