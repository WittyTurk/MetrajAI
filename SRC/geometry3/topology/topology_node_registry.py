# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.geometry3.topology.topology_node import TopologyNode


class TopologyNodeRegistry:

    TOLERANCE = 5.0

    # ---------------------------------------------------------

    def __init__(self):

        self._lookup = {}
        self._next_id = 1

    # ---------------------------------------------------------

    def _key(self, x: float, y: float):

        return (
            round(x / self.TOLERANCE),
            round(y / self.TOLERANCE),
        )

    # ---------------------------------------------------------

    def get_or_create(self, x: float, y: float) -> TopologyNode:

        key = self._key(x, y)

        if key in self._lookup:
            return self._lookup[key]

        node = TopologyNode(
            id=self._next_id,
            x=x,
            y=y,
            h=0.0,
        )

        self._lookup[key] = node

        self._next_id += 1

        return node

    # ---------------------------------------------------------

    def all_nodes(self):

        return list(self._lookup.values())
