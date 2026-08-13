# -*- coding: utf-8 -*-
"""
Geometry3

Topology Graph
"""

from __future__ import annotations

from typing import Dict, List

from SRC.geometry3.topology.node import Node
from SRC.geometry3.topology.edge import Edge


class Graph:
    """
    Geometry3 Topology Graph

    Graph;

        - Node koleksiyonunu
        - Edge koleksiyonunu
        - Komşuluk ilişkilerini

    yönetir.
    """

    def __init__(self):

        self.nodes: Dict[int, Node] = {}
        self.edges: Dict[int, Edge] = {}

    # ---------------------------------------------------------

    def clear(self):

        self.nodes.clear()
        self.edges.clear()

    # ---------------------------------------------------------

    def add_node(self, node: Node):

        self.nodes[node.id] = node

    # ---------------------------------------------------------

    def add_edge(self, edge: Edge):

        self.edges[edge.id] = edge

        if edge.start_node in self.nodes:
            self.nodes[edge.start_node].add_edge(edge.id)
            self.nodes[edge.start_node].add_wall(edge.wall_id)

        if edge.end_node in self.nodes:
            self.nodes[edge.end_node].add_edge(edge.id)
            self.nodes[edge.end_node].add_wall(edge.wall_id)

    # ---------------------------------------------------------

    def get_node(self, node_id: int):

        return self.nodes.get(node_id)

    # ---------------------------------------------------------

    def get_edge(self, edge_id: int):

        return self.edges.get(edge_id)

    # ---------------------------------------------------------

    def neighbors(self, node_id: int) -> List[int]:
        """
        Komşu node id'lerini döndürür.
        """

        node = self.get_node(node_id)

        if node is None:
            return []

        result = []

        for edge_id in node.edges:

            edge = self.edges[edge_id]

            other = edge.other(node_id)

            if other is not None:
                result.append(other)

        return result

    # ---------------------------------------------------------

    @property
    def node_count(self):

        return len(self.nodes)

    # ---------------------------------------------------------

    @property
    def edge_count(self):

        return len(self.edges)

    # ---------------------------------------------------------

    def summary(self):

        print()
        print("=" * 40)
        print("GRAPH")
        print("=" * 40)

        print(f"Node : {self.node_count}")
        print(f"Edge : {self.edge_count}")

    # ---------------------------------------------------------

    def __repr__(self):

        return (
            f"Graph("
            f"nodes={self.node_count}, "
            f"edges={self.edge_count})"
        )
