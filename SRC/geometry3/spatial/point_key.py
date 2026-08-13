# -*- coding: utf-8 -*-
"""
PointKey — tolerans ile kuantize nokta anahtarı.
Aynı hücredeki noktalar aynı node sayılır.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PointKey:
    ix: int
    iy: int

    @staticmethod
    def from_coordinates(x: float, y: float, tolerance: float) -> "PointKey":
        if tolerance <= 0:
            raise ValueError("Tolerance must be greater than zero.")
        return PointKey(
            ix=round(x / tolerance),
            iy=round(y / tolerance),
        )

    def to_coordinates(self, tolerance: float) -> tuple[float, float]:
        return (self.ix * tolerance, self.iy * tolerance)

    def __str__(self) -> str:
        return f"({self.ix}, {self.iy})"