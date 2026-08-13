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
from SRC.geometry3.topology.face_builder import FaceBuilder
from SRC.geometry3.topology.half_edge_builder import HalfEdgeBuilder
from SRC.geometry3.topology.next_prev_builder import NextPrevBuilder
from SRC.geometry3.topology.vertex_builder import VertexBuilder
from SRC.graph.connected_component_builder import ConnectedComponentBuilder
from SRC.graph.wall_graph_builder import WallGraphBuilder
from SRC.models.project import Project
from SRC.readers.dxf_reader import DXFReader
from SRC.validators.face_v2_validator import FaceV2Validator


def _silent(callable_obj):

    with redirect_stdout(io.StringIO()):
        return callable_obj()


def _prepare_mesh(project: Project):

    project.mesh.clear()

    for vertex in project.vertices:
        project.mesh.add_vertex(vertex)

    for half_edge in project.half_edges:
        project.mesh.add_half_edge(half_edge)


def run() -> bool:

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

        # 11) FaceBuilder
        faces_by_id = _silent(lambda: FaceBuilder(project).build())

        # 12) FaceV2Validator
        passed = FaceV2Validator().validate(faces_by_id)

    except Exception:
        print("FACE V2 VALIDATOR")
        print()
        print("Face Count : 0")
        print()
        print("Average Edges Per Face : 0.00")
        print()
        print("Min Edge Count : 0")
        print()
        print("Max Edge Count : 0")
        print()
        print("2-edge Faces : 0")
        print()
        print("3-edge Faces : 0")
        print()
        print("4+ edge Faces : 0")
        print()
        print("Largest Face : None")
        print()
        print("PASS / FAIL : FAIL")

        passed = False

    return passed


if __name__ == "__main__":
    run()
