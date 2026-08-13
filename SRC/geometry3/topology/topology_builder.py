# -*- coding: utf-8 -*-
"""
Geometry3

Topology Builder
"""

from __future__ import annotations

from SRC.geometry3.topology.topology_graph import TopologyGraph
from SRC.geometry3.topology.topology_node_builder import TopologyNodeBuilder
from SRC.geometry3.topology.topology_edge_builder import TopologyEdgeBuilder


class TopologyBuilder:

    def __init__(self):

        self.graph = TopologyGraph()

    # ---------------------------------------------------------

    def build(self, merged_walls):

        self.graph.clear()

        node_id = 1
        edge_id = 1

        node_lookup = {}

        # ---------------------------------------------
        # NODE + EDGE
        # ---------------------------------------------

        for wall in merged_walls:

            p1 = (
                round(wall.start.x, 6),
                round(wall.start.y, 6)
            )

            p2 = (
                round(wall.end.x, 6),
                round(wall.end.y, 6)
            )

            # ---------- START NODE ----------

            if p1 not in node_lookup:

                node = Node(
                    id=node_id,
                    x=p1[0],
                    y=p1[1]
                )

                self.graph.add_node(node)

                node_lookup[p1] = node_id

                node_id += 1

            # ---------- END NODE ----------

            if p2 not in node_lookup:

                node = Node(
                    id=node_id,
                    x=p2[0],
                    y=p2[1]
                )

                self.graph.add_node(node)

                node_lookup[p2] = node_id

                node_id += 1

            # ---------- EDGE ----------

            edge = Edge(
                id=edge_id,
                start_node=node_lookup[p1],
                end_node=node_lookup[p2],
                wall_id=wall.id,
                length=wall.length,
                thickness=wall.thickness
            )

            self.graph.add_edge(edge)

            edge_id += 1

        # ---------------------------------------------

        print()
        print("=" * 40)
        print("TOPOLOGY BUILDER")
        print("=" * 40)

        print(
            f"Node : {self.graph.node_count}"
        )

        print(
            f"Edge : {self.graph.edge_count}"
        )

        print()

        print("İLK 10 NODE")
        print("-" * 40)

        for node in list(self.graph.nodes.values())[:10]:

            print(node)

        print()

        print("İLK 10 EDGE")
        print("-" * 40)

        for edge in list(self.graph.edges.values())[:10]:

            print(edge)

        return self.graph
