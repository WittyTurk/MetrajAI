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
from SRC.geometry3.topology.next_prev_builder import NextPrevBuilder
from SRC.geometry3.topology.vertex_builder import VertexBuilder
from SRC.graph.connected_component_builder import ConnectedComponentBuilder
from SRC.graph.wall_graph_builder import WallGraphBuilder
from SRC.models.project import Project
from SRC.readers.dxf_reader import DXFReader


def _silent(callable_obj):

    with redirect_stdout(io.StringIO()):
        return callable_obj()


def _prepare_mesh(project: Project):

    project.mesh.clear()

    for vertex in project.vertices:
        project.mesh.add_vertex(vertex)

    for half_edge in project.half_edges:
        project.mesh.add_half_edge(half_edge)


def _count_missing_next(half_edges) -> int:

    return sum(1 for edge in half_edges if edge.next is None)


def _count_missing_prev(half_edges) -> int:

    return sum(1 for edge in half_edges if edge.prev is None)


def _count_broken_twin_links(half_edges) -> int:

    by_id = {edge.id: edge for edge in half_edges}
    broken = 0

    for edge in half_edges:

        if edge.twin is None:
            broken += 1
            continue

        twin = by_id.get(edge.twin)

        if twin is None:
            broken += 1
            continue

        if twin.twin != edge.id:
            broken += 1

    return broken


def run() -> bool:

    half_edge_count = 0
    missing_next = 0
    missing_prev = 0
    broken_twin_links = 0

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

        # 8) VertexBuilder
        project.merged_walls = merged_walls
        _silent(lambda: VertexBuilder(project).build())

        # 9) HalfEdgeBuilder
        _silent(lambda: HalfEdgeBuilder(project).build())

        # 10) NextPrevBuilder
        _prepare_mesh(project)
        _silent(lambda: NextPrevBuilder(project).build())

        half_edges = project.half_edges

        half_edge_count = len(half_edges)
        missing_next = _count_missing_next(half_edges)
        missing_prev = _count_missing_prev(half_edges)
        broken_twin_links = _count_broken_twin_links(half_edges)

        passed = (
            missing_next == 0
            and missing_prev == 0
            and broken_twin_links == 0
        )

    except Exception:
        passed = False

    print("=" * 40)
    print("NEXTPREV V2 VALIDATOR")
    print("=" * 40)
    print()
    print(f"HalfEdge Count : {half_edge_count}")
    print()
    print(f"Missing Next : {missing_next}")
    print()
    print(f"Missing Prev : {missing_prev}")
    print()
    print(f"Broken Twin Links : {broken_twin_links}")
    print()
    print(f"PASS / FAIL : {'PASS' if passed else 'FAIL'}")

    return passed


if __name__ == "__main__":
    run()
