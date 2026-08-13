# -*- coding: utf-8 -*-

from __future__ import annotations

from collections.abc import Iterable

from SRC.geometry3.topology.face import Face
from SRC.utils.debug_logger import DebugLogger


class FaceBuilder:

    def __init__(self, project):

        self.project = project
        self.reject_duplicate_edge = 0
        self.reject_duplicate_pair = 0
        self.reject_twin_adjacent = 0
        self.reject_few_vertices = 0
        self.reject_zero_area = 0

    # -------------------------------------------------

    def _trace_closed_loop(self, start_edge):

        mesh = self.project.mesh

        ordered_edges = []
        index_by_edge_id = {}

        current = start_edge

        safety_limit = max(1, len(mesh.half_edges) + 1)

        for _ in range(safety_limit):

            if current is None:
                return None

            if current.next is None:
                return None

            if current.id in index_by_edge_id:

                cycle_start_index = index_by_edge_id[current.id]

                # Closed loop is valid only when it returns to the start edge.
                if cycle_start_index != 0:
                    return None

                return ordered_edges

            index_by_edge_id[current.id] = len(ordered_edges)
            ordered_edges.append(current)

            current = mesh.get_half_edge(current.next)

        raise RuntimeError("Infinite face loop detected")

    # -------------------------------------------------

    @staticmethod
    def _rotate_to_smallest(sequence: list[int]) -> list[int]:

        if not sequence:
            return sequence

        best = sequence

        for shift in range(1, len(sequence)):

            candidate = sequence[shift:] + sequence[:shift]

            if candidate < best:
                best = candidate

        return best

    # -------------------------------------------------

    @classmethod
    def _cycle_signature(cls, edge_ids: Iterable[int]):

        ids = list(edge_ids)

        if not ids:
            return tuple()

        forward = cls._rotate_to_smallest(ids)
        reverse = cls._rotate_to_smallest(list(reversed(ids)))

        return tuple(forward) if forward <= reverse else tuple(reverse)

    # -------------------------------------------------

    @staticmethod
    def _undirected_cycle_signature(loop_edges):

        undirected_pairs = []

        for edge in loop_edges:

            if edge.twin is None:
                pair = (edge.id, edge.id)
            else:
                pair = (edge.id, edge.twin)
                if pair[0] > pair[1]:
                    pair = (pair[1], pair[0])

            undirected_pairs.append(pair)

        undirected_pairs.sort()

        return tuple(undirected_pairs)

    # -------------------------------------------------

    def _boundary_area(self, loop_edges):

        mesh = self.project.mesh

        points = []

        for edge in loop_edges:

            vertex = mesh.get_vertex(edge.origin)

            if vertex is None:
                return 0.0

            points.append((float(vertex.x), float(vertex.y)))

        if len(points) < 3:
            return 0.0

        cross_sum = 0.0

        for index in range(len(points)):

            x1, y1 = points[index]
            x2, y2 = points[(index + 1) % len(points)]

            cross_sum += (x1 * y2) - (x2 * y1)

        return abs(0.5 * cross_sum)

    # -------------------------------------------------

    def _is_simple_boundary(self, loop_edges):

        edge_ids = [edge.id for edge in loop_edges]

        if len(edge_ids) != len(set(edge_ids)):
            self.reject_duplicate_edge += 1
            return False

        undirected_pairs = set()

        for edge in loop_edges:

            if edge.twin is None:
                pair = (edge.id, edge.id)
            else:
                pair = (edge.id, edge.twin)
                if pair[0] > pair[1]:
                    pair = (pair[1], pair[0])

            if pair in undirected_pairs:
                self.reject_duplicate_pair += 1
            else:
                undirected_pairs.add(pair)

            undirected_pairs.add(pair)

        for index, edge in enumerate(loop_edges):

            next_edge = loop_edges[(index + 1) % len(loop_edges)]

            #if edge.twin is not None and next_edge.id == edge.twin:
            #   self.reject_twin_adjacent += 1
            #   return False

        unique_vertices = {edge.origin for edge in loop_edges}

        if len(unique_vertices) < 3:
            self.reject_few_vertices += 1
            return False

        area = self._boundary_area(loop_edges)

        if area <= 1e-8:
            self.reject_zero_area += 1
            return False

        return True

    # -------------------------------------------------

    def build(self):

        mesh = self.project.mesh

        mesh.faces.clear()

        for edge in mesh.half_edges.values():
            edge.face = None

        visited_edges = set()

        cycle_signatures = set()
        undirected_cycle_signatures = set()

        rejected_faces = 0
        accepted_faces = 0

        face_id = 1

        for edge in mesh.half_edges.values():

            if edge.id in visited_edges:
                continue

            loop_edges = self._trace_closed_loop(edge)

            if not loop_edges:
                visited_edges.add(edge.id)
                continue

            for loop_edge in loop_edges:
                visited_edges.add(loop_edge.id)

            face_edges = [loop_edge.id for loop_edge in loop_edges]

            cycle_signature = self._cycle_signature(face_edges)
            if cycle_signature in cycle_signatures:
                continue

            # -------------------------------------------------
            # PATCH-01 (TEMP)
            # Duplicate undirected cycle filtresi gecici olarak kapatıldı.
            # Ortak duvar kullanan odaların yanlıs elenip elenmedigini test ediyoruz.
            # -------------------------------------------------

            # undirected_signature = self._undirected_cycle_signature(loop_edges)

            # if undirected_signature in undirected_cycle_signatures:
            #     continue

            if not self._is_simple_boundary(loop_edges):
                # print()
                # print("REJECTED LOOP")
                print("Edge Count :", len(loop_edges))
                print("Edges :", [e.id for e in loop_edges])
                print("Origins :", [e.origin for e in loop_edges])

                rejected_faces += 1
                continue

            face = Face(
                id=face_id,
                edge_ids=face_edges
            )

            # Face API'de tanimli olmasa da DCEL beklentisi icin atanir.
            face.outer_edge = face_edges[0]

            mesh.add_face(face)

            for loop_edge in loop_edges:
                loop_edge.face = face.id

            cycle_signatures.add(cycle_signature)
            #undirected_cycle_signatures.add(undirected_signature)

            accepted_faces += 1

            face_id += 1

        DebugLogger.section("FACE BUILDER")
        DebugLogger.value("HalfEdge", len(mesh.half_edges))
        DebugLogger.value("Face", len(mesh.faces))

        DebugLogger.subtitle("ILK 10 FACE")

        for face in list(mesh.faces.values())[:10]:
            DebugLogger.item(
                f"Face {face.id}  edges={len(face.edge_ids)}"
            )

        DebugLogger.subtitle("FACE FILTER SUMMARY")
        DebugLogger.value("Rejected Faces", rejected_faces)
        DebugLogger.value("Accepted Faces", accepted_faces)
        DebugLogger.subtitle("BOUNDARY REJECT SUMMARY")
        DebugLogger.value("Duplicate Edge", self.reject_duplicate_edge)
        DebugLogger.value("Duplicate Pair", self.reject_duplicate_pair)
        DebugLogger.value("Twin Adjacent", self.reject_twin_adjacent)
        DebugLogger.value("Few Vertices", self.reject_few_vertices)
        DebugLogger.value("Zero Area", self.reject_zero_area)

        return mesh.faces
