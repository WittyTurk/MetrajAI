# -*- coding: utf-8 -*-


class IntersectionBuilder:

    def __init__(self, project):

        self.project = project

    # -------------------------------------------------

    def build(self):

        print()
        print("=" * 40)
        print("INTERSECTION BUILDER")
        print("=" * 40)

        horizontal = [
            wall
            for wall in self.project.merged_walls
            if wall.is_horizontal
        ]

        vertical = [
            wall
            for wall in self.project.merged_walls
            if wall.is_vertical
        ]

        print(f"Horizontal : {len(horizontal)}")
        print(f"Vertical   : {len(vertical)}")

        EPS = 1.0

        intersections = []

        for h in horizontal:

            y = h.start.y

            hx1 = min(h.start.x, h.end.x)
            hx2 = max(h.start.x, h.end.x)

            for v in vertical:

                x = v.start.x

                vy1 = min(v.start.y, v.end.y)
                vy2 = max(v.start.y, v.end.y)

                if (
                    hx1 - EPS <= x <= hx2 + EPS
                    and
                    vy1 - EPS <= y <= vy2 + EPS
                ):

                    intersections.append((x, y, h.id, v.id))

        print()
        print("İLK 20 KESİŞİM")
        print("-" * 40)

        for i, item in enumerate(intersections[:20], 1):

            x, y, hid, vid = item

            print(
                f"{i:3} : ({x:.2f}, {y:.2f})  H={hid}  V={vid}"
            )

        print()
        print(f"Toplam Kesişim : {len(intersections)}")

        self.project.intersections = intersections
