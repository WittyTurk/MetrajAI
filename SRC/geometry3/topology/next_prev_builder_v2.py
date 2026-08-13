# -*- coding: utf-8 -*-

from __future__ import annotations

import math

from SRC.utils.debug_logger import DebugLogger


class NextPrevBuilderV2:

    def __init__(self, project):

        self.project = project

    # ---------------------------------------------------------

    def calculate_angle(self, edge):

        origin = self.project.mesh.get_vertex(
            edge.origin
        )

        twin = self.project.mesh.get_half_edge(
            edge.twin
        )

        destination = self.project.mesh.get_vertex(
            twin.origin
        )

        dx = destination.x - origin.x
        dy = destination.y - origin.y

        angle = math.degrees(
            math.atan2(dy, dx)
        )

        if angle < 0:
            angle += 360

        edge.angle = angle

    # ---------------------------------------------------------

    def calculate_angles(self):

        mesh = self.project.mesh

        for edge in mesh.half_edges.values():

            self.calculate_angle(edge)

    # ---------------------------------------------------------

    def sort_incident_edges(self):

        mesh = self.project.mesh

        for vertex in mesh.vertices.values():

            vertex.incident_edges.sort(
                key=lambda edge_id: mesh.get_half_edge(edge_id).angle
            )

            angles = [
                round(mesh.get_half_edge(edge_id).angle, 6)
                for edge_id in vertex.incident_edges
            ]

            if len(angles) != len(set(angles)):
                print(
                    "SAME ANGLE",
                    vertex.id,
                    angles
                )

                

    # ---------------------------------------------------------

    def assign_next(self):

        mesh = self.project.mesh

        for edge in mesh.half_edges.values():

            twin = mesh.get_half_edge(edge.twin)
            if twin is None:
                continue

            destination = mesh.get_vertex(twin.origin)
            if destination is None:
                continue

            incident = destination.incident_edges

            if not incident:
                continue

            if len(incident) == 1:
                edge.next = twin.id
                continue

            edge.next = self.find_next_edge(
                edge,
                twin,
                destination,
                incident,
                mesh
            )

    def find_next_edge(
        self,
        edge,
        twin,
        vertex,
        incident,
        mesh
    ):

        index = incident.index(twin.id)

        n = len(incident)

        for i in range(1, n + 1):

            candidate_id = incident[(index - i) % n]

            if candidate_id == twin.id:
                continue

            candidate = mesh.get_half_edge(candidate_id)

            if candidate.origin != vertex.id:
                continue

            return candidate.id

        return twin.id
    # ---------------------------------------------------------

    def assign_prev(self):

        mesh = self.project.mesh

        for edge in mesh.half_edges.values():

            next_edge = mesh.get_half_edge(edge.next)

            next_edge.prev = edge.id

    # ---------------------------------------------------------

    def debug_degree_gt1_vertices(self):

        mesh = self.project.mesh

        DebugLogger.subtitle(
            "DEGREE > 1 VERTEX DEBUG"
        )

        count = 0

        for vertex in mesh.vertices.values():

            if len(vertex.incident_edges) <= 1:
                continue
        DebugLogger.item("")
        DebugLogger.item(f"Vertex ID : {vertex.id}")
        DebugLogger.item(
            f"Incident Edges : {vertex.incident_edges}"
        )

        # Açıları yüksek hassasiyetle göster
        for edge_id in vertex.incident_edges:

            edge = mesh.get_half_edge(edge_id)

            DebugLogger.item(
                f"    Edge {edge.id}  angle={edge.angle:.6f}"
            )

        # Mevcut detaylı debug
        for edge_id in vertex.incident_edges:

            edge = mesh.get_half_edge(edge_id)
            twin = mesh.get_half_edge(edge.twin)
            destination = mesh.get_vertex(twin.origin)

            DebugLogger.item(
                f"  Edge ID={edge.id}"
                f"  Origin={edge.origin}"
                f"  Destination={destination.id}"
                f"  Twin={edge.twin}"
                f"  Angle={edge.angle:.1f}"
                f"  Next={edge.next}"
                f"  Prev={edge.prev}"
            )


            count += 1

            if count >= 3:
                break

    # ---------------------------------------------------------

    def build(self):

        DebugLogger.section("NEXT PREV BUILDER")

        DebugLogger.value("Vertex", len(self.project.vertices))
        DebugLogger.value("HalfEdge", len(self.project.half_edges))

        self.calculate_angles()
        self.sort_incident_edges()
        self.assign_next()
        self.assign_prev()

        self.debug_degree_gt1_vertices()
