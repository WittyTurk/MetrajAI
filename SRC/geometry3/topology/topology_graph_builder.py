# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.geometry3.topology.topology_graph import TopologyGraph
from SRC.geometry3.topology.topology_node_registry import TopologyNodeRegistry
from SRC.geometry3.topology.topology_node_builder import TopologyNodeBuilder
from SRC.geometry3.topology.topology_edge_builder import TopologyEdgeBuilder


class TopologyGraphBuilder:

    # ---------------------------------------------------------

    def __init__(self, project):

        self.project = project

    # ---------------------------------------------------------

    def build(self):

        registry = TopologyNodeRegistry()

        graph = TopologyGraph()

        nodes = TopologyNodeBuilder(
            self.project,
            registry
        ).build()

        _, edges = TopologyEdgeBuilder(
            self.project,
            registry
        ).build()

        for node in nodes:
            graph.add_node(node)

        for edge in edges:
            graph.add_edge(edge)
        print()
        print("=" * 40)
        print("TOPOLOGY GRAPH")
        print("=" * 40)
        print("Nodes :", graph.node_count)
        print("Edges :", graph.edge_count)

        self.project.topology_graph = graph

        return graph
