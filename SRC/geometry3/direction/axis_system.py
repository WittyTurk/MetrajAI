# -*- coding: utf-8 -*-
"""
Geometry3 Axis System — duvar/eksen açı sınıflandırma.

  set_axes(0, 90)  → yatay / düşey ana yönler
  classify_angle(angle) → AXIS_1 | AXIS_2
  same_direction / opposite_direction / perpendicular
"""

from __future__ import annotations

import math
from typing import Optional


class AxisSystem:

    def __init__(self, axis1: Optional[float] = None, axis2: Optional[float] = None):
        self.axis1 = self.normalize_angle(axis1) if axis1 is not None else None
        self.axis2 = self.normalize_angle(axis2) if axis2 is not None else None

    # -------------------------------------------------

    @staticmethod
    def normalize_angle(angle: float) -> float:
        """0 .. 180 aralığına getir (yönsüz doğru açısı)."""
        a = angle % 180.0
        if a < 0:
            a += 180.0
        return a

    def set_axes(self, axis1: float, axis2: float) -> None:
        self.axis1 = self.normalize_angle(axis1)
        self.axis2 = self.normalize_angle(axis2)

    def set_from_degrees(self, a1_deg: float, a2_deg: float) -> None:
        self.set_axes(a1_deg, a2_deg)

    # -------------------------------------------------

    def angle_difference(self, a: float, b: float) -> float:
        diff = abs(self.normalize_angle(a) - self.normalize_angle(b))
        return min(diff, 180.0 - diff)

    def classify_angle(self, angle: float, tol: float = 20.0) -> Optional[str]:
        if self.axis1 is None:
            return None

        d1 = self.angle_difference(angle, self.axis1)
        d2 = (
            self.angle_difference(angle, self.axis2)
            if self.axis2 is not None
            else 999.0
        )

        if d1 <= d2 and d1 <= tol:
            return "AXIS_1"
        if self.axis2 is not None and d2 <= tol:
            return "AXIS_2"
        return None

    def same_direction(self, angle1: float, angle2: float, tolerance: float = 5.0) -> bool:
        return self.angle_difference(angle1, angle2) <= tolerance

    def opposite_direction(self, angle1: float, angle2: float, tolerance: float = 5.0) -> bool:
        """Aynı doğru, ters yön ≈ 180° fark → normalize'de 0'a yakın (aynı eksen).
        Yönlü 180 için harici atan2 farkı gerekir; burada 'aynı eksen' = same_direction.
        """
        return self.same_direction(angle1, angle2, tolerance)

    def perpendicular(self, angle1: float, angle2: float, tolerance: float = 5.0) -> bool:
        """Dik (≈ 90°). Eski opposite_direction aslında bunu yapıyordu."""
        diff = abs(self.angle_difference(angle1, angle2) - 90.0)
        return diff <= tolerance

    def is_axis1(self, angle: float, tol: float = 5.0) -> bool:
        if self.axis1 is None:
            return False
        return self.angle_difference(angle, self.axis1) <= tol

    def is_axis2(self, angle: float, tol: float = 5.0) -> bool:
        if self.axis2 is None:
            return False
        return self.angle_difference(angle, self.axis2) <= tol

    def snap_to_axis(self, angle: float) -> float:
        """Açıya en yakın ana eksen açısını döndür."""
        if self.axis1 is None:
            return self.normalize_angle(angle)
        c = self.classify_angle(angle, tol=45.0)
        if c == "AXIS_1":
            return self.axis1
        if c == "AXIS_2" and self.axis2 is not None:
            return self.axis2
        return self.normalize_angle(angle)