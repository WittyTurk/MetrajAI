# -*- coding: utf-8 -*-

from __future__ import annotations

import math

from SRC.utils.debug_logger import DebugLogger


class NextPrevBuilder:

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

            # Twin edge
            twin = mesh.get_half_edge(edge.twin)

            # Destination vertex
            vertex = mesh.get_vertex(twin.origin)

            edges = vertex.incident_edges

            # Twin'in listedeki yeri
            index = edges.index(twin.id)

            # CCW dolasim icin bir onceki edge
            next_index = (index - 1) % len(edges)

            edge.next = edges[next_index]

            if edge.next == edge.twin:

                twin = mesh.get_half_edge(edge.twin)
                vertex = mesh.get_vertex(twin.origin)

                if len(vertex.incident_edges) > 1:
                    print(
                        "BAD NEXT",
                        edge.id,
                        "->",
                        edge.next,
                        "degree =",
                        len(vertex.incident_edges)
                    )


            # print(f"Edge {edge.id} -> Next {edge.next}")

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
