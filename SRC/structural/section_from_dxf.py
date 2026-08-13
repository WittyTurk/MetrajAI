# -*- coding: utf-8 -*-
"""
Kolon kesit + perde kalinlik — yalnizca DXF aplikasyon.
Uydurma yok: bulunamazsa None / 0 + uyari.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ezdxf.document import Drawing

SECTION_RE = re.compile(r"(\d{2,3})\s*[xX×/\-]\s*(\d{2,3})")
THICK_RE = re.compile(
    r"(?:t|kalinlik|kalınlık|thk)?\s*[:=]?\s*(\d{2,3})\s*cm", re.I
)
THICK_RE2 = re.compile(r"(\d{2,3})\s*cm", re.I)


def _layer_u(e) -> str:
    return (e.dxf.layer or "").upper().replace("İ", "I").replace("Ş", "S")


def _insert_xy(e) -> Optional[Tuple[float, float]]:
    try:
        return float(e.dxf.insert.x), float(e.dxf.insert.y)
    except Exception:
        return None


def _texts_in_block(doc, block_name: str) -> List[str]:
    out = []
    block = doc.blocks.get(block_name)
    if not block:
        return out
    for be in block:
        if be.dxftype() in ("TEXT", "MTEXT"):
            t = getattr(be.dxf, "text", None) or ""
            if hasattr(be, "plain_text"):
                try:
                    t = be.plain_text()
                except Exception:
                    pass
            if t:
                out.append(str(t))
    return out


def parse_section_cm(text: str) -> Optional[Tuple[float, float]]:
    if not text:
        return None
    m = SECTION_RE.search(text)
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    if 15 <= a <= 150 and 15 <= b <= 150:
        return (a, b)
    return None


def parse_thickness_cm(text: str) -> Optional[float]:
    if not text:
        return None
    m = THICK_RE.search(text)
    if m:
        v = float(m.group(1))
        if 10 <= v <= 80:
            return v
    m = THICK_RE2.search(text)
    if m:
        v = float(m.group(1))
        if 15 <= v <= 60:
            return v
    return None


class ColumnSectionHit:
    def __init__(self, x, y, section, source=""):
        self.x = x
        self.y = y
        self.section = section
        self.source = source


class ShearSectionHit:
    def __init__(self, x, y, thickness_cm, length_m=0.0, source=""):
        self.x = x
        self.y = y
        self.thickness_cm = thickness_cm
        self.length_m = length_m
        self.source = source


class SectionFromDxf:
    def __init__(self, doc: "Drawing", unit_to_m: float = 0.001, floor: str = "GENEL"):
        self.doc = doc
        self.msp = doc.modelspace()
        self.unit_to_m = unit_to_m
        self.floor = floor
        self.column_hits: List[ColumnSectionHit] = []
        self.shear_hits: List[ShearSectionHit] = []

    def extract(self) -> "SectionFromDxf":
        self.column_hits = self._scan_columns()
        self.shear_hits = self._scan_shears()
        self._print()
        return self

    def _scan_columns(self) -> List[ColumnSectionHit]:
        hits = []
        for e in self.msp:
            if e.dxftype() != "INSERT":
                continue
            lu = _layer_u(e)
            xy = _insert_xy(e)
            if not xy:
                continue
            sec = None
            src = e.dxf.name or ""
            for t in _texts_in_block(self.doc, e.dxf.name):
                sec = parse_section_cm(t)
                if sec:
                    src = t
                    break
            if sec is None:
                sec = parse_section_cm(e.dxf.name or "")
            if sec is None:
                continue
            if "KOLON" not in lu and "COLUMN" not in lu:
                if not parse_section_cm(e.dxf.name or ""):
                    continue
            hits.append(ColumnSectionHit(xy[0], xy[1], sec, source=src))
        return hits

    def _scan_shears(self) -> List[ShearSectionHit]:
        hits = []
        for e in self.msp:
            lu = _layer_u(e)
            if "PERDE" not in lu and "SHEAR" not in lu and "WALL" not in lu:
                continue
            if e.dxftype() != "INSERT":
                continue
            xy = _insert_xy(e) or (0.0, 0.0)
            thick = None
            for t in _texts_in_block(self.doc, e.dxf.name):
                thick = parse_thickness_cm(t)
                if thick:
                    break
            if thick is None:
                thick = parse_thickness_cm(e.dxf.name or "")
            length_m = 0.0
            block = self.doc.blocks.get(e.dxf.name)
            if block:
                xs, ys = [], []
                for be in block:
                    if be.dxftype() == "LINE":
                        try:
                            xs += [be.dxf.start.x, be.dxf.end.x]
                            ys += [be.dxf.start.y, be.dxf.end.y]
                        except Exception:
                            pass
                if xs and ys:
                    length_m = max(max(xs) - min(xs), max(ys) - min(ys)) * self.unit_to_m
            if thick and thick > 0:
                hits.append(
                    ShearSectionHit(xy[0], xy[1], thick, length_m, source=e.dxf.name)
                )
        return hits

    def _print(self):
        print()
        print("=" * 55)
        print("SECTION FROM DXF [kat: {}]".format(self.floor))
        print("=" * 55)
        cc = Counter(h.section for h in self.column_hits)
        print("Kolon kesit hit: {}".format(len(self.column_hits)))
        for sec, n in cc.most_common(12):
            print("  {:.0f}/{:.0f} -> {} adet".format(sec[0], sec[1], n))
        if not self.column_hits:
            print("  ! Kolon kesit okunamadi (aplikasyon TEXT/INSERT)")
        sc = Counter(h.thickness_cm for h in self.shear_hits)
        print("Perde kalinlik hit: {}".format(len(self.shear_hits)))
        for th, n in sc.most_common(8):
            print("  t={:.0f} cm -> {} adet".format(th, n))
        if not self.shear_hits:
            print("  ! Perde kalinlik okunamadi")

    def section_at(self, x_u: float, y_u: float, tol_m: float = 1.5):
        if not self.column_hits:
            return None
        best = None
        best_d = 1e18
        for h in self.column_hits:
            for sx, sy in (
                (h.x, h.y),
                (h.x * 0.01, h.y * 0.01),
                (h.x * 0.001, h.y * 0.001),
            ):
                d = ((sx - x_u) ** 2 + (sy - y_u) ** 2) ** 0.5
                if d < best_d:
                    best_d = d
                    best = h.section
        if best is not None and best_d <= tol_m:
            return best
        return None

    def most_common_column_section(self):
        if not self.column_hits:
            return None
        return Counter(h.section for h in self.column_hits).most_common(1)[0][0]

    def most_common_shear_thickness(self):
        if not self.shear_hits:
            return None
        return Counter(h.thickness_cm for h in self.shear_hits).most_common(1)[0][0]