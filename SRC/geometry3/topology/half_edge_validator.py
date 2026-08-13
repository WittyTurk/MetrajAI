# -*- coding: utf-8 -*-

from __future__ import annotations


class HalfEdgeValidator:

    def __init__(self, project):
        self.project = project

    # ---------------------------------------------------------

    def validate(self):

        half_edges = self.project.half_edges
        vertices = self.project.vertices

        edge_by_id = {}
        vertex_ids = set()
        wall_counts = {}

        # ---------------------------------------------
        # 4. HalfEdge ID'leri benzersiz mi?
        # 3. Origin vertex mevcut mu?
        # 5. Aynı duvara ait tam iki HalfEdge var mı?
        # ---------------------------------------------

        for vertex in vertices:
            vertex_ids.add(vertex.id)

        for edge in half_edges:

            if edge.id in edge_by_id:
                return False

            edge_by_id[edge.id] = edge

            if edge.origin not in vertex_ids:
                return False

            wall_counts[edge.wall_id] = wall_counts.get(edge.wall_id, 0) + 1

        # ---------------------------------------------
        # 1. Twin var mı?
        # 2. Twin karşılıklı mı?
        # ---------------------------------------------

        for edge in half_edges:

            if edge.twin is None:
                return False

            twin = edge_by_id.get(edge.twin)

            if twin is None:
                return False

            if twin.twin != edge.id:
                return False

        # ---------------------------------------------
        # 5. Aynı duvara ait tam iki HalfEdge var mı?
        # ---------------------------------------------

        for count in wall_counts.values():
            if count != 2:
                return False

        return True
