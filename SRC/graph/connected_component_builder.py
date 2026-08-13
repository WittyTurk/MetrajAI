# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.graph.wall_graph import WallGraph


class ConnectedComponentBuilder:

    def build(self, graph: WallGraph) -> list[list[int]]:

        components: list[list[int]] = []
        visited: set[int] = set()

        for node_id in graph.nodes:

            if node_id in visited:
                continue

            component: list[int] = []
            self._dfs(node_id, graph, visited, component)
            components.append(component)

        return components

    # -------------------------------------------------

    def _dfs(
        self,
        start_id: int,
        graph: WallGraph,
        visited: set[int],
        component: list[int],
    ):

        stack = [start_id]

        while stack:

            node_id = stack.pop()

            if node_id in visited:
                continue

            visited.add(node_id)
            component.append(node_id)

            for neighbor_id in graph.edges.get(node_id, set()):

                if neighbor_id not in visited:
                    stack.append(neighbor_id)
