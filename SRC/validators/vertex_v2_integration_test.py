# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.builders.merged_wall_builder_v2 import MergedWallBuilderV2
from SRC.builders.wall_axis_builder import WallAxisBuilder
from SRC.builders.wall_component_builder import WallComponentBuilder
from SRC.geometry3.topology.vertex_builder import VertexBuilder
from SRC.graph.connected_component_builder import ConnectedComponentBuilder
from SRC.graph.wall_graph_builder import WallGraphBuilder
from SRC.models.project import Project
from SRC.validators.vertex_v2_validator import VertexV2Validator


class VertexV2IntegrationTest:

    def run(self, project: Project) -> bool:

        # Flow: WallGraph -> ConnectedComponent -> WallComponent
        graph = WallGraphBuilder(project).build()
        components = ConnectedComponentBuilder().build(graph)
        wall_components = WallComponentBuilder().build(components, graph)

        # Flow: WallAxis -> MergedWall V2 -> VertexBuilder
        axes = WallAxisBuilder().build(wall_components)
        merged_walls = MergedWallBuilderV2().build(axes)

        project.merged_walls = merged_walls
        vertices = VertexBuilder(project).build()

        return VertexV2Validator().validate(merged_walls, vertices)
