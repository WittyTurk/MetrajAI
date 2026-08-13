# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from SRC.models.point import Point


Polygon = Any


@dataclass(slots=True)
class Room:

    # ---------- Identity ----------
    id: int
    face_id: int

    # ---------- Geometry ----------
    polygon: Polygon
    area: float
    perimeter: float
    centroid: Point

    # ---------- Topology ----------
    boundary_wall_ids: list[int]
    boundary_vertex_ids: list[int]
    boundary_halfedge_ids: list[int]

    # ---------- Building Elements ----------
    door_ids: list[int]
    window_ids: list[int]

    # ---------- Semantic ----------
    mahal_no: str | None = None
    mahal_name: str | None = None

    # ---------- Finishes ----------
    floor_finish: dict[str, Any] = field(default_factory=dict)
    wall_finish: dict[str, Any] = field(default_factory=dict)
    ceiling_finish: dict[str, Any] = field(default_factory=dict)

    # ---------- Project ----------
    level_id: int | None = None
    building_id: int | None = None
    parent_room_id: int | None = None

    # ---------- Status ----------
    is_external: bool = False
    is_valid: bool = True

    # ---------- Metadata ----------
    properties: dict[str, Any] = field(default_factory=dict)
