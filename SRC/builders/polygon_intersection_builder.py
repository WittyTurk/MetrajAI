# -*- coding: utf-8 -*-


class PolygonIntersectionBuilder:

    def __init__(self, project):

        self.project = project

    # -------------------------------------------------

    def build(self):

        print()
        print("=" * 40)
        print("POLYGON INTERSECTION BUILDER")
        print("=" * 40)

        polygons = self.project.wall_polygons

        print(f"WallPolygon : {len(polygons)}")

        intersections = []

        for i, p1 in enumerate(polygons):

            xs1 = [p.x for p in p1.corners]
            ys1 = [p.y for p in p1.corners]

            minx1 = min(xs1)
            maxx1 = max(xs1)
            miny1 = min(ys1)
            maxy1 = max(ys1)

            for p2 in polygons[i + 1:]:

                xs2 = [p.x for p in p2.corners]
                ys2 = [p.y for p in p2.corners]

                minx2 = min(xs2)
                maxx2 = max(xs2)
                miny2 = min(ys2)
                maxy2 = max(ys2)

                if (
                    maxx1 >= minx2 and
                    maxx2 >= minx1 and
                    maxy1 >= miny2 and
                    maxy2 >= miny1
                ):

                    intersections.append((p1.id, p2.id))

        print()
        print("Intersection :", len(intersections))

        print()
        print("İLK 20")
        print("-" * 40)

        for a, b in intersections[:20]:
            print(a, "<->", b)
