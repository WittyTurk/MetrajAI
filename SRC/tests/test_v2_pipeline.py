# -*- coding: utf-8 -*-

from __future__ import annotations

import io
from contextlib import redirect_stdout

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


def _graph_edge_count(graph) -> int:

    # Graph edges are undirected and stored in adjacency sets.
    return sum(len(neighbors) for neighbors in graph.edges.values()) // 2


def _vertex_keys(vertices) -> list[tuple[float, float]]:

    return [GeometryKey.point(vertex.x, vertex.y) for vertex in vertices]


def run() -> bool:

    project = Project()

    # Prepare walls from input DXF without polluting console output.
    reader = DXFReader(project)
    _silent(reader.read)
    _silent(lambda: WallBuilder(project).build())

    graph = WallGraphBuilder(project).build()
    components = ConnectedComponentBuilder().build(graph)
    wall_components = WallComponentBuilder().build(components, graph)
    axes = WallAxisBuilder().build(wall_components)
    merged_walls = MergedWallBuilderV2().build(axes)

    project.merged_walls = merged_walls
    vertices = _silent(lambda: VertexBuilder(project).build())

    validator = VertexV2Validator()
    validator_passed = _silent(lambda: validator.validate(merged_walls, vertices))

    endpoint_keys = validator.endpoint_keys(merged_walls)
    vertex_keys = _vertex_keys(vertices)

    duplicate_vertex = len(vertex_keys) - len(set(vertex_keys))
    missing_vertex = len(endpoint_keys - set(vertex_keys))

    passed = (
        len(merged_walls) == len(axes)
        and validator_passed
        and duplicate_vertex == 0
        and missing_vertex == 0
    )

    print("=" * 40)
    print("GEOMETRY3 V2 TEST")
    print("=" * 40)
    print()
    print(f"Wall Count : {len(project.walls)}")
    print()
    print(f"Graph Nodes : {len(graph.nodes)}")
    print()
    print(f"Graph Edges : {_graph_edge_count(graph)}")
    print()
    print(f"Connected Components : {len(components)}")
    print()
    print(f"Wall Components : {len(wall_components)}")
    print()
    print(f"Wall Axis : {len(axes)}")
    print()
    print(f"MergedWall V2 : {len(merged_walls)}")
    print()
    print(f"Vertex : {len(vertices)}")
    print()
    print(f"Duplicate Vertex : {duplicate_vertex}")
    print()
    print(f"Missing Vertex : {missing_vertex}")
    print()
    print("=" * 40)
    print()
    print(f"PASS / FAIL : {'PASS' if passed else 'FAIL'}")

    return passed


if __name__ == "__main__":
    run()
