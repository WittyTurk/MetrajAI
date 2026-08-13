# -*- coding: utf-8 -*-

from __future__ import annotations

from math import cos
from math import isfinite
from math import pi
from math import radians
from math import sin

from SRC.models.point import Point
from SRC.models.room import Room
from SRC.models.window import Window


class WindowMatcher:

    def __init__(self, offset: float = 0.05):

        self.offset = float(offset)

    # -------------------------------------------------

    def match(self, rooms: list[Room], windows: list[Window]) -> None:

        room_polygons: list[tuple[int, list[tuple[float, float]]]] = []

        for room in rooms:
            room_polygons.append((room.id, self._extract_polygon_points(room)))

        for window in windows:

            window.room_ids = []

            if window.position is None:
                continue

            left_point, right_point = self._test_points(
                window.position,
                window.rotation,
                self.offset,
            )

            matched_room_ids: list[int] = []

            for test_point in (left_point, right_point):
                room_id = self._find_room_id(test_point, room_polygons)

                if room_id is None:
                    continue

                if room_id in matched_room_ids:
                    continue

                matched_room_ids.append(room_id)

            window.room_ids = matched_room_ids

    # -------------------------------------------------

    def _test_points(self, position: Point, rotation: float, offset: float) -> tuple[Point, Point]:

        angle = self._to_radians(rotation)

        # Wall-normal direction derived from window rotation.
        nx = -sin(angle)
        ny = cos(angle)

        left_point = Point(
            position.x + (nx * offset),
            position.y + (ny * offset),
        )

        right_point = Point(
            position.x - (nx * offset),
            position.y - (ny * offset),
        )

        return left_point, right_point

    # -------------------------------------------------

    @staticmethod
    def _to_radians(rotation: float) -> float:

        try:
            angle = float(rotation)
        except (TypeError, ValueError):
            return 0.0

        if not isfinite(angle):
            return 0.0

        if abs(angle) > (2.0 * pi + 1e-9):
            return radians(angle)

        return angle

    # -------------------------------------------------

    def _find_room_id(
        self,
        point: Point,
        room_polygons: list[tuple[int, list[tuple[float, float]]]],
    ) -> int | None:

        for room_id, polygon_points in room_polygons:

            if self._is_point_in_polygon(point, polygon_points):
                return room_id

        return None

    # -------------------------------------------------

    def _extract_polygon_points(self, room: Room) -> list[tuple[float, float]]:

        polygon = getattr(room, "polygon", None)

        if polygon is None:
            return []

        candidates = (
            "points",
            "corners",
            "vertices",
            "coords",
            "coordinates",
        )

        raw_points = None

        for field_name in candidates:
            value = getattr(polygon, field_name, None)

            if value is not None:
                raw_points = value
                break

        if raw_points is None and isinstance(polygon, (list, tuple)):
            raw_points = polygon

        if raw_points is None:
            return []

        points: list[tuple[float, float]] = []

        for raw_point in raw_points:
            xy = self._to_xy(raw_point)

            if xy is None:
                return []

            points.append(xy)

        if len(points) >= 2 and points[0] == points[-1]:
            points = points[:-1]

        return points

    # -------------------------------------------------

    @staticmethod
    def _to_xy(value) -> tuple[float, float] | None:

        if value is None:
            return None

        if isinstance(value, Point):
            return (float(value.x), float(value.y))

        x = getattr(value, "x", None)
        y = getattr(value, "y", None)

        if x is not None and y is not None:
            try:
                return (float(x), float(y))
            except (TypeError, ValueError):
                return None

        if isinstance(value, (tuple, list)) and len(value) >= 2:
            try:
                return (float(value[0]), float(value[1]))
            except (TypeError, ValueError):
                return None

        return None

    # -------------------------------------------------

    def _is_point_in_polygon(self, point: Point, polygon: list[tuple[float, float]]) -> bool:

        if len(polygon) < 3:
            return False

        x = float(point.x)
        y = float(point.y)

        # Edge-inclusive check avoids missing near-boundary hits.
        for index in range(len(polygon)):
            x1, y1 = polygon[index]
            x2, y2 = polygon[(index + 1) % len(polygon)]

            if self._is_point_on_segment(x, y, x1, y1, x2, y2):
                return True

        inside = False

        for index in range(len(polygon)):
            x1, y1 = polygon[index]
            x2, y2 = polygon[(index + 1) % len(polygon)]

            intersects = ((y1 > y) != (y2 > y))

            if not intersects:
                continue

            x_at_y = x1 + ((y - y1) * (x2 - x1) / (y2 - y1))

            if x < x_at_y:
                inside = not inside

        return inside

    # -------------------------------------------------

    @staticmethod
    def _is_point_on_segment(
        px: float,
        py: float,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        epsilon: float = 1e-9,
    ) -> bool:

        cross = ((px - x1) * (y2 - y1)) - ((py - y1) * (x2 - x1))

        if abs(cross) > epsilon:
            return False

        min_x = min(x1, x2) - epsilon
        max_x = max(x1, x2) + epsilon
        min_y = min(y1, y2) - epsilon
        max_y = max(y1, y2) + epsilon

        return (min_x <= px <= max_x) and (min_y <= py <= max_y)
