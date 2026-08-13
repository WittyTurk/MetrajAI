# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.geometry3.topology.face import Face
from SRC.models.point import Point
from SRC.models.room import Room


class RoomBuilderV2:

    def __init__(self, faces: list[Face]):

        self.faces = faces

    # -------------------------------------------------

    @staticmethod
    def _is_outer_face(face: Face) -> bool:

        return bool(
            getattr(face, "outer", False)
            or getattr(face, "is_outer", False)
        )

    # -------------------------------------------------

    @staticmethod
    def _extract_polygon(face: Face):

        polygon = getattr(face, "polygon", None)

        if polygon is not None:
            return polygon

        return getattr(face, "face_polygon", None)

    # -------------------------------------------------

    @staticmethod
    def _extract_area(face: Face) -> float:

        area = getattr(face, "area", 0.0)

        try:
            return float(area)
        except (TypeError, ValueError):
            return 0.0

    # -------------------------------------------------

    @staticmethod
    def _extract_perimeter(face: Face, polygon) -> float:

        perimeter = getattr(face, "perimeter", None)

        if perimeter is not None:
            try:
                return float(perimeter)
            except (TypeError, ValueError):
                pass

        points = getattr(polygon, "points", None)
        if points is None:
            points = getattr(polygon, "corners", None)

        if not points or len(points) < 2:
            return 0.0

        total = 0.0

        for index in range(len(points)):
            p1 = points[index]
            p2 = points[(index + 1) % len(points)]

            x1 = float(getattr(p1, "x", 0.0))
            y1 = float(getattr(p1, "y", 0.0))
            x2 = float(getattr(p2, "x", 0.0))
            y2 = float(getattr(p2, "y", 0.0))

            dx = x2 - x1
            dy = y2 - y1

            total += (dx * dx + dy * dy) ** 0.5

        return total

    # -------------------------------------------------

    @staticmethod
    def _extract_centroid(face: Face, polygon) -> Point:

        centroid = getattr(face, "centroid", None)

        if centroid is None and polygon is not None:
            centroid = getattr(polygon, "centroid", None)

        if centroid is None:
            points = getattr(polygon, "points", None)
            if points is None:
                points = getattr(polygon, "corners", None)

            if points:
                sx = 0.0
                sy = 0.0

                for point in points:
                    sx += float(getattr(point, "x", 0.0))
                    sy += float(getattr(point, "y", 0.0))

                count = len(points)
                if count > 0:
                    return Point(sx / count, sy / count)

            return Point(0.0, 0.0)

        if isinstance(centroid, Point):
            return centroid

        if isinstance(centroid, (tuple, list)) and len(centroid) >= 2:
            return Point(float(centroid[0]), float(centroid[1]))

        x = getattr(centroid, "x", None)
        y = getattr(centroid, "y", None)

        if x is not None and y is not None:
            return Point(float(x), float(y))

        return Point(0.0, 0.0)

    # -------------------------------------------------

    @staticmethod
    def _extract_halfedge_ids(face: Face) -> list[int]:

        edge_ids = getattr(face, "edge_ids", None)

        if not edge_ids:
            edge_ids = getattr(face, "halfedge_ids", None)

        if not edge_ids:
            return []

        normalized: list[int] = []

        for edge_id in edge_ids:
            try:
                normalized.append(int(edge_id))
            except (TypeError, ValueError):
                continue

        return normalized

    # -------------------------------------------------

    @staticmethod
    def _extract_vertex_ids(face: Face) -> list[int]:

        vertex_ids = getattr(face, "vertex_ids", None)

        if vertex_ids is None:
            vertices = getattr(face, "vertices", None)
            if vertices:
                vertex_ids = [getattr(vertex, "id", vertex) for vertex in vertices]

        if not vertex_ids:
            return []

        normalized: list[int] = []

        for vertex_id in vertex_ids:
            try:
                normalized.append(int(vertex_id))
            except (TypeError, ValueError):
                continue

        return normalized

    # -------------------------------------------------

    @staticmethod
    def _extract_wall_ids(face: Face) -> list[int]:

        wall_ids = getattr(face, "wall_ids", None)

        if wall_ids is None:
            edges = getattr(face, "edges", None)
            if edges:
                wall_ids = [getattr(edge, "wall_id", None) for edge in edges]

        if not wall_ids:
            return []

        normalized: list[int] = []

        for wall_id in wall_ids:
            try:
                normalized.append(int(wall_id))
            except (TypeError, ValueError):
                continue

        return normalized

    # -------------------------------------------------

    def build(self) -> list[Room]:

        rooms: list[Room] = []

        room_id = 1

        for face in self.faces:

            halfedge_ids = self._extract_halfedge_ids(face)

            if len(halfedge_ids) == 2:
                continue

            if self._is_outer_face(face):
                continue

            polygon = self._extract_polygon(face)

            room = Room(
                id=room_id,
                face_id=int(getattr(face, "id")),
                polygon=polygon,
                area=self._extract_area(face),
                perimeter=self._extract_perimeter(face, polygon),
                centroid=self._extract_centroid(face, polygon),
                boundary_wall_ids=self._extract_wall_ids(face),
                boundary_vertex_ids=self._extract_vertex_ids(face),
                boundary_halfedge_ids=halfedge_ids,
                door_ids=[],
                window_ids=[],
                mahal_no=None,
                mahal_name=None,
            )

            rooms.append(room)

            room_id += 1

        return rooms
