# -*- coding: utf-8 -*-

from math import degrees
from SRC.models.wall_pair import WallPair


class WallMerge:

    def __init__(self, project):
        self.project = project

    def split_horizontal(self):

        return [
            wall
            for wall in self.project.walls
            if wall.is_horizontal
        ]

    def split_vertical(self):

        return [
            wall
            for wall in self.project.walls
            if wall.is_vertical
        ]

    # -------------------------------------------------

    def analyze(self):

        horizontal = self.split_horizontal()
        vertical = self.split_vertical()

        print()
        print("=" * 40)
        print("WALL GROUPS")
        print("=" * 40)
        print(f"Horizontal : {len(horizontal)}")
        print(f"Vertical   : {len(vertical)}")

        if not self.project.walls:
            return

    def parallel(self, wall1, wall2):

        a1 = abs(wall1.angle)
        a2 = abs(wall2.angle)

        diff = abs(a1 - a2)

        if diff > 3.14159265 / 2:
            diff = abs(diff - 3.14159265)

        return diff < 0.05

    def overlap(self, wall1, wall2):

        if wall1.is_horizontal and wall2.is_horizontal:

            a1, a2 = wall1.x_range
            b1, b2 = wall2.x_range

        elif wall1.is_vertical and wall2.is_vertical:

            a1, a2 = wall1.y_range
            b1, b2 = wall2.y_range

        else:
            return False

        overlap = min(a2, b2) - max(a1, b1)

        return overlap > 10

    def build(self):

        self.project.wall_pairs.clear()

        horizontal = self.split_horizontal()
        vertical = self.split_vertical()

        self.find_pairs(horizontal)
        self.find_pairs(vertical)

        print()
        print("=" * 40)
        print("WALL PAIRS")
        print("=" * 40)
        print(f"Horizontal : {len(horizontal)}")
        print(f"Vertical   : {len(vertical)}")
        print(f"WallPair   : {len(self.project.wall_pairs)}")

    # -------------------------------------------------

    def find_pairs(self, walls):

        candidate_count = 0

        for i in range(len(walls)):

            wall1 = walls[i]

            for j in range(i + 1, len(walls)):

                wall2 = walls[j]

                if not self.parallel(wall1, wall2):
                    continue

                # Uzunluk farkı
                if abs(wall1.length - wall2.length) > 5:
                    continue

                # Midpoint mesafesi
                distance = wall1.midpoint.distance_to(
                    wall2.midpoint
                )

                if distance < 10 or distance > 40:
                    continue
                if not self.overlap(wall1, wall2):
                    continue

                pair = WallPair(wall1, wall2)

                self.project.wall_pairs.append(pair)
