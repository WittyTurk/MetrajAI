"""
Geometry3
HalfEdge Linker
"""

from __future__ import annotations


class HalfEdgeLinker:

    # ---------------------------------------------------------
    
    def __init__(self, project):

        self.project = project

    # ---------------------------------------------------------

    def build(self):

        edge_by_id = {
            edge.id: edge
            for edge in self.project.half_edges
        }

        vertex_by_id = {
            vertex.id: vertex
            for vertex in self.project.vertices
        }

        for vertex in self.project.vertices:

            incident_edges = []

            for edge_id in vertex.incident_edges:
                incident_edges.append(edge_by_id[edge_id])

            incident_edges.sort(key=lambda edge: edge.angle)
        return self.project.half_edges