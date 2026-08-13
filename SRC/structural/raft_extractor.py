# -*- coding: utf-8 -*-
"""
Büyük projeler için radye (raft foundation) extractor.
"""

from __future__ import annotations

import math
import re
from typing import List, Optional, Tuple

from SRC.structural.models import Raft


class RaftExtractor:
    THICKNESS_RE = re.compile(
        r"(?:h|t|kalınlık|kalinlik)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(?:cm)?",
        re.I,
    )
    THICKNESS_RE2 = re.compile(r"(\d+(?:[.,]\d+)?)\s*cm", re.I)

    def __init__(
        self,
        doc,
        layer_names=None,
        default_thickness_cm: float = 40.0,
        unit_to_m: float = 0.01,
    ):
        self.doc = doc
        self.msp = doc.modelspace()
        self.layer_names = [
            n.upper()
            for n in (
                layer_names
                or [
                    "RADYEDÖŞEMEKENARI",
                    "RADYEDOSEMEKENARI",
                    "RADYE",
                    "RAFT",
                    "TEMEL",
                ]
            )
        ]
        self.default_thickness_cm = default_thickness_cm
        self.unit_to_m = unit_to_m

    def extract(self) -> List[Raft]:
        print()
        print("=" * 55)
        print("RAFT EXTRACTOR (büyük proje)")
        print("=" * 55)

        candidates = []

        for e in self.msp:
            layer = e.dxf.layer.upper().replace("İ", "I").replace("Ş", "S").replace("Ö", "O")
            if not any(k in layer for k in ("RADYE", "RAFT", "TEMEL")) and layer not in self.layer_names:
                continue

            if e.dxftype() == "INSERT":
                geom = self._geometry_from_block(e.dxf.name)
                if geom is None:
                    continue
                area_u, peri_u, thick = geom
                candidates.append({
                    "x": e.dxf.insert.x,
                    "y": e.dxf.insert.y,
                    "area_u": area_u,
                    "peri_u": peri_u,
                    "thickness_cm": thick or self.default_thickness_cm,
                })

            elif e.dxftype() == "LWPOLYLINE" and e.closed:
                pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
                area_u = abs(self._polygon_area(pts))
                peri_u = self._polygon_perimeter(pts)
                if area_u < 1e-6:
                    continue
                candidates.append({
                    "x": sum(p[0] for p in pts) / len(pts),
                    "y": sum(p[1] for p in pts) / len(pts),
                    "area_u": area_u,
                    "peri_u": peri_u,
                    "thickness_cm": self.default_thickness_cm,
                })

        print(f"Ham aday           : {len(candidates)}")
        unique = self._dedup(candidates, tol=100.0)
        print(f"Unique radye       : {len(unique)}")

        rafts: List[Raft] = []
        for i, c in enumerate(unique, start=1):
            area_m2 = c["area_u"] * (self.unit_to_m ** 2)
            peri_m = c["peri_u"] * self.unit_to_m
            rafts.append(
                Raft(
                    id=i,
                    area_m2=area_m2,
                    thickness_cm=c["thickness_cm"],
                    perimeter_m=peri_m,
                )
            )

        self._print_summary(rafts)
        return rafts

    def _geometry_from_block(self, block_name: str) -> Optional[Tuple[float, float, Optional[float]]]:
        block = self.doc.blocks.get(block_name)
        if block is None:
            return None

        best_area = 0.0
        best_peri = 0.0
        thickness = None

        for e in block:
            if e.dxftype() == "LWPOLYLINE" and getattr(e, "closed", False):
                pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
                if len(pts) < 3:
                    continue
                area = abs(self._polygon_area(pts))
                peri = self._polygon_perimeter(pts)
                if area > best_area:
                    best_area = area
                    best_peri = peri

            text = None
            if e.dxftype() == "TEXT":
                text = e.dxf.text
            elif e.dxftype() == "MTEXT":
                text = getattr(e, "text", None) or ""
                text = re.sub(r"\\[A-Za-z][^;]*;", "", text)
                text = re.sub(r"[{}]", "", text)

            if text:
                t = self._parse_thickness(text)
                if t is not None:
                    thickness = t

        if best_area < 1e-6:
            return None
        return best_area, best_peri, thickness

    def _parse_thickness(self, text: str) -> Optional[float]:
        m = self.THICKNESS_RE.search(text)
        if m:
            return float(m.group(1).replace(",", "."))
        m = self.THICKNESS_RE2.search(text)
        if m:
            val = float(m.group(1).replace(",", "."))
            if 15 <= val <= 150:
                return val
        return None

    @staticmethod
    def _polygon_area(pts: List[Tuple[float, float]]) -> float:
        n = len(pts)
        if n < 3:
            return 0.0
        a = 0.0
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            a += x1 * y2 - x2 * y1
        return a / 2.0

    @staticmethod
    def _polygon_perimeter(pts: List[Tuple[float, float]]) -> float:
        n = len(pts)
        if n < 2:
            return 0.0
        p = 0.0
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            p += math.hypot(x2 - x1, y2 - y1)
        return p

    def _dedup(self, items, tol=100.0):
        groups = []
        for it in items:
            placed = False
            for g in groups:
                if abs(it["x"] - g["x"]) <= tol and abs(it["y"] - g["y"]) <= tol:
                    if it["area_u"] > g["area_u"]:
                        g.update(it)
                    placed = True
                    break
            if not placed:
                groups.append(dict(it))
        return groups

    def _print_summary(self, rafts: List[Raft]):
        print(f"\nRadye sayısı        : {len(rafts)}")
        for r in rafts:
            print(
                f"  #{r.id}  alan={r.area_m2:.2f} m²  "
                f"h={r.thickness_cm:.0f} cm  "
                f"çevre={r.perimeter_m:.2f} m  "
                f"beton={r.concrete_m3:.2f} m³  "
                f"kalıp={r.formwork_m2:.2f} m²"
            )