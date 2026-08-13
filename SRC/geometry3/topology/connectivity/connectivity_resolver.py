# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.geometry3.topology.connectivity.graph_model import Graph
from SRC.geometry3.topology.connectivity.graph_model import Segment
from SRC.geometry3.topology.connectivity.node_registry import NodeRegistry


class ConnectivityResolver:

    def __init__(self, tolerance: float = 0.0):

        self.tolerance = max(0.0, float(tolerance))

    # ---------------------------------------------------------

    def resolve(self, wall_axes) -> Graph:

        registry = NodeRegistry(tolerance=self.tolerance)
        graph = Graph()

        for index, axis in enumerate(wall_axes, start=1):

            start_node = registry.create_or_get_node(
                axis.start.x,
                axis.start.y,
            )

            end_node = registry.create_or_get_node(
                axis.end.x,
                axis.end.y,
            )

            graph.add_node(start_node)
            graph.add_node(end_node)

            source_wall_ids = getattr(axis, "source_wall_ids", [])
            source_wall_id = source_wall_ids[0] if source_wall_ids else None

            segment = Segment(
                id=index,
                start_node=start_node.id,
                end_node=end_node.id,
                source_wall_id=source_wall_id,
            )

            graph.add_segment(segment)

        return graph
