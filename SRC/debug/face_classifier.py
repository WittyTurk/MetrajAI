# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.models.wall_axis import WallAxis
from SRC.models.wall_component import WallComponent


class FaceClassifier:

    def classify(
        self,
        project,
        wall_axes: list[WallAxis] | None = None,
        wall_components: list[WallComponent] | None = None,
    ) -> bool:

        mesh = project.mesh

        axes_by_id = {axis.id: axis for axis in (wall_axes or [])}
        components_by_id = {
            component.id: component
            for component in (wall_components or [])
        }

        total_face = len(mesh.faces)
        two_edge_face = 0
        four_plus_edge_face = 0

        same_axis_for_all_two_edge_faces = True
        same_component_for_all_two_edge_faces = True

        pair_counts: dict[tuple[int, int], int] = {}

        for face in mesh.faces.values():

            edge_ids = list(face.edge_ids)
            edge_count = len(edge_ids)

            if edge_count >= 4:
                four_plus_edge_face += 1

            if edge_count != 2:
                continue

            two_edge_face += 1

            pair_key = tuple(sorted(edge_ids))
            pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1

            print()
            print(f"Face ID : {face.id}")
            print(f"Edge Count : {edge_count}")
            print(f"Edge IDs : {edge_ids}")

            axis_ids: list[int | None] = []
            component_ids: list[int | None] = []

            for edge_id in edge_ids:

                edge = mesh.get_half_edge(edge_id)

                if edge is None:
                    print()
                    print(f"  Edge ID : {edge_id}")
                    print("  Origin Vertex : None")
                    print("  Destination Vertex : None")
                    print("  Twin : None")
                    print("  Next : None")
                    print("  Prev : None")
                    print("  WallAxis ID (varsa) : None")
                    print("  WallComponent ID (varsa) : None")

                    axis_ids.append(None)
                    component_ids.append(None)
                    continue

                destination_vertex = None

                if edge.twin is not None:
                    twin_edge = mesh.get_half_edge(edge.twin)
                    if twin_edge is not None:
                        destination_vertex = twin_edge.origin

                axis_id = self.resolve_axis_id(edge.wall_id, axes_by_id)
                component_id = self.resolve_component_id(
                    axis_id,
                    axes_by_id,
                    components_by_id,
                )

                axis_ids.append(axis_id)
                component_ids.append(component_id)

                print()
                print(f"  Edge ID : {edge.id}")
                print(f"  Origin Vertex : {edge.origin}")
                print(f"  Destination Vertex : {destination_vertex}")
                print(f"  Twin : {edge.twin}")
                print(f"  Next : {edge.next}")
                print(f"  Prev : {edge.prev}")
                print(f"  WallAxis ID (varsa) : {axis_id}")
                print(f"  WallComponent ID (varsa) : {component_id}")

            if (
                len(axis_ids) != 2
                or axis_ids[0] is None
                or axis_ids[1] is None
                or axis_ids[0] != axis_ids[1]
            ):
                same_axis_for_all_two_edge_faces = False

            if (
                len(component_ids) != 2
                or component_ids[0] is None
                or component_ids[1] is None
                or component_ids[0] != component_ids[1]
            ):
                same_component_for_all_two_edge_faces = False

        repeated_half_edge_pair = any(
            count > 1
            for count in pair_counts.values()
        )

        if two_edge_face == 0:
            same_axis_for_all_two_edge_faces = True
            same_component_for_all_two_edge_faces = True

        passed = (
            total_face > 0
            and same_axis_for_all_two_edge_faces
            and same_component_for_all_two_edge_faces
            and (not repeated_half_edge_pair)
        )

        print()
        print("=" * 40)
        print("FACE CLASSIFIER")
        print("=" * 40)
        print()
        print(f"Total Face : {total_face}")
        print()
        print(f"2-edge Face : {two_edge_face}")
        print()
        print(f"4+ edge Face : {four_plus_edge_face}")
        print()
        print(
            "2-edge yuzler ayni WallAxis uzerinde mi? : "
            f"{'YES' if same_axis_for_all_two_edge_faces else 'NO'}"
        )
        print()
        print(
            "2-edge yuzler ayni WallComponent icinde mi? : "
            f"{'YES' if same_component_for_all_two_edge_faces else 'NO'}"
        )
        print()
        print(
            "Ayni iki HalfEdge surekli tekrar ediyor mu? : "
            f"{'YES' if repeated_half_edge_pair else 'NO'}"
        )
        print()
        print(f"PASS / FAIL : {'PASS' if passed else 'FAIL'}")

        return passed

    # -------------------------------------------------

    def resolve_axis_id(
        self,
        wall_id: int,
        axes_by_id: dict[int, WallAxis],
    ) -> int | None:

        if not axes_by_id:
            return wall_id

        if wall_id in axes_by_id:
            return wall_id

        return None

    # -------------------------------------------------

    def resolve_component_id(
        self,
        axis_id: int | None,
        axes_by_id: dict[int, WallAxis],
        components_by_id: dict[int, WallComponent],
    ) -> int | None:

        if axis_id is None:
            return None

        axis = axes_by_id.get(axis_id)

        if axis is None:
            return None

        component_id = axis.component_id

        if not components_by_id:
            return component_id

        if component_id in components_by_id:
            return component_id

        return None
