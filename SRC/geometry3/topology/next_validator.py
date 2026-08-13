# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.utils.debug_logger import DebugLogger


class NextValidator:

    def __init__(self, project):
        self.project = project

    # ---------------------------------------------------------

    def validate(self):

        mesh = self.project.mesh

        missing_next = 0
        missing_prev = 0

        degree1 = 0
        degree_gt1 = 0

        twin_next_degree1 = 0
        twin_next_degree_gt1 = 0

        for edge in mesh.half_edges.values():

            if edge.next is None:
                missing_next += 1

            if edge.prev is None:
                missing_prev += 1

            vertex = mesh.get_vertex(edge.origin)
            degree = len(vertex.incident_edges)

            if degree == 1:

                degree1 += 1

                if edge.next == edge.twin:
                    twin_next_degree1 += 1

            else:

                degree_gt1 += 1

                if edge.next == edge.twin:
                    twin_next_degree_gt1 += 1

        # -----------------------------------------------------
        # Report
        # -----------------------------------------------------

        DebugLogger.section("NEXT VALIDATOR")

        DebugLogger.value("HalfEdge", len(mesh.half_edges))
        DebugLogger.value("MissingNext", missing_next)
        DebugLogger.value("MissingPrev", missing_prev)

        DebugLogger.subtitle("DEGREE STATS")

        DebugLogger.value("Degree=1", degree1)
        DebugLogger.value(">1 Degree", degree_gt1)

        DebugLogger.value("TwinNext d1", twin_next_degree1)
        DebugLogger.value("TwinNext d>1", twin_next_degree_gt1)

        ratio_degree1 = 0.0
        ratio_degree_gt1 = 0.0

        if degree1 > 0:
            ratio_degree1 = (twin_next_degree1 / degree1) * 100.0

        if degree_gt1 > 0:
            ratio_degree_gt1 = (twin_next_degree_gt1 / degree_gt1) * 100.0

        DebugLogger.value("d1 Twin %", f"{ratio_degree1:.1f}")
        DebugLogger.value("d>1 Twin %", f"{ratio_degree_gt1:.1f}")

        is_ok = (missing_next == 0 and missing_prev == 0)

        if is_ok:
            DebugLogger.success("NEXT/PREV assigned")
        else:
            DebugLogger.error("Missing NEXT/PREV found")

        if degree_gt1 > 0 and twin_next_degree_gt1 > 0:
            DebugLogger.warning("Degree>1 vertexlerde next==twin goruldu")

        return is_ok
