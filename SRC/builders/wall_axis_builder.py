# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.models.point import Point
from SRC.models.wall import Wall
from SRC.models.wall_axis import WallAxis
from SRC.models.wall_component import Orientation
from SRC.models.wall_component import WallComponent


class WallAxisBuilder:

    def build(self, components: list[WallComponent]) -> list[WallAxis]:

        print(">>> WALL AXIS BUILDER EXECUTED <<<")

        axes: list[WallAxis] = []

        # One axis is produced per connected wall component.
        for axis_id, component in enumerate(components, start=1):
            print(
                "COMPONENT",
                axis_id,
                "WALL_COUNT=",
                len(component.walls),
                "WALL_IDS=",
                component.wall_ids[:20]
            )
            axis = self.build_component_axis(axis_id, component)
            axes.append(axis)
        print()
        print("=" * 40)
        print("WALL AXIS AUDIT")
        print("=" * 40)

        print("Axis Count :", len(axes))

        horizontal_count = 0
        vertical_count = 0

        for axis in axes:

            if axis.orientation == Orientation.HORIZONTAL:
                horizontal_count += 1

            elif axis.orientation == Orientation.VERTICAL:
                vertical_count += 1

        print("Horizontal Axis :", horizontal_count)
        print("Vertical Axis   :", vertical_count)
        total_length = 0.0
        long_axis = 0

        for axis in axes:

            dx = axis.end.x - axis.start.x
            dy = axis.end.y - axis.start.y

            length = (dx * dx + dy * dy) ** 0.5

            total_length += length

            if length > 5000:
                long_axis += 1

        print("Long Axis (>5000 mm):", long_axis)

        if len(axes):
            print("Average Length:", round(total_length / len(axes), 1))

        print()

        for axis in axes[:100]:

            print(
                f"Axis {axis.id:3d}",
                f"({axis.start.x:.1f},{axis.start.y:.1f})",
                "->",
                f"({axis.end.x:.1f},{axis.end.y:.1f})"
            )

        print("=" * 40)

        

        print()
        print("=" * 40)
        print("AXIS COORDINATES")
        print("=" * 40)

        for axis in axes:

            if axis.orientation == Orientation.HORIZONTAL:

                print(
                    axis.id,
                    "H",
                    round(axis.start.y, 1),
                    round(axis.length, 1)
                )

            else:

                print(
                    axis.id,
                    "V",
                    round(axis.start.x, 1),
                    round(axis.length, 1)
                )
  
        return axes
    

    # -------------------------------------------------

    def build_component_axis(
        self,
        axis_id: int,
        component: WallComponent,
    ) -> WallAxis:

        walls = component.walls
        first_wall = walls[0] if walls else None

        orientation = self.resolve_orientation(first_wall)
        thickness = self.resolve_thickness(first_wall)

        if not walls:
            return WallAxis(
                id=axis_id,
                component_id=component.id,
                orientation=orientation,
                thickness=thickness,
                start=Point(0.0, 0.0),
                end=Point(0.0, 0.0),
                source_wall_ids=component.wall_ids,
            )

        # Axis direction is selected from the first wall orientation.
        if orientation == Orientation.HORIZONTAL:
            start, end = self.build_horizontal_axis(component)

        elif orientation == Orientation.VERTICAL:
            start, end = self.build_vertical_axis(component)

        else:
            start = walls[0].start
            end = walls[0].end

        return WallAxis(
            id=axis_id,
            component_id=component.id,
            orientation=orientation,
            thickness=thickness,
            start=start,
            end=end,
            source_wall_ids=component.wall_ids,
        )

    # -------------------------------------------------

    def build_horizontal_axis(self, component: WallComponent) -> tuple[Point, Point]:

        walls = component.walls

        x_values: list[float] = []
        y_midpoints: list[float] = []

        for wall in walls:
            x_values.extend([wall.start.x, wall.end.x])
            y_midpoints.append(wall.midpoint.y)

        # Horizontal axis spans full x-range, y is mean centerline level.
        center_y = sum(y_midpoints) / len(y_midpoints)
        start_x = min(x_values)
        end_x = max(x_values)

        return Point(start_x, center_y), Point(end_x, center_y)

    # -------------------------------------------------

    def build_vertical_axis(self, component: WallComponent) -> tuple[Point, Point]:

        walls = component.walls

        x_midpoints: list[float] = []
        y_values: list[float] = []

        for wall in walls:
            x_midpoints.append(wall.midpoint.x)
            y_values.extend([wall.start.y, wall.end.y])

        # Vertical axis spans full y-range, x is mean centerline level.
        center_x = sum(x_midpoints) / len(x_midpoints)
        start_y = min(y_values)
        end_y = max(y_values)

        return Point(center_x, start_y), Point(center_x, end_y)

    # -------------------------------------------------

    def resolve_orientation(self, wall: Wall | None) -> Orientation:

        if wall is None:
            return Orientation.UNKNOWN

        if wall.is_horizontal:
            return Orientation.HORIZONTAL

        if wall.is_vertical:
            return Orientation.VERTICAL

        return Orientation.UNKNOWN

    # -------------------------------------------------

    def resolve_thickness(self, wall: Wall | None) -> float:

        if wall is None:
            return 0.0

        thickness = getattr(wall, "thickness", 0.0)

        try:
            return float(thickness)
        except (TypeError, ValueError):
            return 0.0

 
