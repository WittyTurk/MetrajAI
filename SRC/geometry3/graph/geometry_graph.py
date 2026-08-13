# -*- coding: utf-8 -*-
"""
Geometry3 — duvar topoloji grafı.

Node  = uç nokta (snap ile birleşir)
Edge  = duvar
Adjacency = aynı node'u paylaşan duvarlar
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Set, Tuple


@dataclass(slots=True)
class GeometryNode:
    id: int
    x: float
    y: float


@dataclass(slots=True)
class GeometryEdge:
    wall_id: int
    start_node: int
    end_node: int


class GeometryGraph:

    def __init__(self):
        self.nodes: Dict[int, GeometryNode] = {}
        self.edges: Dict[int, GeometryEdge] = {}
        self.wall_to_nodes: Dict[int, Tuple[int, int]] = {}
        self.node_to_walls: Dict[int, Set[int]] = {}
        self.adjacency: Dict[int, Set[int]] = {}

    def add_node(self, node: GeometryNode) -> None:
        self.nodes[node.id] = node
        self.node_to_walls.setdefault(node.id, set())

    def add_wall(self, wall_id: int, start_node: int, end_node: int) -> None:
        self.edges[wall_id] = GeometryEdge(
            wall_id=wall_id,
            start_node=start_node,
            end_node=end_node,
        )
        self.wall_to_nodes[wall_id] = (start_node, end_node)
        self.adjacency.setdefault(wall_id, set())
        self.node_to_walls.setdefault(start_node, set()).add(wall_id)
        self.node_to_walls.setdefault(end_node, set()).add(wall_id)

    def connect(self, wall1: int, wall2: int) -> None:
        if wall1 == wall2:
            return
        self.adjacency.setdefault(wall1, set()).add(wall2)
        self.adjacency.setdefault(wall2, set()).add(wall1)

    def neighbors(self, wall_id: int) -> Set[int]:
        return self.adjacency.get(wall_id, set())

    def wall_neighbors(self, wall_id: int) -> Set[int]:
        return self.neighbors(wall_id)

    def degree(self, wall_id: int) -> int:
        return len(self.neighbors(wall_id))

    def has_wall(self, wall_id: int) -> bool:
        return wall_id in self.edges

    def has_node(self, node_id: int) -> bool:
        return node_id in self.nodes

    def isolated_walls(self) -> Iterable[int]:
        for wall_id, neighbours in self.adjacency.items():
            if not neighbours:
                yield wall_id

    def connected_components(self) -> list[list[int]]:
        """Duvar id listeleri (bağlı bileşenler)."""
        seen: Set[int] = set()
        components = []
        for wid in self.edges:
            if wid in seen:
                continue
            stack = [wid]
            comp = []
            seen.add(wid)
            while stack:
                u = stack.pop()
                comp.append(u)
                for v in self.neighbors(u):
                    if v not in seen:
                        seen.add(v)
                        stack.append(v)
            components.append(comp)
        return components

    def statistics(self) -> dict:
        edge_count = sum(len(v) for v in self.adjacency.values()) // 2
        isolated = sum(1 for _ in self.isolated_walls())
        return {
            "node_count": len(self.nodes),
            "wall_count": len(self.edges),
            "edge_count": edge_count,
            "isolated_wall_count": isolated,
            "component_count": len(self.connected_components()),
        }

    def debug_print(self) -> None:
        stats = self.statistics()
        print()
        print("=" * 60)
        print("GEOMETRY GRAPH")
        print("=" * 60)
        print(f"Nodes          : {stats['node_count']}")
        print(f"Walls          : {stats['wall_count']}")
        print(f"Graph Edges    : {stats['edge_count']}")
        print(f"Isolated Walls : {stats['isolated_wall_count']}")
        print(f"Components     : {stats['component_count']}")
        print()
        print("FIRST 20 WALLS")
        for i, wall_id in enumerate(sorted(self.adjacency)):
            if i >= 20:
                break
            print(
                f"{wall_id:5d} -> degree={len(self.adjacency[wall_id])} "
                f"{sorted(self.adjacency[wall_id])}"
            )