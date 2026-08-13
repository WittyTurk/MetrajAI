# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.models.wall import Wall
from SRC.models.wall_component import Orientation
from SRC.models.wall_component import WallComponent


class WallComponentValidator:

    def validate(
        self,
        components: list[WallComponent],
        thickness_tolerance: float = 0.01,
    ) -> bool:

        component_count = len(components)
        total_walls = 0
        duplicate_wall_ids = 0
        missing_wall_ids = 0
        orientation_errors = 0
        thickness_errors = 0

        seen_ids: set[int] = set()

        for component in components:

            # Empty components are considered invalid.
            if component.wall_count == 0:
                missing_wall_ids += 1

            if len(component.wall_ids) != len(component.walls):
                missing_wall_ids += abs(len(component.wall_ids) - len(component.walls))

            total_walls += len(component.wall_ids)

            for wall_id in component.wall_ids:
                if wall_id in seen_ids:
                    duplicate_wall_ids += 1
                else:
                    seen_ids.add(wall_id)

            for wall in component.walls:
                if self.wall_orientation(wall) != component.orientation:
                    orientation_errors += 1

                wall_thickness = self.wall_thickness(wall)

                if abs(wall_thickness - component.thickness) > thickness_tolerance:
                    thickness_errors += 1

        passed = (
            missing_wall_ids == 0
            and duplicate_wall_ids == 0
            and orientation_errors == 0
            and thickness_errors == 0
        )

        print()
        print("=" * 40)
        print("WALL COMPONENT VALIDATOR")
        print("=" * 40)
        print()
        print(f"Component Count : {component_count}")
        print()
        print(f"Total Walls : {total_walls}")
        print()
        print(f"Duplicate Wall IDs : {duplicate_wall_ids}")
        print()
        print(f"Missing Wall IDs : {missing_wall_ids}")
        print()
        print(f"Orientation Errors : {orientation_errors}")
        print()
        print(f"Thickness Errors : {thickness_errors}")
        print()

        if passed:
            print("WALL COMPONENT VALIDATOR : PASS")
        else:
            print("WALL COMPONENT VALIDATOR : FAIL")

        return passed

    # -------------------------------------------------

    def wall_orientation(self, wall: Wall) -> Orientation:

        if wall.is_horizontal:
            return Orientation.HORIZONTAL

        if wall.is_vertical:
            return Orientation.VERTICAL

        return Orientation.UNKNOWN

    # -------------------------------------------------

    def wall_thickness(self, wall: Wall) -> float:

        thickness = getattr(wall, "thickness", 0.0)

        try:
            return float(thickness)
        except (TypeError, ValueError):
            return 0.0
