# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from SRC.models.wall import Wall


class Orientation(str, Enum):

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    UNKNOWN = "unknown"


@dataclass
class WallComponent:

    id: int
    wall_ids: list[int]
    walls: list[Wall]
    orientation: Orientation
    thickness: float

    @property
    def wall_count(self) -> int:

        return len(self.wall_ids)

    def __repr__(self) -> str:

        return (
            "WallComponent("
            f"id={self.id}, "
            f"wall_count={self.wall_count}, "
            f"orientation='{self.orientation.value}', "
            f"thickness={self.thickness:.2f}"
            ")"
        )
