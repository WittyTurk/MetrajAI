# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.geometry3.topology.vertex import Vertex
from SRC.utils.debug_logger import DebugLogger


class VertexBuilder:

    def __init__(self, project):

        self.project = project

    # ---------------------------------------------------------

    def debug_vertex_wall_groups(self):

        wall_groups = {}

        for vertex in self.project.vertices:
            wall_groups[vertex.id] = []

        for wall in self.project.merged_walls:

            for vertex in self.project.vertices:

                if (
                    abs(vertex.x - wall.start.x) < 1e-6 and
                    abs(vertex.y - wall.start.y) < 1e-6
                ):
                    wall_groups[vertex.id].append(wall.id)

                if (
                    abs(vertex.x - wall.end.x) < 1e-6 and
                    abs(vertex.y - wall.end.y) < 1e-6
                ):
                    wall_groups[vertex.id].append(wall.id)

        DebugLogger.subtitle("VERTEX WALL GROUPS")

        for vertex in self.project.vertices:
            if len(wall_groups[vertex.id]) >= 3:

            
                DebugLogger.item(
                    f"Vertex {vertex.id}"
                    f"  ({vertex.x:.1f}, {vertex.y:.1f})"
                    f"  MergedWalls={wall_groups[vertex.id]}"
                )

    # ---------------------------------------------------------

    def build(self):

        DebugLogger.section("VERTEX BUILDER")

        self.project.vertices.clear()

        for node in self.project.topology_graph.nodes.values():

            vertex = Vertex(
                id=node.id,
                x=node.x,
                y=node.y
            )

            self.project.vertices.append(vertex)

        DebugLogger.value(
            "Topology Nodes",
            self.project.topology_graph.node_count
        )

        DebugLogger.value(
            "Vertex",
            len(self.project.vertices)
        )

        DebugLogger.subtitle("FIRST 10 VERTEX")

        for vertex in self.project.vertices[:10]:
            DebugLogger.item(vertex)

        return self.project.vertices

        # ---------------------------------------------

        for wall in self.project.merged_walls:

            for point in (wall.start, wall.end):

                key = GeometryKey.point(point)

                if key in lookup:
                    continue

                if point.x < -5000 or point.x > 5800 or abs(point.x + 398.10438) < 1:
                    print(
                        "NEW VERTEX:",
                         wall.id,
                         point.x,
                         point.y
                     )
                vertex = Vertex(
                    id=vertex_id,
                    x=point.x,
                    y=point.y
                )

                self.project.vertices.append(vertex)

                lookup[key] = vertex

                vertex_id += 1

        # ---------------------------------------------

        DebugLogger.value(
            "MergedWall",
            len(self.project.merged_walls)
        )

        DebugLogger.value(
            "Vertex",
            len(self.project.vertices)
        )

        DebugLogger.subtitle("ILK 10 VERTEX")

        for vertex in self.project.vertices[:10]:
            DebugLogger.item(vertex)

        self.debug_vertex_wall_groups()

        return self.project.vertices
