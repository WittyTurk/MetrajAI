# -*- coding: utf-8 -*-
"""
Geometry Graph Builder — merged_walls veya walls listesinden graf.

  builder = GeometryGraphBuilder(project)
  graph = builder.build()                    # project.merged_walls
  graph = builder.build(walls=project.walls) # alternatif
"""

from __future__ import annotations

from typing import List, Optional

from SRC.geometry3.graph.geometry_graph import GeometryGraph
from SRC.geometry3.spatial.point_index import PointIndex


class GeometryGraphBuilder:

    def __init__(self, project, snap_tol: float = 1.0, debug: bool = False):
        self.project = project
        self.snap_tol = snap_tol
        self.debug = debug
        self.graph = GeometryGraph()
        self.index = PointIndex(tol=snap_tol) if self._index_accepts_tol() else PointIndex()

    def _index_accepts_tol(self) -> bool:
        try:
            import inspect
            return "tol" in inspect.signature(PointIndex.__init__).parameters
        except Exception:
            return False

    def build(self, walls: Optional[List] = None) -> GeometryGraph:
        self.graph = GeometryGraph()
        try:
            self.index = PointIndex(tol=self.snap_tol)
        except TypeError:
            self.index = PointIndex()

        source = walls
        if source is None:
            source = getattr(self.project, "merged_walls", None) or getattr(
                self.project, "walls", []
            )

        for wall in source:
            self._add_wall(wall)

        self._connect_node_walls()

        if self.debug:
            self.graph.debug_print()
        else:
            s = self.graph.statistics()
            print()
            print("=" * 40)
            print("GEOMETRY GRAPH BUILDER")
            print("=" * 40)
            print(f"Walls : {s['wall_count']}  Nodes : {s['node_count']}  "
                  f"Links : {s['edge_count']}  Isolated : {s['isolated_wall_count']}")

        return self.graph

    def _add_wall(self, wall) -> None:
        start = self.index.get_or_create_node(wall.start.x, wall.start.y)
        end = self.index.get_or_create_node(wall.end.x, wall.end.y)

        if self.debug:
            print(
                f"ADD_WALL {wall.id}  "
                f"({wall.start.x:.1f},{wall.start.y:.1f})->"
                f"({wall.end.x:.1f},{wall.end.y:.1f})  "
                f"nodes={start.id}->{end.id}"
            )

        self.graph.add_node(start)
        self.graph.add_node(end)
        self.graph.add_wall(wall.id, start.id, end.id)

    def _connect_node_walls(self) -> None:
        for wall_ids in self.graph.node_to_walls.values():
            walls = list(wall_ids)
            for i in range(len(walls)):
                for j in range(i + 1, len(walls)):
                    self.graph.connect(walls[i], walls[j])