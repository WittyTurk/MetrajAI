# -*- coding: utf-8 -*-
"""
Aks grid omurgası.

  1) Düşey bantlar (X)
  2) Yatay bantlar (Y)
  3) Yönelim: klasik 1../A.. veya ters A../1..
  4) Birim + dilatasyon + validate
  5) Geçersizse AxisGridError

Manuel: AxisGrid.from_spacings(...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, TYPE_CHECKING

from SRC.structural.axis_x_reader import (
    AxisVerticalScanner,
    AxisDirectionResult,
    is_numeric_family,
    is_letter_family,
)
from SRC.structural.axis_y_reader import AxisHorizontalScanner

if TYPE_CHECKING:
    from ezdxf.document import Drawing


class AxisGridError(Exception):
    pass


@dataclass
class AxisGrid:
    x_labels: List[str] = field(default_factory=list)
    y_labels: List[str] = field(default_factory=list)
    x_positions_u: List[float] = field(default_factory=list)
    y_positions_u: List[float] = field(default_factory=list)
    unit_to_m: float = 0.01
    unit_name: str = "cm"
    source: str = ""
    dilatation_x: List[Tuple[str, str, float]] = field(default_factory=list)
    orientation: str = ""

    @property
    def x_spacings_m(self) -> List[float]:
        xs = self.x_positions_u
        return [abs(xs[i + 1] - xs[i]) * self.unit_to_m for i in range(len(xs) - 1)]

    @property
    def y_spacings_m(self) -> List[float]:
        ys = self.y_positions_u
        return [abs(ys[i + 1] - ys[i]) * self.unit_to_m for i in range(len(ys) - 1)]

    @property
    def total_x_m(self) -> float:
        return sum(self.x_spacings_m)

    @property
    def total_y_m(self) -> float:
        return sum(self.y_spacings_m)

    def span_x_m(self, i: int) -> float:
        sp = self.x_spacings_m
        return sp[i] if 0 <= i < len(sp) else 0.0

    def span_y_m(self, i: int) -> float:
        sp = self.y_spacings_m
        return sp[i] if 0 <= i < len(sp) else 0.0

    def is_valid(self) -> bool:
        if len(self.x_labels) < 2 or len(self.y_labels) < 2:
            return False
        if len(self.x_labels) != len(self.x_positions_u):
            return False
        if len(self.y_labels) != len(self.y_positions_u):
            return False
        if self.total_x_m < 3.0 or self.total_y_m < 3.0:
            return False
        if self.total_x_m > 200 or self.total_y_m > 150:
            return False
        return True

    def require_valid(self) -> None:
        if not self.is_valid():
            raise AxisGridError(
                f"Aks grid geçersiz (kaynak={self.source}, orient={self.orientation}). "
                f"X={self.total_x_m:.2f}m/{len(self.x_labels)}  "
                f"Y={self.total_y_m:.2f}m/{len(self.y_labels)}. "
                "proje.json axis_grid ile kilitleyin."
            )

    def report(self) -> None:
        print()
        print("=" * 55)
        print("AKS GRID")
        print("=" * 55)
        print(f"Kaynak     : {self.source}")
        print(f"Yönelim    : {self.orientation or '-'}")
        print(f"Birim      : {self.unit_name} (unit_to_m={self.unit_to_m})")
        print(f"X etiket   : {self.x_labels}")
        print(f"Y etiket   : {self.y_labels}")
        print("X aralıkları (m):")
        for i, s in enumerate(self.x_spacings_m):
            a = self.x_labels[i] if i < len(self.x_labels) else "?"
            b = self.x_labels[i + 1] if i + 1 < len(self.x_labels) else "?"
            flag = "  [DILATASYON]" if 0 < s < 0.6 else ""
            print(f"  {a} → {b} : {s:.2f} m{flag}")
        print("Y aralıkları (m):")
        for i, s in enumerate(self.y_spacings_m):
            a = self.y_labels[i] if i < len(self.y_labels) else "?"
            b = self.y_labels[i + 1] if i + 1 < len(self.y_labels) else "?"
            print(f"  {a} → {b} : {s:.2f} m")
        print(f"Toplam X : {self.total_x_m:.2f} m")
        print(f"Toplam Y : {self.total_y_m:.2f} m")
        print(f"Geçerli  : {'EVET' if self.is_valid() else 'HAYIR'}")
        if self.dilatation_x:
            print("Dilatasyon X:")
            for a, b, g in self.dilatation_x:
                print(f"  {a} → {b} : {g:.2f} m")

    @classmethod
    def from_spacings(
        cls,
        x_labels: list,
        y_labels: list,
        x_spacings_m: list,
        y_spacings_m: list,
        source: str = "manuel (proje.json)",
        dilatation_spans: Optional[list] = None,
    ) -> "AxisGrid":
        if len(x_labels) != len(x_spacings_m) + 1:
            raise AxisGridError(
                f"X: {len(x_labels)} etiket, {len(x_spacings_m)} aralık"
            )
        if len(y_labels) != len(y_spacings_m) + 1:
            raise AxisGridError(
                f"Y: {len(y_labels)} etiket, {len(y_spacings_m)} aralık"
            )
        xp = [0.0]
        for s in x_spacings_m:
            xp.append(xp[-1] + float(s))
        yp = [0.0]
        for s in y_spacings_m:
            yp.append(yp[-1] + float(s))
        dil: List[Tuple[str, str, float]] = []
        for d in dilatation_spans or []:
            dil.append((str(d["from"]), str(d["to"]), float(d.get("gap_m", 0))))
        for i, s in enumerate(x_spacings_m):
            if 0 < float(s) < 0.6:
                dil.append((str(x_labels[i]), str(x_labels[i + 1]), float(s)))
        g = cls(
            x_labels=[str(x) for x in x_labels],
            y_labels=[str(y) for y in y_labels],
            x_positions_u=xp,
            y_positions_u=yp,
            unit_to_m=1.0,
            unit_name="m",
            source=source,
            dilatation_x=dil,
            orientation="manuel",
        )
        g.require_valid()
        g.report()
        return g


class AxisGridBuilder:
    def __init__(self, doc: "Drawing", unit_to_m_hint: Optional[float] = None):
        self.doc = doc
        self.unit_to_m_hint = unit_to_m_hint

    def build(self, require_valid: bool = True) -> AxisGrid:
        print()
        print("=" * 55)
        print("AKS OMURGA (düşey → yatay → yönelim)")
        print("=" * 55)

        vert = AxisVerticalScanner(self.doc).scan()
        horiz = AxisHorizontalScanner(self.doc).scan()
        x_labels, x_pos, y_labels, y_pos, orient = self._assign_orientation(vert, horiz)

        grid = AxisGrid(
            x_labels=x_labels,
            y_labels=y_labels,
            x_positions_u=x_pos,
            y_positions_u=y_pos,
            source=f"DXF vert={vert.source} horiz={horiz.source}",
            orientation=orient,
        )
        self._resolve_unit(grid)
        self._mark_dilatation(grid)
        grid.report()
        if require_valid:
            grid.require_valid()
        return grid

    def _assign_orientation(self, vert: AxisDirectionResult, horiz: AxisDirectionResult):
        v_labs = vert.labels
        h_labs = horiz.labels
        v_num = sum(1 for L in v_labs if is_numeric_family(L))
        v_let = sum(1 for L in v_labs if is_letter_family(L))
        h_num = sum(1 for L in h_labs if is_numeric_family(L))
        h_let = sum(1 for L in h_labs if is_letter_family(L))

        def filter_bands(res: AxisDirectionResult, numeric: bool):
            bands = [
                b for b in res.bands
                if (is_numeric_family(b.label) if numeric else is_letter_family(b.label))
            ]
            if len(bands) < 2:
                bands = list(res.bands)
            bands = sorted(bands, key=lambda b: b.position_u)
            return [b.label for b in bands], [b.position_u for b in bands]

        if v_num >= v_let and h_let >= h_num:
            orient = "num_x_letter_y"
            x_labels, x_pos = filter_bands(vert, numeric=True)
            y_labels, y_pos = filter_bands(horiz, numeric=False)
        elif v_let > v_num and h_num >= h_let:
            orient = "letter_x_num_y"
            x_labels, x_pos = filter_bands(vert, numeric=False)
            y_labels, y_pos = filter_bands(horiz, numeric=True)
        else:
            orient = "mixed_or_unknown"
            x_labels, x_pos = vert.labels, vert.positions_u
            y_labels, y_pos = horiz.labels, horiz.positions_u

        print(
            f"Yönelim: {orient}  "
            f"(vert num/let={v_num}/{v_let}, horiz num/let={h_num}/{h_let})"
        )
        return x_labels, x_pos, y_labels, y_pos, orient

    def _resolve_unit(self, grid: AxisGrid) -> None:
        gaps = []
        xs, ys = grid.x_positions_u, grid.y_positions_u
        for i in range(len(xs) - 1):
            gaps.append(abs(xs[i + 1] - xs[i]))
        for i in range(len(ys) - 1):
            gaps.append(abs(ys[i + 1] - ys[i]))
        if not gaps:
            grid.unit_to_m = self.unit_to_m_hint or 0.01
            grid.unit_name = "cm"
            return
        avg = sum(gaps) / len(gaps)
        candidates = [("mm", 0.001), ("cm", 0.01), ("m", 1.0)]

        def score(u: float) -> float:
            span = avg * u
            sc = abs(span - 7.0)
            if 2.5 <= span <= 12.0:
                sc -= 10.0
            tot_x = (max(xs) - min(xs)) * u if len(xs) >= 2 else 0.0
            tot_y = (max(ys) - min(ys)) * u if len(ys) >= 2 else 0.0
            if 12 <= tot_x <= 120:
                sc -= 5.0
            if 8 <= tot_y <= 80:
                sc -= 5.0
            if tot_y < 4.0 and len(ys) >= 3:
                sc += 25.0
            if tot_x > 200:
                sc += 20.0
            if self.unit_to_m_hint and abs(u - self.unit_to_m_hint) < 1e-12:
                sc -= 2.0
            return sc

        best = min(candidates, key=lambda c: score(c[1]))
        grid.unit_name, grid.unit_to_m = best

    def _mark_dilatation(self, grid: AxisGrid) -> None:
        dil = []
        for i, s in enumerate(grid.x_spacings_m):
            if 0 < s < 0.6 and i + 1 < len(grid.x_labels):
                dil.append((grid.x_labels[i], grid.x_labels[i + 1], s))
        grid.dilatation_x = dil