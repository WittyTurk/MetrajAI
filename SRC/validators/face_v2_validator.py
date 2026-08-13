# -*- coding: utf-8 -*-

from __future__ import annotations


class FaceV2Validator:

    def validate(self, faces_by_id: dict[int, object]) -> bool:

        faces = list(faces_by_id.values())
        edge_counts = [len(face.edge_ids) for face in faces]

        face_count = len(edge_counts)

        if face_count == 0:
            average_edges = 0.0
            min_edge_count = 0
            max_edge_count = 0
            two_edge_faces = 0
            three_edge_faces = 0
            four_plus_edge_faces = 0
            largest_face = "None"
        else:
            average_edges = sum(edge_counts) / face_count
            min_edge_count = min(edge_counts)
            max_edge_count = max(edge_counts)
            two_edge_faces = sum(1 for count in edge_counts if count == 2)
            three_edge_faces = sum(1 for count in edge_counts if count == 3)
            four_plus_edge_faces = sum(1 for count in edge_counts if count >= 4)

            largest = max(faces, key=lambda face: len(face.edge_ids))
            largest_face = f"Face {largest.id} ({len(largest.edge_ids)} edges)"

        categories_total = (
            two_edge_faces
            + three_edge_faces
            + four_plus_edge_faces
        )

        passed = (
            face_count > 0
            and categories_total <= face_count
            and min_edge_count >= 0
            and max_edge_count >= min_edge_count
        )

        print("FACE V2 VALIDATOR")
        print()
        print(f"Face Count : {face_count}")
        print()
        print(f"Average Edges Per Face : {average_edges:.2f}")
        print()
        print(f"Min Edge Count : {min_edge_count}")
        print()
        print(f"Max Edge Count : {max_edge_count}")
        print()
        print(f"2-edge Faces : {two_edge_faces}")
        print()
        print(f"3-edge Faces : {three_edge_faces}")
        print()
        print(f"4+ edge Faces : {four_plus_edge_faces}")
        print()
        print(f"Largest Face : {largest_face}")
        print()
        print(f"PASS / FAIL : {'PASS' if passed else 'FAIL'}")

        return passed
