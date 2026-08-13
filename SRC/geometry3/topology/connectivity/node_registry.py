# -*- coding: utf-8 -*-

from __future__ import annotations

from math import hypot

from SRC.geometry3.topology.connectivity.graph_model import Node


class NodeRegistry:

    def __init__(self, tolerance: float = 0.0):

        self.tolerance = max(0.0, float(tolerance))

        self._nodes_by_id: dict[int, Node] = {}
        self._next_node_id = 1

    # ---------------------------------------------------------

    @property
    def nodes(self) -> dict[int, Node]:

        return self._nodes_by_id

    # ---------------------------------------------------------

    def _find_with_tolerance(self, x: float, y: float) -> Node | None:

        if not self._nodes_by_id:
            return None

        for node in self._nodes_by_id.values():

            if hypot(node.x - x, node.y - y) <= self.tolerance:
                return node

        return None

    # ---------------------------------------------------------

    def lookup(self, x: float, y: float) -> Node | None:

        return self._find_with_tolerance(float(x), float(y))

    # ---------------------------------------------------------

    def create_or_get_node(self, x: float, y: float) -> Node:

        x = float(x)
        y = float(y)

        existing = self._find_with_tolerance(x, y)

        if existing is not None:
            return existing

        node = Node(
            id=self._next_node_id,
            x=x,
            y=y,
        )

        self._nodes_by_id[node.id] = node
        self._next_node_id += 1

        return node
