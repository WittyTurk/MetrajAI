# -*- coding: utf-8 -*-
"""
SRC/geometry3/topology/half_edge_from_walls.py

Wall listesinden:
  - unique Vertex
  - HalfEdge + twin
  - incident listeleri
üretecek iskelet (next/prev henüz yok).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import math


# -------------------------------------------------
# Basit modeller (istersen mevcut geometry3 modellerine bağlanır)
# -------------------------------------------------

@dataclass
class Vertex:
    id: int
    x: float
    y: float
    incident_edges: List[int] = field(default_factory=list)


@dataclass
class HalfEdge:
    id: int
    origin: int
    twin: int | None = None
    next: int | None = None
    prev: int | None = None
    face: int | None = None
    wall_id: int | None = None
    angle: float = 0.0


# -------------------------------------------------
# Builder
# -------------------------------------------------

class HalfEdgeFromWalls:
    """
    project.walls → vertices + half_edges

    Büyük proje için:
    - Nokta snap (tolerance)
    - Spatial hash ile hızlı unique
    - Her duvar için 2 half-edge (twin)
    """

    def __init__(self, project, snap_tol: float = 1.0):
        self.project = project
        self.snap_tol = snap_tol

        self.vertices: Dict[int, Vertex] = {}
        self.half_edges: Dict[int, HalfEdge] = {}

        self._point_to_vid: Dict[Tuple[int, int], int] = {}
        self._next_vid = 1
        self._next_eid = 1

    # -------------------------------------------------

    def build(self):
        print()
        print("=" * 55)
        print("HALF-EDGE FROM WALLS")
        print("=" * 55)
        print(f"Wall count     : {len(self.project.walls)}")
        print(f"Snap tolerance : {self.snap_tol}")

        for wall in self.project.walls:
            self._add_wall(wall)

        self._build_incident_lists()
        self._compute_angles()

        print(f"Vertex count   : {len(self.vertices)}")
        print(f"HalfEdge count : {len(self.half_edges)}")

        # İsteğe bağlı: project'e yaz
        self.project.vertices = list(self.vertices.values())
        self.project.half_edges = list(self.half_edges.values())

        # Mesh benzeri erişim için
        if not hasattr(self.project, "mesh") or self.project.mesh is None:
            self.project.mesh = type("Mesh", (), {})()
        self.project.mesh.vertices = self.vertices
        self.project.mesh.half_edges = self.half_edges
        self.project.mesh.get_vertex = lambda vid: self.vertices.get(vid)
        self.project.mesh.get_half_edge = lambda eid: self.half_edges.get(eid)

        return self.vertices, self.half_edges

    # -------------------------------------------------

    def _snap_key(self, x: float, y: float) -> Tuple[int, int]:
        """Tolerance ile grid key"""
        t = self.snap_tol
        return (int(round(x / t)), int(round(y / t)))

    def _get_or_create_vertex(self, x: float, y: float) -> int:
        key = self._snap_key(x, y)
        if key in self._point_to_vid:
            return self._point_to_vid[key]

        vid = self._next_vid
        self._next_vid += 1

        # Snap'lenmiş koordinat kullan (tutarlılık için)
        sx = key[0] * self.snap_tol
        sy = key[1] * self.snap_tol

        self.vertices[vid] = Vertex(id=vid, x=sx, y=sy)
        self._point_to_vid[key] = vid
        return vid

    # -------------------------------------------------

    def _add_wall(self, wall):
        """Her duvar → 2 half-edge (twin)"""
        v1 = self._get_or_create_vertex(wall.start.x, wall.start.y)
        v2 = self._get_or_create_vertex(wall.end.x, wall.end.y)

        if v1 == v2:
            return  # sıfır uzunluk, atla

        e1_id = self._next_eid
        e2_id = self._next_eid + 1
        self._next_eid += 2

        e1 = HalfEdge(id=e1_id, origin=v1, twin=e2_id, wall_id=wall.id)
        e2 = HalfEdge(id=e2_id, origin=v2, twin=e1_id, wall_id=wall.id)

        self.half_edges[e1_id] = e1
        self.half_edges[e2_id] = e2

    # -------------------------------------------------

    def _build_incident_lists(self):
        """Her vertex'ten çıkan half-edge'leri yaz"""
        for v in self.vertices.values():
            v.incident_edges.clear()

        for e in self.half_edges.values():
            self.vertices[e.origin].incident_edges.append(e.id)

    # -------------------------------------------------

    def _compute_angles(self):
        """Her half-edge için yön açısı (0–360)"""
        for e in self.half_edges.values():
            twin = self.half_edges.get(e.twin)
            if twin is None:
                continue
            v0 = self.vertices[e.origin]
            v1 = self.vertices[twin.origin]
            dx = v1.x - v0.x
            dy = v1.y - v0.y
            ang = math.degrees(math.atan2(dy, dx))
            if ang < 0:
                ang += 360.0
            e.angle = ang