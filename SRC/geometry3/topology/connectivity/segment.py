# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from SRC.geometry3.topology.connectivity.node import Node


@dataclass(slots=True)
class Segment:

    id: int
    start_node: int
    end_node: int
    wall_id: int | None
    axis_id: int | None
    length: float
    direction_vector: tuple[float, float]

    @classmethod
    def from_nodes(
        cls,
        segment_id: int,
        start: Node,
        end: Node,
        wall_id: int | None,
        axis_id: int | None,
    ) -> "Segment":

        dx = float(end.x) - float(start.x)
        dy = float(end.y) - float(start.y)

        length = hypot(dx, dy)

        if length == 0.0:
            direction = (0.0, 0.0)
        else:
            direction = (dx / length, dy / length)

        return cls(
            id=segment_id,
            start_node=start.id,
            end_node=end.id,
            wall_id=wall_id,
            axis_id=axis_id,
            length=length,
            direction_vector=direction,
        )
