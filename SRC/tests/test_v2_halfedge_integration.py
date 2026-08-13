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
from SRC.geometry3.topology.half_edge_builder import HalfEdgeBuilder
from SRC.geometry3.topology.vertex_builder import VertexBuilder
from SRC.graph.connected_component_builder import ConnectedComponentBuilder
from SRC.graph.wall_graph_builder import WallGraphBuilder
from SRC.models.project import Project
from SRC.readers.dxf_reader import DXFReader


def _silent(callable_obj):

    with redirect_stdout(io.StringIO()):
        return callable_obj()


def _count_twin_missing(half_edges) -> int:

    by_id = {edge.id: edge for edge in half_edges}
    missing = 0

    for edge in half_edges:

        if edge.twin is None:
            missing += 1
            continue

        twin = by_id.get(edge.twin)

        if twin is None:
            missing += 1
            continue

        if twin.twin != edge.id:
            missing += 1

    return missing


def _count_duplicate_half_edges(half_edges) -> int:

    by_id = {edge.id: edge for edge in half_edges}
    keys: list[tuple[int, int, int]] = []

    for edge in half_edges:

        twin = by_id.get(edge.twin)

        if twin is None:
            continue

        # Directed key: origin -> twin.origin with wall binding.
        keys.append((edge.origin, twin.origin, edge.wall_id))

    return len(keys) - len(set(keys))


def _count_orphan_half_edges(half_edges, vertices, merged_walls) -> int:

    vertex_ids = {vertex.id for vertex in vertices}
    wall_ids = {wall.id for wall in merged_walls}

    orphan = 0

    for edge in half_edges:

        if edge.origin not in vertex_ids:
            orphan += 1
            continue

        if edge.wall_id not in wall_ids:
            orphan += 1
            continue

    return orphan


def run() -> bool:

    vertex_count = 0
    half_edge_count = 0
    twin_missing = 0
    duplicate_half_edge = 0
    orphan_half_edge = 0

    try:
        project = Project()

        # 1) DXF
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

        # 9) HalfEdgeBuilder (V1)
        half_edges = _silent(lambda: HalfEdgeBuilder(project).build())

        vertex_count = len(vertices)
        half_edge_count = len(half_edges)

        twin_missing = _count_twin_missing(half_edges)
        duplicate_half_edge = _count_duplicate_half_edges(half_edges)
        orphan_half_edge = _count_orphan_half_edges(
            half_edges,
            vertices,
            merged_walls,
        )

        passed = (
            twin_missing == 0
            and duplicate_half_edge == 0
            and orphan_half_edge == 0
        )

    except Exception:
        passed = False

    print("=" * 40)
    print("HALFEDGE V2 VALIDATOR")
    print("=" * 40)
    print()
    print(f"Vertex Count : {vertex_count}")
    print()
    print(f"HalfEdge Count : {half_edge_count}")
    print()
    print(f"Twin Missing : {twin_missing}")
    print()
    print(f"Duplicate HalfEdge : {duplicate_half_edge}")
    print()
    print(f"Orphan HalfEdge : {orphan_half_edge}")
    print()
    print(f"PASS / FAIL : {'PASS' if passed else 'FAIL'}")

    return passed


if __name__ == "__main__":
    run()
