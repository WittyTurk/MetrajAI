# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.geometry3.topology.vertex import Vertex
from SRC.models.merged_wall import MergedWall
from SRC.utils.geometry_key import GeometryKey


class VertexV2Validator:

    def validate(
        self,
        merged_walls: list[MergedWall],
        vertices: list[Vertex],
    ) -> bool:

        merged_wall_count = len(merged_walls)
        vertex_count = len(vertices)

        duplicate_vertex = self.count_duplicate_vertices(vertices)
        missing_vertex = self.count_missing_vertices(merged_walls, vertices)

        expected_vertex_count = len(self.endpoint_keys(merged_walls))

        passed = (
            duplicate_vertex == 0
            and missing_vertex == 0
            and vertex_count == expected_vertex_count
        )

        print()
        print("=" * 40)
        print("VERTEX V2 VALIDATOR")
        print("=" * 40)
        print()
        print(f"MergedWall Count : {merged_wall_count}")
        print()
        print(f"Vertex Count : {vertex_count}")
        print()
        print(f"Duplicate Vertex : {duplicate_vertex}")
        print()
        print(f"Missing Vertex : {missing_vertex}")
        print()

        if passed:
            print("VERTEX V2 VALIDATOR : PASS")
        else:
            print("VERTEX V2 VALIDATOR : FAIL")

        return passed

    # -------------------------------------------------

    def endpoint_keys(self, merged_walls: list[MergedWall]) -> set[tuple[float, float]]:

        keys: set[tuple[float, float]] = set()

        for wall in merged_walls:
            keys.add(GeometryKey.point(wall.start))
            keys.add(GeometryKey.point(wall.end))

        return keys

    # -------------------------------------------------

    def vertex_keys(self, vertices: list[Vertex]) -> list[tuple[float, float]]:

        return [
            GeometryKey.point_xy(vertex.x, vertex.y)
            for vertex in vertices
        ]

    # -------------------------------------------------

    def count_duplicate_vertices(self, vertices: list[Vertex]) -> int:

        keys = self.vertex_keys(vertices)

        return len(keys) - len(set(keys))

    # -------------------------------------------------

    def count_missing_vertices(
        self,
        merged_walls: list[MergedWall],
        vertices: list[Vertex],
    ) -> int:

        endpoint_keys = self.endpoint_keys(merged_walls)
        vertex_keys = set(self.vertex_keys(vertices))

        return len(endpoint_keys - vertex_keys)
