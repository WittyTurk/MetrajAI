# -*- coding: utf-8 -*-
"""
Geometry3

Topology HalfEdge
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HalfEdge:
    """
    Directed topological half-edge.

    Bir HalfEdge;

    - bir origin vertex'e sahiptir
    - twin half-edge ile eşleşir
    - opsiyonel olarak next/prev/face bağları taşır
    """

    id: int

    origin: int
    wall_id: int

    twin: int | None = None
    next: int | None = None
    prev: int | None = None
    face: int | None = None
    angle: float | None = None

    # ---------------------------------------------------------

    def __repr__(self):

        return (
            f"HalfEdge("
            f"id={self.id}, "
            f"origin={self.origin}, "
            f"twin={self.twin}, "
            f"wall={self.wall_id})"
        )
