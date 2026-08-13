# -*- coding: utf-8 -*-
"""
Geometry3

Topology Edge
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Edge:
    """
    Graph edge.

    Bir edge iki node'u birbirine bağlar.

    Genellikle bir duvar eksenini temsil eder.
    """

    id: int

    start_node: int
    end_node: int

    wall_id: int

    length: float
    thickness: float

    # ---------------------------------------------------------

    @property
    def nodes(self):

        return (
            self.start_node,
            self.end_node
        )

    # ---------------------------------------------------------

    def contains(self, node_id: int):

        return (
            node_id == self.start_node or
            node_id == self.end_node
        )

    # ---------------------------------------------------------

    def other(self, node_id: int):

        if node_id == self.start_node:
            return self.end_node

        if node_id == self.end_node:
            return self.start_node

        return None

    # ---------------------------------------------------------

    @property
    def is_zero(self):

        return self.length <= 1e-6

    # ---------------------------------------------------------

    def __repr__(self):

        return (
            f"Edge("
            f"id={self.id}, "
            f"{self.start_node}->{self.end_node}, "
            f"wall={self.wall_id}, "
            f"L={self.length:.2f})"
        )
