# -*- coding: utf-8 -*-
"""Aks grid tabanli kolon/kiris metraj."""

from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional, Tuple, TYPE_CHECKING

from SRC.structural.models import Column, Beam
from SRC.structural.axis_grid import AxisGrid, AxisGridBuilder, AxisGridError

if TYPE_CHECKING:
    from ezdxf.document import Drawing


class AxisBasedStructural:
    SECTION_RE = re.compile(r"(\d+)\s*/\s*(\d+)")
    BEAM_LABEL_RE = re.compile(r"(KZ\d+|K\d+)\s+(\d+)\s*/\s*(\d+)", re.I)

    def __init__(
        self,
        doc: "Drawing",
        height_cm: float = 300.0,
        default_column_section: Tuple[float, float] = (60.0, 40.0),
        default_beam_section: Tuple[float, float] = (40.0, 60.0),
        floor: str = "GENEL",
        unit_to_m_hint: Optional[float] = None,
        beam_mode: str = "line",
        grid_override: Optional[AxisGrid] = None,
    ):
        self.doc = doc
        self.msp = doc.modelspace()
        self.height_cm = height_cm
        self.default_column_section = default_column_section
        self.default_beam_section = default_beam_section
        self.floor = floor
        self.unit_to_m_hint = unit_to_m_hint
        self.beam_mode = beam_mode
        self.grid_override = grid_override

    def build(self):
        print()
        print("=" * 55)
        print("AKS TABANLI STATIK")
        print("=" * 55)

        if getattr(self, "grid_override", None) is not None:
            grid = self.grid_override
            print("Grid: manuel override")
        else:
            grid = AxisGridBuilder(
                self.doc, unit_to_m_hint=self.unit_to_m_hint
            ).build()

        try:
            grid.require_valid()
        except AxisGridError as e:
            print("HATA:", e)
            raise

        col_sec = self._detect_column_section() or self.default_column_section
        beam_sec = self._detect_beam_section() or self.default_beam_section
        print("Kolon kesiti (DXF en sik) : {:.0f}/{:.0f} cm".format(col_sec[0], col_sec[1]))
        print("Kiris kesiti (DXF en sik) : {:.0f}/{:.0f} cm".format(beam_sec[0], beam_sec[1]))
        print("Kiris modu         :", self.beam_mode)

        columns = self._build_columns(grid, col_sec)
        beams = self._build_beams(grid, beam_sec)

        print("")
        print(
            "Kolon adedi :",
            len(columns),
            "(beklenen",
            len(grid.x_labels) * len(grid.y_labels),
            ")",
        )
        print("Kiris adedi :", len(beams))
        for b in beams:
            print(
                "  {:8}  {:.0f}/{:.0f}  L={:.2f} m".format(
                    b.mark, b.section[0], b.section[1], b.length_m
                )
            )

        return columns, beams, grid

    def _build_columns(self, grid, section):
        placed = self._column_sections_by_xy()
        columns = []
        cid = 1
        sec_counts = Counter()
        n_default = 0
        for yi, (yl, yu) in enumerate(zip(grid.y_labels, grid.y_positions_u)):
            for xi, (xl, xu) in enumerate(zip(grid.x_labels, grid.x_positions_u)):
                sec = self._nearest_section(xu, yu, placed, fallback=section)
                if not placed or sec == section:
                    n_default += 1
                sec_counts[sec] += 1
                columns.append(
                    Column(
                        id=cid,
                        mark="C{}{}".format(xl, yl),
                        section=sec,
                        x=xu,
                        y=yu,
                        height_cm=self.height_cm,
                        floor=self.floor,
                    )
                )
                cid += 1
        print("Kolon kesit dagilimi:")
        for sec, n in sec_counts.most_common():
            print("  {:.0f}/{:.0f} -> {} adet".format(sec[0], sec[1], n))
        if not placed:
            print(
                "  ! DXF kolon INSERT kesit yok - hepsi {:.0f}/{:.0f}".format(
                    section[0], section[1]
                )
            )
        elif n_default:
            print(
                "  ! {} kolon en-sik/varsayilan kesit (eslesme zayif)".format(n_default)
            )
        return columns

    def _column_sections_by_xy(self):
        out = []
        for e in self.msp:
            if e.dxftype() != "INSERT":
                continue
            layer = (e.dxf.layer or "").upper()
            if layer not in ("KOLON", "COLUMN") and "KOLON" not in layer:
                continue
            try:
                x = float(e.dxf.insert.x)
                y = float(e.dxf.insert.y)
            except Exception:
                continue
            sec = None
            block = self.doc.blocks.get(e.dxf.name)
            if block:
                for be in block:
                    if be.dxftype() != "TEXT":
                        continue
                    m = self.SECTION_RE.search(be.dxf.text or "")
                    if m:
                        a, b = float(m.group(1)), float(m.group(2))
                        if 20 <= a <= 120 and 20 <= b <= 120:
                            sec = (a, b)
                            break
            if sec is None:
                m = self.SECTION_RE.search(e.dxf.name or "")
                if m:
                    a, b = float(m.group(1)), float(m.group(2))
                    if 20 <= a <= 120 and 20 <= b <= 120:
                        sec = (a, b)
            if sec:
                out.append((x, y, sec))
        return out
    def _nearest_section(self, xu, yu, placed, fallback, tol_m=1.5):
        if not placed:
            return fallback
        best = None
        best_d = 1e18
        for x, y, sec in placed:
            for sx, sy in ((x, y), (x * 0.01, y * 0.01), (x * 0.001, y * 0.001)):
                d = ((sx - xu) ** 2 + (sy - yu) ** 2) ** 0.5
                if d < best_d:
                    best_d = d
                    best = sec
        if best is not None and best_d <= tol_m:
            return best
        return fallback

    def _build_beams(self, grid, section):
        beams = []
        bid = 1
        if self.beam_mode == "span":
            x_sp = list(getattr(grid, "x_spacings_m", []) or [])
            y_sp = list(getattr(grid, "y_spacings_m", []) or [])
            for yi, yl in enumerate(grid.y_labels):
                for xi in range(len(x_sp)):
                    L = x_sp[xi]
                    if hasattr(grid, "span_x_m"):
                        L = grid.span_x_m(xi)
                    beams.append(
                        Beam(
                            id=bid,
                            mark="KX-{}-{}{}".format(
                                yl, grid.x_labels[xi], grid.x_labels[xi + 1]
                            ),
                            section=section,
                            length_m=L,
                            x=(grid.x_positions_u[xi] + grid.x_positions_u[xi + 1]) / 2,
                            y=grid.y_positions_u[yi],
                            floor=self.floor,
                            length_from_geometry=False,
                        )
                    )
                    bid += 1
            for xi, xl in enumerate(grid.x_labels):
                for yi in range(len(y_sp)):
                    L = y_sp[yi]
                    if hasattr(grid, "span_y_m"):
                        L = grid.span_y_m(yi)
                    beams.append(
                        Beam(
                            id=bid,
                            mark="KY-{}-{}{}".format(
                                xl, grid.y_labels[yi], grid.y_labels[yi + 1]
                            ),
                            section=section,
                            length_m=L,
                            x=grid.x_positions_u[xi],
                            y=(grid.y_positions_u[yi] + grid.y_positions_u[yi + 1]) / 2,
                            floor=self.floor,
                            length_from_geometry=False,
                        )
                    )
                    bid += 1
        else:
            for yi, yl in enumerate(grid.y_labels):
                beams.append(
                    Beam(
                        id=bid,
                        mark="KX-{}".format(yl),
                        section=section,
                        length_m=grid.total_x_m,
                        x=(grid.x_positions_u[0] + grid.x_positions_u[-1]) / 2,
                        y=grid.y_positions_u[yi],
                        floor=self.floor,
                        length_from_geometry=False,
                    )
                )
                bid += 1
            for xi, xl in enumerate(grid.x_labels):
                beams.append(
                    Beam(
                        id=bid,
                        mark="KY-{}".format(xl),
                        section=section,
                        length_m=grid.total_y_m,
                        x=grid.x_positions_u[xi],
                        y=(grid.y_positions_u[0] + grid.y_positions_u[-1]) / 2,
                        floor=self.floor,
                        length_from_geometry=False,
                    )
                )
                bid += 1
        return beams

    def _detect_column_section(self):
        counts = Counter()
        for e in self.msp:
            if e.dxftype() != "INSERT":
                continue
            if e.dxf.layer.upper() not in ("KOLON", "COLUMN"):
                continue
            block = self.doc.blocks.get(e.dxf.name)
            if not block:
                continue
            for be in block:
                if be.dxftype() != "TEXT":
                    continue
                m = self.SECTION_RE.search(be.dxf.text or "")
                if m:
                    a, b = float(m.group(1)), float(m.group(2))
                    if 20 <= a <= 120 and 20 <= b <= 120:
                        counts[(a, b)] += 1
        return counts.most_common(1)[0][0] if counts else None

    def _detect_beam_section(self):
        counts = Counter()
        for e in self.msp:
            if e.dxftype() != "INSERT":
                continue
            layer = e.dxf.layer or ""
            lu = layer.upper()
            if "KIRIS" not in lu and "BEAM" not in lu and "Kir" not in layer:
                continue
            block = self.doc.blocks.get(e.dxf.name)
            if not block:
                continue
            for be in block:
                if be.dxftype() != "TEXT":
                    continue
                m = self.BEAM_LABEL_RE.search(be.dxf.text or "")
                if m:
                    a, b = float(m.group(2)), float(m.group(3))
                    if 15 <= a <= 120 and 20 <= b <= 150:
                        counts[(a, b)] += 1
                else:
                    m2 = self.SECTION_RE.search(be.dxf.text or "")
                    if m2:
                        a, b = float(m2.group(1)), float(m2.group(2))
                        if 15 <= a <= 120 and 20 <= b <= 150:
                            counts[(a, b)] += 1
        return counts.most_common(1)[0][0] if counts else None