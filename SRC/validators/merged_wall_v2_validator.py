# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.models.merged_wall import MergedWall
from SRC.models.wall_axis import WallAxis


class MergedWallV2Validator:

    def validate(self, axes: list[WallAxis], merged_walls: list[MergedWall]) -> bool:

        axis_count = len(axes)
        merged_count = len(merged_walls)

        zero_length = 0
        geometry_keys: set[tuple[float, float, float, float, float]] = set()
        duplicate_geometry = 0

        for wall in merged_walls:

            if wall.length <= 0:
                zero_length += 1

            key = self.geometry_key(wall)

            if key in geometry_keys:
                duplicate_geometry += 1
            else:
                geometry_keys.add(key)

        passed = (
            axis_count == merged_count
            and zero_length == 0
            and duplicate_geometry == 0
        )

        print()
        print("=" * 40)
        print("MERGED WALL V2 VALIDATOR")
        print("=" * 40)
        print()
        print(f"Axis Count : {axis_count}")
        print()
        print(f"MergedWall Count : {merged_count}")
        print()
        print(f"Zero Length : {zero_length}")
        print()
        print(f"Duplicate Geometry : {duplicate_geometry}")
        print()

        if passed:
            print("MERGED WALL V2 VALIDATOR : PASS")
        else:
            print("MERGED WALL V2 VALIDATOR : FAIL")

        return passed

    # -------------------------------------------------

    def geometry_key(self, wall: MergedWall) -> tuple[float, float, float, float, float]:

        # Normalize segment direction so reversed start/end maps to same key.
        p1 = (round(wall.start.x, 4), round(wall.start.y, 4))
        p2 = (round(wall.end.x, 4), round(wall.end.y, 4))

        if p1 <= p2:
            a, b = p1, p2
        else:
            a, b = p2, p1

        thickness = round(float(wall.thickness), 4)

        return (a[0], a[1], b[0], b[1], thickness)
