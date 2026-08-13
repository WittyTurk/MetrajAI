"""
Geometry3
Intersection Splitter
"""

from __future__ import annotations


class IntersectionSplitter:

    # ---------------------------------------------------------

    def __init__(self, project):

        self.project = project

    # ---------------------------------------------------------

    def build(self):

        # raise Exception("INTERSECTION SPLITTER CALLED")

        print()
        print("=" * 40)
        print("INTERSECTION SPLITTER")
        print("=" * 40)

        print("Input Walls :", len(self.project.merged_walls))

        print()
        print("FIRST 20 WALLS")

        for wall in self.project.merged_walls[:20]:
            print(
                wall.id,
                f"({wall.start.x:.1f}, {wall.start.y:.1f})",
                "->",
                f"({wall.end.x:.1f}, {wall.end.y:.1f})"
            )
        print()
        print("VERTEX FREQUENCY")

        freq = {}

        for wall in self.project.merged_walls:

            p1 = (round(wall.start.x, 1), round(wall.start.y, 1))
            p2 = (round(wall.end.x, 1), round(wall.end.y, 1))

            freq[p1] = freq.get(p1, 0) + 1
            freq[p2] = freq.get(p2, 0) + 1

        for pt, count in sorted(freq.items(), key=lambda x: -x[1]):

            if count > 1:
                print(pt, "=>", count)

        return self.project.merged_walls

       