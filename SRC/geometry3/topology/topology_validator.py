# -*- coding: utf-8 -*-
"""
Geometry3

Topology Validator
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationResult:

    success: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ValidationError(Exception):

    def __init__(self, errors: list[str]):

        self.errors = errors

        message_lines = ["Topology validation failed:"]

        for index, error in enumerate(errors, start=1):
            message_lines.append(f"{index}. {error}")

        super().__init__("\n".join(message_lines))


class TopologyValidator:

    def __init__(self, mesh_or_project):

        self.mesh = self._resolve_mesh(mesh_or_project)

    # ---------------------------------------------------------

    @staticmethod
    def _resolve_mesh(mesh_or_project):

        if hasattr(mesh_or_project, "mesh"):
            return mesh_or_project.mesh

        if hasattr(mesh_or_project, "half_edges") and hasattr(mesh_or_project, "faces"):
            return mesh_or_project

        raise TypeError(
            "TopologyValidator expects a mesh or an object that has a 'mesh' attribute."
        )

    # ---------------------------------------------------------

    @staticmethod
    def _check_chain(start_edge_id, edge_by_id):

        local_order = []
        local_set = set()

        current_id = start_edge_id
        max_steps = max(1, len(edge_by_id) + 1)

        for _ in range(max_steps):

            if current_id in local_set:

                if current_id == start_edge_id:
                    return {
                        "status": "closed",
                        "path": local_order,
                    }

                loop_anchor = current_id

                return {
                    "status": "disconnected",
                    "path": local_order,
                    "reason": (
                        "chain enters a loop that does not return to its start "
                        f"(anchors at edge {loop_anchor})"
                    ),
                }

            edge = edge_by_id.get(current_id)

            if edge is None:
                return {
                    "status": "disconnected",
                    "path": local_order,
                    "reason": f"edge {current_id} is missing",
                }

            local_order.append(current_id)
            local_set.add(current_id)

            if edge.next is None:
                return {
                    "status": "disconnected",
                    "path": local_order,
                    "reason": f"edge {edge.id} has no next",
                }

            current_id = edge.next

        return {
            "status": "infinite",
            "path": local_order,
            "reason": (
                "next traversal exceeded safety limit; possible infinite loop or corrupted links"
            ),
        }

    # ---------------------------------------------------------

    def validate(self, raise_on_error: bool = True) -> ValidationResult:

        errors = []

        edge_by_id = dict(self.mesh.half_edges.items())
        face_by_id = dict(self.mesh.faces.items())
        vertex_by_id = dict(self.mesh.vertices.items())

        # 1-2-3-4-5: next/prev/twin integrity checks
        for edge in edge_by_id.values():

            if edge.next is None:
                errors.append(f"HalfEdge {edge.id}: next is None")
            elif edge.next not in edge_by_id:
                errors.append(
                    f"HalfEdge {edge.id}: next={edge.next} does not exist"
                )

            if edge.prev is None:
                errors.append(f"HalfEdge {edge.id}: prev is None")
            elif edge.prev not in edge_by_id:
                errors.append(
                    f"HalfEdge {edge.id}: prev={edge.prev} does not exist"
                )

            if edge.next in edge_by_id:
                next_edge = edge_by_id[edge.next]
                if next_edge.prev != edge.id:
                    errors.append(
                        f"HalfEdge {edge.id}: next.prev mismatch "
                        f"(next={next_edge.id}, next.prev={next_edge.prev})"
                    )

            if edge.prev in edge_by_id:
                prev_edge = edge_by_id[edge.prev]
                if prev_edge.next != edge.id:
                    errors.append(
                        f"HalfEdge {edge.id}: prev.next mismatch "
                        f"(prev={prev_edge.id}, prev.next={prev_edge.next})"
                    )

            if edge.twin is not None:
                twin_edge = edge_by_id.get(edge.twin)

                if twin_edge is None:
                    errors.append(
                        f"HalfEdge {edge.id}: twin={edge.twin} does not exist"
                    )
                elif twin_edge.twin != edge.id:
                    errors.append(
                        f"HalfEdge {edge.id}: twin.twin mismatch "
                        f"(twin={twin_edge.id}, twin.twin={twin_edge.twin})"
                    )

        # 6-7: face/outer_edge checks
        for face in face_by_id.values():

            outer_edge_id = getattr(face, "outer_edge", None)

            if outer_edge_id is None:
                errors.append(
                    f"Face {face.id}: outer_edge is missing or None"
                )
            elif outer_edge_id not in edge_by_id:
                errors.append(
                    f"Face {face.id}: outer_edge={outer_edge_id} does not exist"
                )

            for edge_id in face.edge_ids:

                edge = edge_by_id.get(edge_id)

                if edge is None:
                    errors.append(
                        f"Face {face.id}: edge {edge_id} does not exist"
                    )
                    continue

                if edge.face is None:
                    errors.append(
                        f"Face {face.id}: edge {edge.id} has face=None"
                    )
                elif edge.face != face.id:
                    errors.append(
                        f"Face {face.id}: edge {edge.id} references face {edge.face}"
                    )

        # 8: vertex incident_edges existence
        for vertex in vertex_by_id.values():

            for incident_edge_id in vertex.incident_edges:

                if incident_edge_id not in edge_by_id:
                    errors.append(
                        f"Vertex {vertex.id}: incident edge {incident_edge_id} does not exist"
                    )

        # 9-10: chain checks for infinite/disconnected traversal
        analyzed = set()

        for edge_id in edge_by_id:

            if edge_id in analyzed:
                continue

            chain_result = self._check_chain(edge_id, edge_by_id)

            for traversed_edge_id in chain_result["path"]:
                analyzed.add(traversed_edge_id)

            if chain_result["status"] == "infinite":
                errors.append(
                    "Infinite loop detected from edge "
                    f"{edge_id}: {chain_result['reason']}"
                )
            elif chain_result["status"] == "disconnected":
                preview = chain_result["path"][:10]
                errors.append(
                    "Disconnected chain detected from edge "
                    f"{edge_id}: {chain_result['reason']}; path={preview}"
                )

        result = ValidationResult(
            success=(len(errors) == 0),
            errors=errors,
            warnings=[],
        )

        if not result.success and raise_on_error:
            raise ValidationError(result.errors)

        return result
