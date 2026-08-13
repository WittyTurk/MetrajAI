# -*- coding: utf-8 -*-
"""Perde extractor — DXF birebir, çok katlı."""

from __future__ import annotations

import math
import re
from typing import List

from SRC.structural.models import ShearWall


class ShearWallExtractor:
    def __init__(
        self,
        doc,
        default_thickness_cm: float = 25.0,
        default_height_cm: float = 300.0,
        unit_to_m: float = 0.01,
        floor: str = "GENEL",
    ):
        self.doc = doc
        self.msp = doc.modelspace()
        self.default_thickness_cm = default_thickness_cm
        self.default_height_cm = default_height_cm
        self.unit_to_m = unit_to_m
        self.floor = floor

    def extract(self) -> List[ShearWall]:
        print()
        print("=" * 55)
        print(f"SHEAR WALL EXTRACTOR  [kat: {self.floor}]")
        print("=" * 55)

        raw = []
        for e in self.msp:
            layer = e.dxf.layer.upper().replace("İ", "I").replace("Ş", "S")
            if "PERDE" not in layer and "SHEAR" not in layer and e.dxf.layer != "Perde":
                continue

            if e.dxftype() == "INSERT":
                length_u, thick = self._from_block(e.dxf.name)
                if length_u is None or length_u < 1e-3:
                    continue
                length_m = length_u * self.unit_to_m
                if length_m < 0.3 or length_m > 50:
                    continue
                raw.append({
                    "x": e.dxf.insert.x,
                    "y": e.dxf.insert.y,
                    "length_m": length_m,
                    "thickness_cm": thick or self.default_thickness_cm,
                })
            elif e.dxftype() == "LWPOLYLINE":
                pts = list(e.get_points())
                length_u = 0.0
                for i in range(len(pts) - 1):
                    length_u += math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1])
                length_m = length_u * self.unit_to_m
                if length_m < 0.3:
                    continue
                raw.append({
                    "x": sum(p[0] for p in pts) / len(pts),
                    "y": sum(p[1] for p in pts) / len(pts),
                    "length_m": length_m,
                    "thickness_cm": self.default_thickness_cm,
                })

        print(f"Ham aday           : {len(raw)}")
        unique = self._dedup(raw, tol=50.0)
        print(f"Unique perde       : {len(unique)}")

        walls = []
        for i, item in enumerate(unique, start=1):
            walls.append(ShearWall(
                id=i,
                thickness_cm=item["thickness_cm"],
                length_m=item["length_m"],
                height_cm=self.default_height_cm,
                x=item["x"],
                y=item["y"],
                floor=self.floor,
            ))

        total_len = sum(w.length_m for w in walls)
        print(f"Toplam uzunluk     : {total_len:.2f} m")
        return walls

    def _from_block(self, name: str):
        block = self.doc.blocks.get(name)
        if not block:
            return None, None
        max_len = 0.0
        thick = None
        for e in block:
            if e.dxftype() == "LINE":
                max_len = max(max_len, math.hypot(
                    e.dxf.end.x - e.dxf.start.x,
                    e.dxf.end.y - e.dxf.start.y,
                ))
            elif e.dxftype() == "LWPOLYLINE":
                pts = list(e.get_points())
                for i in range(len(pts) - 1):
                    max_len = max(max_len, math.hypot(
                        pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]
                    ))
            text = None
            if e.dxftype() == "TEXT":
                text = e.dxf.text
            elif e.dxftype() == "MTEXT":
                text = getattr(e, "text", "") or ""
            if text:
                m = re.search(r"(\d+)\s*cm", text, re.I)
                if m:
                    v = float(m.group(1))
                    if 15 <= v <= 80:
                        thick = v
        return (max_len if max_len > 0 else None), thick

    def _dedup(self, items, tol=50.0):
        groups = []
        for it in items:
            placed = False
            for g in groups:
                if abs(it["x"]-g["x"]) <= tol and abs(it["y"]-g["y"]) <= tol:
                    if it["length_m"] > g["length_m"]:
                        g.update(it)
                    placed = True
                    break
            if not placed:
                groups.append(dict(it))
        return groups