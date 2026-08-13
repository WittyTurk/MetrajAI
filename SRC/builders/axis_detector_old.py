# -*- coding: utf-8 -*-

from collections import defaultdict


class AxisDetector:

    TOLERANCE = 100.0 

    def __init__(self, project):

        self.project = project

    # -------------------------------------------------

    def detect(self):

        print()
        print("=" * 40)

        print("AKS ANALYSIS")
        print("=" * 40)

        vertical = []
        horizontal = []

        for e in self.project.modelspace:

            if e.dxf.layer != "AKS":
                continue

            if e.dxftype() != "LINE":
                continue

            x1 = e.dxf.start.x
            y1 = e.dxf.start.y
            x2 = e.dxf.end.x
            y2 = e.dxf.end.y

            if abs(x1 - x2) < 1.0:
                vertical.append(round(x1, 1))

            elif abs(y1 - y2) < 1.0:
                horizontal.append(round(y1, 1))

        print("Vertical AKS Lines   :", len(vertical))
        print("Horizontal AKS Lines :", len(horizontal))

        print()

        print("VERTICAL AKS X VALUES")

        for e in self.project.modelspace:

            if e.dxf.layer != "AKS":
                continue

            if e.dxftype() != "LINE":
                continue

            x1 = e.dxf.start.x
            y1 = e.dxf.start.y
            x2 = e.dxf.end.x
            y2 = e.dxf.end.y

            if abs(x1 - x2) < 1.0:
                print(round(x1,1))

        print()
        print("=" * 40)
        print("AXIS DETECTOR INPUT")
        print("=" * 40)

        print("Wall Count =", len(self.project.walls))

        x_axes = self.detect_vertical_axes()
        y_axes = self.detect_horizontal_axes()

        print()
        print("=" * 40)
        print("AXIS DETECTOR")
        print("=" * 40)

        print("XX Axis Count :", len(x_axes))
        print("YY Axis Count :", len(y_axes))

        print()
        print("XX POSITIONS")

        for x in x_axes:
            print(round(x, 1))

        print()
        print("YY POSITIONS")

        for y in y_axes:
            print(round(y, 1))



    # -------------------------------------------------

    def detect_vertical_axes(self):

        values = []

        print()
        print("VERTICAL WALLS USED")

        for wall in self.project.walls:

            if not wall.is_vertical:
                continue

            if wall.length < 500:
                continue

            print(
                wall.id,
                "x=",
                round(wall.midpoint.x, 1),
                "len=",
                round(wall.length, 1)
            )

            values.append(wall.midpoint.x)

        print()
        print("Vertical walls used :", len(values))

        return self.cluster(values)

    # -------------------------------------------------

    def detect_horizontal_axes(self):

        values = []

        print()
        print("HORIZONTAL WALLS USED")

        for wall in self.project.walls:

            if not wall.is_horizontal:
                continue

            if wall.length < 500:
                continue

            print(
                wall.id,
                "y=",
                round(wall.midpoint.y, 1),
                "len=",
                round(wall.length, 1)
            )

            values.append(wall.midpoint.y)

        print()
        print("Horizontal walls used :", len(values))

        return self.cluster(values)



    # -------------------------------------------------

    def cluster(self, values):

        values = sorted(values)

        if not values:
            return []

        groups = []

        current = [values[0]]

        for value in values[1:]:

            if abs(value - current[-1]) <= self.TOLERANCE:
                current.append(value)

            else:
                groups.append(current)
                current = [value]

        groups.append(current)

        print()
        print("CLUSTERS")

        for group in groups:
            print(
                len(group),
                "items ->",
                round(sum(group) / len(group), 1)
            )

        result = []

        for group in groups:
            result.append(sum(group) / len(group))

        filtered = []

        for x in result:

            if not filtered:
                filtered.append(x)
                continue

            if abs(x - filtered[-1]) >= 2000:
                filtered.append(x)

        return filtered

        