# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass

from SRC.models.wall_component import Orientation


@dataclass
class Grid:

    id: int

    orientation: Orientation

    coordinate: float

    axis_ids: list[int]