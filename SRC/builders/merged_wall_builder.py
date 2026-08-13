# -*- coding: utf-8 -*-

from SRC.models.merged_wall import MergedWall
from SRC.models.point import Point
from SRC.utils.debug_logger import DebugLogger
from SRC.utils.geometry_key import GeometryKey


class MergedWallBuilder:

    def __init__(self, project):

        self.project = project
        self.segment_keys = set()

    # -------------------------------------------------

    def debug_selected_keys(self, wall, key):

        target_ids = {89, 90, 91, 99}

        if wall.id not in target_ids:
            return

        DebugLogger.item("")
        DebugLogger.item(f"MW{wall.id}")
        DebugLogger.item(f"repr(key) : {repr(key)}")
        DebugLogger.item(f"type(key) : {type(key)}")

        for index, value in enumerate(key):
            DebugLogger.item(
                f"key[{index}] = {value!r}  type={type(value)}"
            )

    # -------------------------------------------------

    def debug_duplicates(self):

        groups = {}

        for wall in self.project.merged_walls:

            key = GeometryKey.segment(
                wall.start,
                wall.end,
                thickness=wall.thickness,
                precision=None
            )

            self.debug_selected_keys(wall, key)

            groups.setdefault(key, []).append(wall)

        DebugLogger.section("MERGED WALL DUPLICATES")

        duplicate_count = 0

        for walls in groups.values():

            if len(walls) <= 1:
                continue

            duplicate_count += 1

            DebugLogger.item("")
            DebugLogger.item(f"Duplicate Count : {len(walls)}")

            for wall in walls:

                DebugLogger.item(
                    f"MergedWall ID : {wall.id}"
                )
                DebugLogger.item(
                    f"Start         : ({wall.start.x:.1f}, {wall.start.y:.1f})"
                )
                DebugLogger.item(
                    f"End           : ({wall.end.x:.1f}, {wall.end.y:.1f})"
                )
                DebugLogger.item(
                    f"Length        : {wall.length:.1f}"
                )
                DebugLogger.item(
                    f"Thickness     : {wall.thickness:.1f}"
                )

        if duplicate_count == 0:
            DebugLogger.item("No duplicate merged walls")

    # -------------------------------------------------

    def build(self):
        
        print()
        print("XXXXXXXXXX MERGED WALL BUILDER STARTED XXXXXXXXXX")
        print()
    
        self.project.merged_walls.clear()
        self.segment_keys.clear()

        original_pair_count = len(self.project.wall_pairs)
        skipped_duplicate = 0

        wall_id = 1

        for pair in self.project.wall_pairs:
            print(
                "PAIR",
                pair.wall1.id,
                pair.wall2.id,
                "T=",
                pair.thickness
             )

            w1 = pair.wall1
            w2 = pair.wall2

            if w1.is_horizontal:

                center_y = (w1.midpoint.y + w2.midpoint.y) / 2

                start_x = max(
                    min(w1.start.x, w1.end.x),
                    min(w2.start.x, w2.end.x)
                )

                end_x = min(
                    max(w1.start.x, w1.end.x),
                    max(w2.start.x, w2.end.x)
                )

                start = Point(start_x, center_y)
                end = Point(end_x, center_y)

                if end_x <= start_x:
                    print(
                        f"SKIP {pair.wall1.id}-{pair.wall2.id}"
                    )
                    continue

            else:

                center_x = (w1.midpoint.x + w2.midpoint.x) / 2

                start_y = max(
                    min(w1.start.y, w1.end.y),
                    min(w2.start.y, w2.end.y)
                )

                end_y = min(
                    max(w1.start.y, w1.end.y),
                    max(w2.start.y, w2.end.y)
                )

                start = Point(center_x, start_y)
                end = Point(center_x, end_y)

                if end_y <= start_y:
                    print(
                        f"SKIP {pair.wall1.id}-{pair.wall2.id}"
                    )
                    continue

            wall = MergedWall(
                id=wall_id,
                start=start,
                end=end,
                thickness=pair.thickness,
                source_pair=pair
            )

            if wall.length < 1:
                continue

            segment_key = GeometryKey.segment(
                start,
                end,
                thickness=pair.thickness
            )

            if segment_key in self.segment_keys:
                skipped_duplicate += 1
                continue

            self.segment_keys.add(segment_key)

            if wall.is_horizontal:
                print(f"H {wall.id}  {wall.start} -> {wall.end}")

            if wall.is_vertical:
                print(f"V {wall.id}  {wall.start} -> {wall.end}")

            self.project.merged_walls.append(wall)

            wall_id += 1

        print()
        print("=" * 40)
        print("MERGED WALLS")
        print("=" * 40)
        print(f"Toplam : {len(self.project.merged_walls)}")

        for wall in self.project.merged_walls:

            print(
                wall.id,
                f"({wall.start.x:.1f},{wall.start.y:.1f})",
                "->",
                f"({wall.end.x:.1f},{wall.end.y:.1f})"
            )

        print()
        print("WALL PAIRS =", len(self.project.wall_pairs))
        print("MERGED WALLS =", len(self.project.merged_walls))
        print("SKIPPED DUPLICATE =", skipped_duplicate)

        print()
        print("=" * 40)
        print("İLK 20 MERGED WALL")
        print("=" * 40)

        for wall in self.project.merged_walls[:20]:

            print(
                f"{wall.id:3} | "
                f"({wall.start.x:.1f},{wall.start.y:.1f}) -> "
                f"({wall.end.x:.1f},{wall.end.y:.1f}) | "
                f"L={wall.length:.1f} "
                f"T={wall.thickness:.1f}"
            )

        print()
        print("=" * 40)
        print("İLK 20 VERTICAL MERGED WALL")
        print("=" * 40)

        count = 0

        for wall in self.project.merged_walls:

            if abs(wall.start.x - wall.end.x) < 1:

                count += 1

                print(
                    f"{wall.id:3} | "
                    f"({wall.start.x:.1f},{wall.start.y:.1f}) -> "
                    f"({wall.end.x:.1f},{wall.end.y:.1f}) | "
                    f"L={wall.length:.1f}"
                )

                if count == 20:
                    break

            self.debug_duplicates()

            print()
            print("=" * 40)
            print("MERGED WALL DEDUP")
            print("=" * 40)
            print(f"Original Pair Count : {original_pair_count}")
            print(f"MergedWall Count    : {len(self.project.merged_walls)}")
            print(f"Skipped Duplicate   : {skipped_duplicate}")
