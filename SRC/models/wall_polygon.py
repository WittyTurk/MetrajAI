# -*- coding: utf-8 -*-


class WallPolygon:

    def __init__(
        self,
        id,
        merged_wall,
        corners
    ):

        self.id = id
        self.merged_wall = merged_wall
        self.corners = corners

    def __repr__(self):

        return (
            f"WallPolygon("
            f"id={self.id}, "
            f"corners={len(self.corners)})"
        )
