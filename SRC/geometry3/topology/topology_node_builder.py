# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.geometry3.topology.topology_node_registry import TopologyNodeRegistry


class TopologyNodeBuilder:

    # ---------------------------------------------------------

    def __init__(self, project, registry):

        self.project = project
        self.registry = registry

    # ---------------------------------------------------------

    def build(self):
        print(">>> TOPOLOGY NODE BUILDER EXECUTED <<<")

        for wall in self.project.merged_walls:
            if wall.id in (255, 257, 357, 475):
                print(
                    "NODE BUILDER:",
                    wall.id,
                    (wall.start.x, wall.start.y),
                    "->",
                    (wall.end.x, wall.end.y)
                )

            self.registry.get_or_create(
                wall.start.x,
                wall.start.y
            )

            self.registry.get_or_create(
                wall.end.x,
                wall.end.y
            )

        nodes = self.registry.all_nodes()

        print()
        print("=" * 40)
        print("TOPOLOGY NODE BUILDER")
        print("=" * 40)
        print("Topology Nodes :", len(nodes))

        return nodes