# -*- coding: utf-8 -*-
"""
Geometry3

Room Builder
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite


@dataclass(slots=True)
class Room:

    id: int
    polygon: object
    area: float
    centroid: tuple[float, float]
    bounding_box: tuple[float, float, float, float]
    name: str = "Unknown"
    properties: dict = field(default_factory=dict)


class RoomBuilder:

    def __init__(self, project):

        self.project = project

    # ---------------------------------------------------------

    @staticmethod
    def _to_xy(point):

        if point is None:
            return None

        x = getattr(point, "x", None)
        y = getattr(point, "y", None)

        if x is None or y is None:

            if isinstance(point, (tuple, list)) and len(point) >= 2:
                x, y = point[0], point[1]
            else:
                return None

        try:
            x = float(x)
            y = float(y)
        except (TypeError, ValueError):
            return None

        if not (isfinite(x) and isfinite(y)):
            return None

        return (x, y)

    # ---------------------------------------------------------

    @classmethod
    def _extract_points(cls, polygon):

        candidates = (
            "points",
            "corners",
            "vertices",
            "coords",
            "coordinates",
        )

        raw_points = None

        for field_name in candidates:

            if hasattr(polygon, field_name):
                raw_points = getattr(polygon, field_name)
                break

        if raw_points is None:
            return []

        points = []

        for point in raw_points:
            xy = cls._to_xy(point)
            if xy is None:
                return []
            points.append(xy)

        if len(points) >= 2 and points[0] == points[-1]:
            points = points[:-1]

        return points

    # ---------------------------------------------------------

    @staticmethod
    def _signed_area(points):

        if len(points) < 3:
            return 0.0

        cross_sum = 0.0

        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]
            cross_sum += (x1 * y2) - (x2 * y1)

        return 0.5 * cross_sum

    # ---------------------------------------------------------

    @classmethod
    def _centroid(cls, points):

        signed_area = cls._signed_area(points)

        if abs(signed_area) < 1e-12:
            return None

        cx = 0.0
        cy = 0.0

        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]

            factor = (x1 * y2) - (x2 * y1)
            cx += (x1 + x2) * factor
            cy += (y1 + y2) * factor

        scale = 1.0 / (6.0 * signed_area)

        cx *= scale
        cy *= scale

        if not (isfinite(cx) and isfinite(cy)):
            return None

        return (cx, cy)

    # ---------------------------------------------------------

    @staticmethod
    def _bounding_box(points):

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        return (
            min(xs),
            min(ys),
            max(xs),
            max(ys),
        )

    # ---------------------------------------------------------

    def _iter_polygons(self):

        if hasattr(self.project, "polygons"):
            polygons = getattr(self.project, "polygons")
            if isinstance(polygons, dict):
                return list(polygons.values())
            if polygons is not None:
                return list(polygons)

        return []

    # ---------------------------------------------------------

    def build(self):

        polygons = self._iter_polygons()

        generated_rooms = []
        seen_polygon_ids = set()

        diagnostic = {
            "duplicate_vertices": 0,
            "area_too_small": 0,
            "centroid_failed": 0,
            "invalid_loop": 0,
            "self_intersection": 0,
            "less_than_3_unique_vertices": 0,
            "other": 0,
        }

        def reject(reason_key: str):

            diagnostic[reason_key] = diagnostic.get(reason_key, 0) + 1

        for polygon in polygons:

            polygon_id = getattr(polygon, "id", None)

            if polygon_id is None:
                reject("other")
                continue

            if polygon_id in seen_polygon_ids:
                reject("other")
                continue

            area = getattr(polygon, "area", None)

            if area is None:
                reject("other")
                continue

            try:
                area = float(area)
            except (TypeError, ValueError):
                reject("other")
                continue

            if not isfinite(area):
                reject("other")
                continue

            if abs(area) < 1e-8:
                reject("area_too_small")
                continue

            points = self._extract_points(polygon)

            if len(points) < 3:
                reject("invalid_loop")
                continue

            unique_points = set(points)
            if len(unique_points) < 3:
                reject("less_than_3_unique_vertices")
                continue

            signed_area = abs(self._signed_area(points))
            if signed_area < 1e-12:
                if len(unique_points) < len(points):
                    reject("duplicate_vertices")
                else:
                    reject("area_too_small")
                continue

            centroid = self._centroid(points)
            if centroid is None:
                reject("centroid_failed")
                continue

            bounding_box = self._bounding_box(points)

            room = Room(
            id=polygon_id,
            face_id=polygon_id,

            polygon=polygon,
            area=area,
            perimeter=0.0,
            centroid=centroid,

            boundary_wall_ids=[],
            boundary_vertex_ids=[],
            boundary_halfedge_ids=[],

            door_ids=[],
            window_ids=[],

            mahal_no=None,
            mahal_name="Unknown",

            floor_finish={},
            wall_finish={},
            ceiling_finish={},

            properties={},
    
         )
            

            generated_rooms.append(room)
            seen_polygon_ids.add(polygon_id)

        self.project.rooms = generated_rooms

        print()
        print("ROOM BUILDER DIAGNOSTIC")
        print()
        print(f"Duplicate vertices : {diagnostic['duplicate_vertices']}")
        print()
        print(f"Area too small : {diagnostic['area_too_small']}")
        print()
        print(f"Centroid failed : {diagnostic['centroid_failed']}")
        print()
        print(f"Invalid loop : {diagnostic['invalid_loop']}")
        print()
        print(f"Self intersection : {diagnostic['self_intersection']}")
        print()
        print(
            "Less than 3 unique vertices : "
            f"{diagnostic['less_than_3_unique_vertices']}"
        )
        print()
        print(f"Other : {diagnostic['other']}")
        print()
        print(f"Room Created : {len(self.project.rooms)}")

        return self.project.rooms
