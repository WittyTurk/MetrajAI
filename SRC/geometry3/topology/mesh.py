# -*- coding: utf-8 -*-
"""
Geometry3

Mesh
"""

from __future__ import annotations

from SRC.utils.debug_logger import DebugLogger


class Mesh:

    def __init__(self):

        self.vertices = {}
        self.half_edges = {}
        self.faces = {}

    # ---------------------------------------------------------

    def clear(self):

        self.vertices.clear()
        self.half_edges.clear()
        self.faces.clear()

    # ---------------------------------------------------------

    def add_vertex(self, vertex):

        self.vertices[vertex.id] = vertex

    # ---------------------------------------------------------

    def add_half_edge(self, edge):

        self.half_edges[edge.id] = edge

    # ---------------------------------------------------------

    def add_face(self, face):

        self.faces[face.id] = face

    # ---------------------------------------------------------

    def get_vertex(self, vertex_id):

        return self.vertices.get(vertex_id)

    # ---------------------------------------------------------

    def get_half_edge(self, edge_id):

        return self.half_edges.get(edge_id)

    # ---------------------------------------------------------

    def get_face(self, face_id):

        return self.faces.get(face_id)

    # ---------------------------------------------------------

    @property
    def vertex_count(self):

        return len(self.vertices)

    # ---------------------------------------------------------

    @property
    def half_edge_count(self):

        return len(self.half_edges)

    # ---------------------------------------------------------

    @property
    def face_count(self):

        return len(self.faces)

    # ---------------------------------------------------------

    def summary(self):

        DebugLogger.section("MESH")

        DebugLogger.value(
            "Vertex",
            self.vertex_count
        )

        DebugLogger.value(
            "HalfEdge",
            self.half_edge_count
        )

        DebugLogger.value(
            "Face",
            self.face_count
        )

        DebugLogger.item("")
        DebugLogger.item("Mesh OK")

    # ---------------------------------------------------------

    def __repr__(self):

        return (
            f"Mesh("
            f"vertices={self.vertex_count}, "
            f"half_edges={self.half_edge_count}, "
            f"faces={self.face_count})"
        )
