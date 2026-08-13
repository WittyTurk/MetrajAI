 # -*- coding: utf-8 -*-
"""
Kolon + perde aks düzeni — yalnızca DXF.
Radye / bodrum aplikasyon planı esas alınır. Uydurma yok.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, TYPE_CHECKING

from SRC.structural.axis_grid import AxisGrid, AxisGridBuilder

if TYPE_CHECKING:
    from ezdxf.document import Drawing


@dataclass
class ColumnPlacement:
    id: int
    x: float
    y: float
    section: Tuple[float, float]
    mark: str = ""
    axis_x: str = ""
    axis_y: str = ""
    source: str = ""


@dataclass
class WallPlacement:
    id: int
    x1: float
    y1: float
    x2: float
    y2: float
    thickness_cm: float = 0.0
    mark: str = ""
    source: str = ""

    @property
    def length_u(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)

    def length_m(self, unit_to_m: float) -> float:
        return self.length_u * unit_to_m


@dataclass
class AxisLayout:
    grid: AxisGrid
    columns: List[ColumnPlacement] = field(default_factory=list)
    walls: List[WallPlacement] = field(default_factory=list)
    unit_to_m: float = 0.01
    source_dxf: str = ""
    warnings: List[str] = field(default_factory=list)

    def report(self) -> None:
        print()
        print("=" * 55)
        print("AKS DÜZENİ (DXF birebir)")
        print("=" * 55)
        print(f"Kaynak DXF : {self.source_dxf}")
        print(f"Birim      : unit_to_m={self.unit_to_m}")
        print(f"X aks      : {self.grid.x_labels}  → {[f'{s:.2f}' for s in self.grid.x_spacings_m]} m")
        print(f"Y aks      : {self.grid.y_labels}  → {[f'{s:.2f}' for s in self.grid.y_spacings_m]} m")
        print(f"Kolon      : {len(self.columns)}")
        for c in self.columns[:15]:
            print(
                f"  C{c.id:02d}  ({c.x:.1f},{c.y:.1f})  "
                f"{c.section[0]:.0f}/{c.section[1]:.0f}  "
                f"[{c.axis_x}-{c.axis_y}]  {c.mark}  {c.source}"
            )
        if len(self.columns) > 15:
            print(f"  ... +{len(self.columns) - 15}")
        print(f"Perde      : {len(self.walls)}")
        for w in self.walls[:10]:
            print(
                f"  W{w.id:02d}  L={w.length_m(self.unit_to_m):.2f} m  "
                f"T={w.thickness_cm:.0f} cm  {w.mark}  {w.source}"
            )
        for w in self.warnings:
            print(f"  ! {w}")


class AxisLayoutFromDxf:
    SECTION_RE = re.compile(r"(\d+)\s*/\s*(\d+)")
    COL_LAYER = ("KOLON", "COLUMN", "KOLONLAR", "KOLONTARAMA")
    WALL_LAYER = ("PERDE", "SHEAR", "PERDELER", "DUVAR_PERDE")

    def __init__(
        self,
        doc: "Drawing",
        unit_to_m: Optional[float] = None,
        source_path: str = "",
        snap_to_grid: bool = True,
        snap_tol_u: float = 80.0,
    ):
        self.doc = doc
        self.msp = doc.modelspace()
        self.source_path = source_path
        self.snap_to_grid = snap_to_grid
        self.snap_tol_u = snap_tol_u
        self.unit_to_m_hint = unit_to_m

    def build(self) -> AxisLayout:
        print()
        print("=" * 55)
        print("AKS LAYOUT BUILDER (DXF)")
        print("=" * 55)

        grid = AxisGridBuilder(self.doc, unit_to_m_hint=self.unit_to_m_hint).build()
        unit_to_m = grid.unit_to_m if grid.unit_to_m else (self.unit_to_m_hint or 0.01)

        warnings: List[str] = []
        if len(grid.x_labels) < 2 or len(grid.y_labels) < 2:
            warnings.append("Aks etiketleri yetersiz — TEXT 1,2,3 / A,B,C kontrol edin")

        columns = self._extract_columns(grid, unit_to_m)
        walls = self._extract_walls(unit_to_m)

        if not columns:
            warnings.append(
                "Kolon INSERT/poligon bulunamadı — kesişim uydurulmadı. "
                "Aplikasyon paftasında kolon bloğu gerekli."
            )
        if not walls:
            warnings.append("Perde çizgisi bulunamadı (yoksa normal)")

        layout = AxisLayout(
            grid=grid,
            columns=columns,
            walls=walls,
            unit_to_m=unit_to_m,
            source_dxf=self.source_path or "",
            warnings=warnings,
        )
        layout.report()
        return layout

    def _extract_columns(self, grid: AxisGrid, unit_to_m: float) -> List[ColumnPlacement]:
        raw = []
        for e in self.msp:
            if e.dxftype() != "INSERT":
                continue
            layer = self._norm(e.dxf.layer)
            block = self._norm(e.dxf.name)
            if not any(k in layer for k in self.COL_LAYER) and not any(
                k in block for k in self.COL_LAYER
            ):
                continue
            sec = self._section_from_block(e.dxf.name)
            raw.append({
                "x": e.dxf.insert.x,
                "y": e.dxf.insert.y,
                "section": sec or (0.0, 0.0),
                "mark": e.dxf.name,
                "source": "insert",
            })

        for e in self.msp:
            if e.dxftype() != "LWPOLYLINE" or not e.closed:
                continue
            layer = self._norm(e.dxf.layer)
            if not any(k in layer for k in self.COL_LAYER):
                continue
            pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
            if len(pts) < 4:
                continue
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            sec = self._section_from_polygon(pts, unit_to_m)
            raw.append({
                "x": cx, "y": cy, "section": sec,
                "mark": e.dxf.layer, "source": "polyline",
            })

        cols: List[ColumnPlacement] = []
        tol = self.snap_tol_u
        for r in raw:
            placed = False
            for c in cols:
                if abs(c.x - r["x"]) <= tol and abs(c.y - r["y"]) <= tol:
                    if r["section"][0] > c.section[0]:
                        c.section = r["section"]
                    placed = True
                    break
            if not placed:
                cols.append(ColumnPlacement(
                    id=0, x=r["x"], y=r["y"], section=r["section"],
                    mark=r["mark"], source=r["source"],
                ))

        for i, c in enumerate(cols, start=1):
            c.id = i
            c.axis_x, c.axis_y = self._nearest_axes(c.x, c.y, grid)
        return cols

    def _section_from_block(self, block_name: str) -> Optional[Tuple[float, float]]:
        block = self.doc.blocks.get(block_name)
        if not block:
            return None
        for e in block:
            if e.dxftype() != "TEXT":
                continue
            m = self.SECTION_RE.search(e.dxf.text or "")
            if m:
                a, b = float(m.group(1)), float(m.group(2))
                if 15 <= a <= 150 and 15 <= b <= 150:
                    return (a, b)
        return None

    def _section_from_polygon(self, pts, unit_to_m: float) -> Tuple[float, float]:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w = (max(xs) - min(xs)) * unit_to_m * 100
        h = (max(ys) - min(ys)) * unit_to_m * 100
        return (round(w, 1), round(h, 1))

    def _nearest_axes(self, x: float, y: float, grid: AxisGrid) -> Tuple[str, str]:
        ax, ay = "", ""
        if grid.x_positions_u:
            i = min(range(len(grid.x_positions_u)),
                    key=lambda k: abs(grid.x_positions_u[k] - x))
            if abs(grid.x_positions_u[i] - x) <= self.snap_tol_u * 3:
                ax = grid.x_labels[i] if i < len(grid.x_labels) else str(i + 1)
        if grid.y_positions_u:
            j = min(range(len(grid.y_positions_u)),
                    key=lambda k: abs(grid.y_positions_u[k] - y))
            if abs(grid.y_positions_u[j] - y) <= self.snap_tol_u * 3:
                ay = grid.y_labels[j] if j < len(grid.y_labels) else chr(65 + j)
        return ax, ay

    def _extract_walls(self, unit_to_m: float) -> List[WallPlacement]:
        walls: List[WallPlacement] = []
        wid = 1
        for e in self.msp:
            layer = self._norm(e.dxf.layer)
            if not any(k in layer for k in self.WALL_LAYER):
                continue
            if e.dxftype() == "LINE":
                x1, y1 = e.dxf.start.x, e.dxf.start.y
                x2, y2 = e.dxf.end.x, e.dxf.end.y
                if math.hypot(x2 - x1, y2 - y1) < 10:
                    continue
                walls.append(WallPlacement(
                    id=wid, x1=x1, y1=y1, x2=x2, y2=y2,
                    mark=e.dxf.layer, source="line",
                ))
                wid += 1
            elif e.dxftype() == "LWPOLYLINE":
                pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
                if e.closed and len(pts) >= 4:
                    edges = []
                    for i in range(len(pts)):
                        x1, y1 = pts[i]
                        x2, y2 = pts[(i + 1) % len(pts)]
                        edges.append((math.hypot(x2 - x1, y2 - y1), x1, y1, x2, y2))
                    edges.sort(key=lambda t: t[0])
                    thick_u = edges[0][0]
                    long = edges[-1]
                    walls.append(WallPlacement(
                        id=wid, x1=long[1], y1=long[2], x2=long[3], y2=long[4],
                        thickness_cm=thick_u * unit_to_m * 100,
                        mark=e.dxf.layer, source="polyline",
                    ))
                    wid += 1
                else:
                    for i in range(len(pts) - 1):
                        x1, y1 = pts[i]
                        x2, y2 = pts[i + 1]
                        if math.hypot(x2 - x1, y2 - y1) < 10:
                            continue
                        walls.append(WallPlacement(
                            id=wid, x1=x1, y1=y1, x2=x2, y2=y2,
                            mark=e.dxf.layer, source="polyline_seg",
                        ))
                        wid += 1
        return walls

    @staticmethod
    def _norm(s: str) -> str:
        return (
            (s or "").upper()
            .replace("İ", "I").replace("Ş", "S").replace("Ğ", "G")
            .replace("Ü", "U").replace("Ö", "O").replace("Ç", "C")
        )