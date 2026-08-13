# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.geometry3.topology.topology_edge import TopologyEdge


class TopologyEdgeBuilder:

    # ---------------------------------------------------------

    def __init__(self, project, registry):

        self.project = project
        self.registry = registry

    # ---------------------------------------------------------

    def build(self):

        edges = []

        edge_id = 1

        for wall in self.project.merged_walls:

            start = self.registry.get_or_create(
                wall.start.x,
                wall.start.y
            )

            end = self.registry.get_or_create(
                wall.end.x,
                wall.end.y
            )

            wall.start_node = start.id
            wall.end_node = end.id

            edge = TopologyEdge(

                id=edge_id,

                start_node=start.id,
                end_node=end.id,

                wall_id=wall.id

            )

            edges.append(edge)

            edge_id += 1

        print()
        print("=" * 40)
        print("TOPOLOGY EDGE BUILDER")
        print("=" * 40)
        print("Nodes :", len(self.registry.all_nodes()))
        print("Edges :", len(edges))

        return self.registry.all_nodes(), edges