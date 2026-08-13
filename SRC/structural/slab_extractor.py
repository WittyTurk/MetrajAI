# -*- coding: utf-8 -*-
"""
Döşeme extractor — alan × kalınlık → beton + alt kalıp.
"""

from __future__ import annotations

import math
import re
from typing import List, Optional, Tuple

from SRC.structural.models import Slab


class SlabExtractor:
    THICKNESS_RE = re.compile(
        r"(?:h|t|kalınlık|kalinlik|döşeme|doseme)?\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*cm",
        re.I,
    )

    def __init__(
        self,
        doc,
        layer_names=None,
        default_thickness_cm: float = 15.0,
        unit_to_m: float = 0.01,
        floor: str = "GENEL",
    ):
        self.doc = doc
        self.msp = doc.modelspace()
        self.layer_names = layer_names or ["DÖŞEME", "DOSEME", "SLAB", "StatikDöşemeKenarı"]
        self.default_thickness_cm = default_thickness_cm
        self.unit_to_m = unit_to_m
        self.floor = floor

    def extract(self) -> List[Slab]:
        print()
        print("=" * 55)
        print(f"SLAB EXTRACTOR  [kat: {self.floor}]")
        print("=" * 55)

        candidates = []
        for e in self.msp:
            layer = e.dxf.layer
            layer_u = layer.upper().replace("İ", "I").replace("Ş", "S").replace("Ö", "O")
            if not any(
                k in layer_u
                for k in ("DOSEME", "SLAB", "DOSEMEKENARI", "DOSYEME")
            ) and layer not in ("Döşeme", "StatikDöşemeKenarı"):
                if "DOSEME" not in layer_u and "DÖŞEME" not in e.dxf.layer.upper():
                    continue

            if e.dxftype() == "LWPOLYLINE" and getattr(e, "closed", False):
                pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
                area_u = abs(self._area(pts))
                peri_u = self._peri(pts)
                if area_u < 1e-3:
                    continue
                candidates.append({
                    "area_u": area_u,
                    "peri_u": peri_u,
                    "x": sum(p[0] for p in pts) / len(pts),
                    "y": sum(p[1] for p in pts) / len(pts),
                    "thick": self.default_thickness_cm,
                })
            elif e.dxftype() == "INSERT":
                geom = self._from_block(e.dxf.name)
                if geom is None:
                    continue
                area_u, peri_u, thick = geom
                candidates.append({
                    "area_u": area_u,
                    "peri_u": peri_u,
                    "x": e.dxf.insert.x,
                    "y": e.dxf.insert.y,
                    "thick": thick or self.default_thickness_cm,
                })

        print(f"Ham aday           : {len(candidates)}")
        unique = self._dedup(candidates, tol=100.0)
        print(f"Unique döşeme      : {len(unique)}")

        slabs = []
        for i, c in enumerate(unique, start=1):
            area_m2 = c["area_u"] * (self.unit_to_m ** 2)
            peri_m = c["peri_u"] * self.unit_to_m
            if area_m2 < 0.5 or area_m2 > 5000:
                continue
            slabs.append(Slab(
                id=i,
                area_m2=area_m2,
                thickness_cm=c["thick"],
                perimeter_m=peri_m,
                floor=self.floor,
            ))

        for s in slabs:
            print(
                f"  #{s.id}  alan={s.area_m2:.2f} m²  h={s.thickness_cm:.0f} cm  "
                f"beton={s.concrete_m3:.2f} m³  kalıp={s.formwork_m2:.2f} m²"
            )
        return slabs

    def _from_block(self, name: str) -> Optional[Tuple[float, float, Optional[float]]]:
        block = self.doc.blocks.get(name)
        if not block:
            return None
        best_a, best_p, thick = 0.0, 0.0, None
        for e in block:
            if e.dxftype() == "LWPOLYLINE" and getattr(e, "closed", False):
                pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
                a = abs(self._area(pts))
                if a > best_a:
                    best_a = a
                    best_p = self._peri(pts)
            text = None
            if e.dxftype() == "TEXT":
                text = e.dxf.text
            elif e.dxftype() == "MTEXT":
                text = getattr(e, "text", "") or ""
            if text:
                m = self.THICKNESS_RE.search(text)
                if m:
                    thick = float(m.group(1).replace(",", "."))
        if best_a < 1e-6:
            return None
        return best_a, best_p, thick

    @staticmethod
    def _area(pts):
        n = len(pts)
        a = 0.0
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            a += x1 * y2 - x2 * y1
        return a / 2.0

    @staticmethod
    def _peri(pts):
        n = len(pts)
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