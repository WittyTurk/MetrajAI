# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.graph.wall_graph import WallGraph
from SRC.models.wall_component import WallComponent


class WallComponentBuilder:

    def build(
        self,
        graph: WallGraph,
        components: list[list[int]],
    ) -> list[WallComponent]:

        result: list[WallComponent] = []

        for index, component in enumerate(components, start=1):

            wall_ids = list(dict.fromkeys(component))

            wall_component = WallComponent(
                id=index,
                wall_ids=wall_ids,
                orientation=self.detect_orientation(graph, wall_ids),
                thickness=0.0,
            )

            result.append(wall_component)

        return result

    # -------------------------------------------------

    def detect_orientation(
        self,
        graph: WallGraph,
        wall_ids: list[int],
    ) -> str:

        horizontal = 0
        vertical = 0

        for wall_id in wall_ids:

            wall = graph.nodes.get(wall_id)

            if wall is None:
                continue

            if wall.is_horizontal:
                horizontal += 1

            elif wall.is_vertical:
                vertical += 1

        if horizontal > 0 and vertical == 0:
            return "horizontal"

        if vertical > 0 and horizontal == 0:
            return "vertical"

        if horizontal == 0 and vertical == 0:
            return "unknown"

        return "mixed"

        
