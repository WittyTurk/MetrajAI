# -*- coding: utf-8 -*-
"""
Radye donatı — uydurma yok.

Alan: aks + 2×overhang (standart overhang_m=1.0)
Kalınlık: proje.json / DXF (0 ise beton 0)
Donatı: Ø ve aralık > 0 olan katmanlar; 0 olan atlanır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from SRC.structural.rebar_models import RebarLine, RebarSchedule, WEIGHT_KG_PER_M
from SRC.structural.axis_grid import AxisGrid


@dataclass
class RaftRebarSpec:
    """Şartname / detay / proje.json. dia veya spacing 0 → katman yok."""
    thickness_cm: float = 0.0
    cover_cm: float = 5.0

    bot_x_dia: float = 0.0
    bot_x_spacing_cm: float = 0.0
    bot_y_dia: float = 0.0
    bot_y_spacing_cm: float = 0.0

    top_x_dia: float = 0.0
    top_x_spacing_cm: float = 0.0
    top_y_dia: float = 0.0
    top_y_spacing_cm: float = 0.0

    lap_factor: float = 40.0

    col_starter_dia: float = 0.0
    col_starter_count: int = 0
    col_starter_length_m: float = 0.0

    wall_starter_dia: float = 0.0
    wall_starter_spacing_cm: float = 0.0
    wall_starter_length_m: float = 0.0

    tie_b_cm: float = 0.0
    tie_h_cm: float = 0.0
    tie_long_dia: float = 0.0
    tie_long_count: int = 0
    tie_stirrup_dia: float = 0.0
    tie_stirrup_spacing_cm: float = 0.0
    tie_starter_extra_m: float = 0.0

    col_zone_stirrup_dia: float = 0.0
    col_zone_stirrup_count: int = 0
    col_zone_stirrup_len_factor: float = 0.9

    def mesh_ok(self) -> bool:
        layers = [
            (self.bot_x_dia, self.bot_x_spacing_cm),
            (self.bot_y_dia, self.bot_y_spacing_cm),
            (self.top_x_dia, self.top_x_spacing_cm),
            (self.top_y_dia, self.top_y_spacing_cm),
        ]
        return any(d > 0 and s > 0 for d, s in layers)


@dataclass
class RaftGeometry:
    length_x_m: float
    length_y_m: float
    area_m2: float
    source: str = "axis_grid"
    overhang_m: float = 1.0

    @classmethod
    def from_grid(cls, grid: AxisGrid, overhang_m: float = 1.0) -> "RaftGeometry":
        lx = grid.total_x_m + 2.0 * overhang_m
        ly = grid.total_y_m + 2.0 * overhang_m
        if lx <= 0 or ly <= 0:
            raise ValueError("Radye boyut geçersiz")
        area = lx * ly
        print()
        print("=" * 55)
        print("RADYE GEOMETRİ (aks + taşma)")
        print("=" * 55)
        print(f"  Aks X {grid.total_x_m:.2f} + 2×{overhang_m:.2f} → L={lx:.2f} m")
        print(f"  Aks Y {grid.total_y_m:.2f} + 2×{overhang_m:.2f} → B={ly:.2f} m")
        print(f"  Alan  {area:.2f} m²")
        return cls(lx, ly, area, f"axis_grid+{overhang_m}m", overhang_m)

    @classmethod
    def from_area(
        cls, area_m2: float, length_x_m: float = 0.0, length_y_m: float = 0.0
    ) -> "RaftGeometry":
        if length_x_m <= 0 or length_y_m <= 0:
            side = math.sqrt(max(area_m2, 0.0))
            length_x_m = length_y_m = side
        return cls(length_x_m, length_y_m, area_m2, "area")


class RaftRebarCalculator:
    def __init__(
        self,
        geom: RaftGeometry,
        spec: RaftRebarSpec,
        grid: Optional[AxisGrid] = None,
        n_columns: int = 0,
        column_sections: Optional[List[Tuple[float, float]]] = None,
        floor: str = "TEMEL",
    ):
        self.geom = geom
        self.spec = spec
        self.grid = grid
        self.n_columns = n_columns
        self.column_sections = column_sections or []
        self.floor = floor

    def build(self) -> RebarSchedule:
        lines: List[RebarLine] = []
        if not self.spec.mesh_ok():
            print("! Radye hasır: Ø/aralık yok — mesh demir 0 (uydurma yok)")
        else:
            lines.extend(self._bottom_mesh())
            lines.extend(self._top_mesh())

        if self.spec.col_starter_dia > 0 and self.spec.col_starter_count > 0:
            lines.extend(self._column_starters())
        if self.spec.tie_long_dia > 0 and self.grid is not None:
            lines.extend(self._tie_beams())

        schedule = RebarSchedule(lines=lines, floor=self.floor)
        self._print_raft_summary(schedule)
        return schedule

    def _lap_m(self, dia_mm: float) -> float:
        return self.spec.lap_factor * (dia_mm / 1000.0)

    def _mesh_bars(
        self, element: str, note: str, bar_dir: str, dia: float, spacing_cm: float
    ) -> Optional[RebarLine]:
        if dia <= 0 or spacing_cm <= 0:
            return None
        lx, ly = self.geom.length_x_m, self.geom.length_y_m
        lap = self._lap_m(dia)
        if bar_dir == "X":
            bar_len = lx + 2 * lap
            n = max(1, int(math.floor((ly * 100) / spacing_cm)) + 1)
        else:
            bar_len = ly + 2 * lap
            n = max(1, int(math.floor((lx * 100) / spacing_cm)) + 1)
        return RebarLine(
            id=0,
            element=element,
            diameter_mm=dia,
            length_m=bar_len,
            count=n,
            floor=self.floor,
            note=note,
            axis_ref=f"A={self.geom.area_m2:.1f}m2",
        )

    def _bottom_mesh(self) -> List[RebarLine]:
        s = self.spec
        out = []
        for line in (
            self._mesh_bars("radye", "alt X", "X", s.bot_x_dia, s.bot_x_spacing_cm),
            self._mesh_bars("radye", "alt Y", "Y", s.bot_y_dia, s.bot_y_spacing_cm),
        ):
            if line:
                out.append(line)
        return out

    def _top_mesh(self) -> List[RebarLine]:
        s = self.spec
        out = []
        for line in (
            self._mesh_bars("radye", "ust X", "X", s.top_x_dia, s.top_x_spacing_cm),
            self._mesh_bars("radye", "ust Y", "Y", s.top_y_dia, s.top_y_spacing_cm),
        ):
            if line:
                out.append(line)
        return out

    def _column_starters(self) -> List[RebarLine]:
        s = self.spec
        n_col = self.n_columns or 0
        if n_col <= 0 and self.grid is not None:
            n_col = len(self.grid.x_labels) * len(self.grid.y_labels)
        if n_col <= 0 or s.col_starter_dia <= 0 or s.col_starter_count <= 0:
            return []
        thick_m = s.thickness_cm / 100.0 if s.thickness_cm > 0 else 0.0
        L = s.col_starter_length_m or (thick_m + self._lap_m(s.col_starter_dia) + 0.5)
        total = n_col * s.col_starter_count
        return [
            RebarLine(
                id=0,
                element="radye",
                diameter_mm=s.col_starter_dia,
                length_m=L,
                count=total,
                floor=self.floor,
                note="kolon filizi",
            )
        ]

    def _tie_beams(self) -> List[RebarLine]:
        s = self.spec
        if s.tie_long_dia <= 0 or self.grid is None:
            return []
        lines = []
        for yl in self.grid.y_labels:
            L = self.grid.total_x_m + 2 * self._lap_m(s.tie_long_dia)
            lines.append(
                RebarLine(
                    id=0,
                    element="bag_kiris",
                    diameter_mm=s.tie_long_dia,
                    length_m=L,
                    count=max(1, s.tie_long_count),
                    floor=self.floor,
                    note=f"bag X @{yl}",
                )
            )
        for xl in self.grid.x_labels:
            L = self.grid.total_y_m + 2 * self._lap_m(s.tie_long_dia)
            lines.append(
                RebarLine(
                    id=0,
                    element="bag_kiris",
                    diameter_mm=s.tie_long_dia,
                    length_m=L,
                    count=max(1, s.tie_long_count),
                    floor=self.floor,
                    note=f"bag Y @{xl}",
                )
            )
        return lines

    def _print_raft_summary(self, schedule: RebarSchedule) -> None:
        print()
        print("=" * 55)
        print("RADYE TEMEL DONATISI")
        print("=" * 55)
        print(f"Alan : {self.geom.area_m2:.2f} m² ({self.geom.source})")
        print(f"Ölçü : {self.geom.length_x_m:.2f} × {self.geom.length_y_m:.2f} m")
        print(f"Kalınlık : {self.spec.thickness_cm:.0f} cm")
        print(f"Bindirme : {self.spec.lap_factor:.0f}Ø")
        by: Dict[str, float] = {}
        total = 0.0
        for ln in schedule.lines:
            w = getattr(ln, "weight_kg", None)
            if w is None:
                w = ln.count * ln.length_m * WEIGHT_KG_PER_M.get(int(ln.diameter_mm), 0)
            by[ln.element] = by.get(ln.element, 0.0) + w
            total += w
        for k, v in sorted(by.items()):
            print(f"  {k} {v:.1f} kg")
        print("-" * 55)
        print(f"  RADYE TOPLAM {total:.1f} kg ({total/1000:.2f} ton)")