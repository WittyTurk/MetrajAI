# -*- coding: utf-8 -*-

from SRC.models.wall_polygon import WallPolygon


class WallPolygonBuilder:

    def __init__(self, project):

        self.project = project

    # -------------------------------------------------

    def build(self):

        print()
        print("=" * 40)
        print("WALL POLYGON BUILDER")
        print("=" * 40)

        self.project.wall_polygons.clear()

        polygon_id = 1

        for wall in self.project.merged_walls:

            polygon = WallPolygon(
                id=polygon_id,
                merged_wall=wall,
                corners=wall.corners
            )

            self.project.wall_polygons.append(polygon)

            polygon_id += 1

        print(
            f"WallPolygon : {len(self.project.wall_polygons)}"
        )

        print()
        print("İLK 5 WALL POLYGON")
        print("-" * 40)

        for polygon in self.project.wall_polygons[:5]:

            print(
                polygon.id,
                len(polygon.corners),
                polygon.corners
            )
