# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

WEIGHT_KG_PER_M: Dict[int, float] = {
    6: 0.222, 8: 0.395, 10: 0.617, 12: 0.888, 14: 1.208,
    16: 1.578, 18: 2.000, 20: 2.466, 22: 2.984, 24: 3.551,
    25: 3.853, 28: 4.834, 32: 6.313,
}


@dataclass
class RebarLine:
    id: int
    element: str          # radye | bag_kiris | doseme | kolon | kiris | parapet
    diameter_mm: float
    length_m: float
    count: int
    floor: str = "GENEL"
    note: str = ""
    axis_ref: str = ""

    @property
    def unit_weight(self) -> float:
        d = int(round(self.diameter_mm))
        return WEIGHT_KG_PER_M.get(d, (d / 2) ** 2 * 0.006165)

    @property
    def total_length_m(self) -> float:
        return self.length_m * self.count

    @property
    def weight_kg(self) -> float:
        return self.total_length_m * self.unit_weight


@dataclass
class RebarSchedule:
    lines: List[RebarLine] = field(default_factory=list)
    floor: str = "GENEL"

    def by_element(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for ln in self.lines:
            out[ln.element] = out.get(ln.element, 0.0) + ln.weight_kg
        return out

    def by_diameter(self) -> Dict[float, float]:
        out: Dict[float, float] = {}
        for ln in self.lines:
            out[ln.diameter_mm] = out.get(ln.diameter_mm, 0.0) + ln.weight_kg
        return out

    @property
    def total_kg(self) -> float:
        return sum(ln.weight_kg for ln in self.lines)

    def report(self) -> None:
        print()
        print("=" * 55)
        print("DEMİR METRAJ (aks grid)")
        print("=" * 55)
        for el, kg in sorted(self.by_element().items()):
            print(f"  {el:12}  {kg:10.1f} kg")
        print("-" * 55)
        print(f"  {'TOPLAM':12}  {self.total_kg:10.1f} kg  ({self.total_kg/1000:.2f} ton)")
        print("\nÇapa göre:")
        for d, kg in sorted(self.by_diameter().items()):
            print(f"  Ø{d:.0f}  →  {kg:.1f} kg")
