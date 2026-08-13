# -*- coding: utf-8 -*-
"""
PointIndex — toleranslı uzamsal nokta indeksi.

  idx = PointIndex(tolerance=1.0)
  node = idx.get_or_create_node(x, y)
"""

from __future__ import annotations

from typing import Dict, Iterator, Optional

from SRC.geometry3.graph.geometry_graph import GeometryNode
from SRC.geometry3.spatial.point_key import PointKey


class PointIndex:

    def __init__(self, tolerance: float = 1.0, **kwargs):
        # tol= alias (GeometryGraphBuilder uyumu)
        if "tol" in kwargs and kwargs["tol"] is not None:
            tolerance = kwargs["tol"]
        if tolerance <= 0:
            raise ValueError("Tolerance must be greater than zero.")
        self.tolerance = tolerance
        self._next_node_id = 0
        self._keys: Dict[PointKey, int] = {}
        self._nodes: Dict[int, GeometryNode] = {}
        self._duplicate_hits = 0

    def clear(self) -> None:
        self._next_node_id = 0
        self._keys.clear()
        self._nodes.clear()
        self._duplicate_hits = 0

    def key(self, x: float, y: float) -> PointKey:
        return PointKey.from_coordinates(x, y, self.tolerance)

    def get_or_create_node(self, x: float, y: float) -> GeometryNode:
        k = self.key(x, y)
        node_id = self._keys.get(k)
        if node_id is not None:
            self._duplicate_hits += 1
            return self._nodes[node_id]

        node = GeometryNode(id=self._next_node_id, x=x, y=y)
        self._keys[k] = node.id
        self._nodes[node.id] = node
        self._next_node_id += 1
        return node

    def find_node(self, x: float, y: float) -> Optional[GeometryNode]:
        """Varsa node, yoksa None (yeni oluşturmaz)."""
        node_id = self._keys.get(self.key(x, y))
        if node_id is None:
            return None
        return self._nodes[node_id]

    def contains(self, x: float, y: float) -> bool:
        return self.key(x, y) in self._keys

    @property
    def nodes(self) -> Dict[int, GeometryNode]:
        return self._nodes

    def node_count(self) -> int:
        return len(self._nodes)

    def statistics(self) -> dict:
        return {
            "tolerance": self.tolerance,
            "node_count": len(self._nodes),
            "duplicate_points": self._duplicate_hits,
        }

    def debug_print(self) -> None:
        stats = self.statistics()
        print()
        print("=" * 60)
        print("POINT INDEX")
        print("=" * 60)
        print(f"Tolerance       : {stats['tolerance']:.3f}")
        print(f"Nodes           : {stats['node_count']}")
        print(f"Duplicate Points: {stats['duplicate_points']}")
        print()
        print("FIRST 20 NODES")
        for i, node in enumerate(self._nodes.values()):
            if i >= 20:
                break
            print(f"{node.id:5d} : ({node.x:.3f}, {node.y:.3f})")

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, key: PointKey) -> bool:
        return key in self._keys

    def __iter__(self) -> Iterator[GeometryNode]:
        return iter(self._nodes.values())