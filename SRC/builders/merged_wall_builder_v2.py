# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.models.merged_wall import MergedWall
from SRC.models.wall_axis import WallAxis


class MergedWallBuilderV2:

    def build(self, axes: list[WallAxis]) -> list[MergedWall]:

        print()
        print("=" * 40)
        print("MERGED WALL BUILDER V2")
        print("=" * 40)
        print("AXIS COUNT =", len(axes))

        merged_walls: list[MergedWall] = []

        
        # One merged wall is generated directly from each axis.
        for wall_id, axis in enumerate(axes, start=1):
            merged_wall = MergedWall(
                id=wall_id,
                start=axis.start,
                end=axis.end,
                thickness=axis.thickness,
                source_pair=None,
            )

            merged_walls.append(merged_wall)
            print(
                wall_id,
                f"({axis.start.x:.1f},{axis.start.y:.1f})",
                "->",
                f"({axis.end.x:.1f},{axis.end.y:.1f})"
            )

        return merged_walls
