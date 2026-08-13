# -*- coding: utf-8 -*-

from dataclasses import dataclass


@dataclass
class WallPair:

    wall1: object
    wall2: object

    @property
    def thickness(self):

        return self.wall1.midpoint.distance_to(
            self.wall2.midpoint
        )

    @property
    def average_length(self):

        return (
            self.wall1.length +
            self.wall2.length
        ) / 2

    def __repr__(self):

        return (
            f"WallPair("
            f"{self.wall1.id}, "
            f"{self.wall2.id}, "
            f"t={self.thickness:.2f})"
        )