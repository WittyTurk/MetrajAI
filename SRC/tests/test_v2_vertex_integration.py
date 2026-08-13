# -*- coding: utf-8 -*-

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from SRC.builders.merged_wall_builder_v2 import MergedWallBuilderV2
from SRC.builders.wall_axis_builder import WallAxisBuilder
from SRC.builders.wall_builder import WallBuilder
from SRC.builders.wall_component_builder import WallComponentBuilder
from SRC.geometry3.topology.vertex_builder import VertexBuilder
from SRC.graph.connected_component_builder import ConnectedComponentBuilder
from SRC.graph.wall_graph_builder import WallGraphBuilder
from SRC.models.project import Project
from SRC.readers.dxf_reader import DXFReader
from SRC.utils.geometry_key import GeometryKey
from SRC.validators.vertex_v2_validator import VertexV2Validator


def _silent(callable_obj):

    with redirect_stdout(io.StringIO()):
        return callable_obj()


def _vertex_keys(vertices) -> list[tuple[float, float]]:

    return [
        GeometryKey.point(vertex.x, vertex.y)
        for vertex in vertices
    ]


def run() -> bool:

    merged_wall_count = 0
    vertex_count = 0
    duplicate_vertex = 0
    missing_vertex = 0

    try:
        project = Project()

        # 1) DXF read
        reader = DXFReader(project, input_folder="INPUT")
        _silent(reader.read)

        # 2) WallBuilder
        _silent(lambda: WallBuilder(project).build())

        # 3) WallGraphBuilder
        graph = WallGraphBuilder(project).build()

        # 4) ConnectedComponentBuilder
        components = ConnectedComponentBuilder().build(graph)

        # 5) WallComponentBuilder
        wall_components = WallComponentBuilder().build(components, graph)

        # 6) WallAxisBuilder
        wall_axes = WallAxisBuilder().build(wall_components)

        # 7) MergedWallBuilderV2
        merged_walls = MergedWallBuilderV2().build(wall_axes)

        # 8) VertexBuilder (V1)
        project.merged_walls = merged_walls
        vertices = _silent(lambda: VertexBuilder(project).build())

        # 9) VertexV2Validator (metrics source)
        validator = VertexV2Validator()

        merged_wall_count = len(merged_walls)
        vertex_count = len(vertices)

        vertex_keys = _vertex_keys(vertices)
        endpoint_keys = validator.endpoint_keys(merged_walls)

        duplicate_vertex = len(vertex_keys) - len(set(vertex_keys))
        missing_vertex = len(endpoint_keys - set(vertex_keys))

        passed = (
            duplicate_vertex == 0
            and missing_vertex == 0
        )

    except Exception:
        passed = False

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
    print(f"PASS / FAIL : {'PASS' if passed else 'FAIL'}")

    return passed


if __name__ == "__main__":
    run()
