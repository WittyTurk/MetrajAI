# -*- coding: utf-8 -*-
"""Y yönü aks taraması (yatay çizgiler → Y konumu)."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, TYPE_CHECKING

from SRC.structural.axis_x_reader import (
    AxisBand,
    AxisDirectionResult,
    normalize_label,
)

if TYPE_CHECKING:
    from ezdxf.document import Drawing


class AxisHorizontalScanner:
    LAYER = re.compile(r"AKS|EKSEN|AXIS|AXES", re.I)

    def __init__(self, doc: "Drawing"):
        self.doc = doc
        self.msp = doc.modelspace()

    def scan(self) -> AxisDirectionResult:
        print("--- Y (yatay bant) ---")
        by_label: Dict[str, List[float]] = defaultdict(list)
        for e in self.msp:
            if e.dxftype() != "TEXT":
                continue
            if not self.LAYER.search(e.dxf.layer or ""):
                continue
            lab = normalize_label(e.dxf.text or "")
            if not lab:
                continue
            by_label[lab].append(float(e.dxf.insert.y))

        if len(by_label) >= 2:
            bands = self._bands_from_map(by_label)
            print(f"  TEXT: {len(bands)} etiket  {[b.label for b in bands]}")
            return AxisDirectionResult(bands, "TEXT")

        ys = self._horizontal_line_ys()
        if len(ys) >= 2:
            bands = [AxisBand(chr(65 + i), y) for i, y in enumerate(ys)]
            print(f"  LINE: {len(bands)} yatay küme")
            return AxisDirectionResult(bands, "LINE")

        print("  Y: yetersiz")
        return AxisDirectionResult([], "yok")

    def _horizontal_line_ys(self) -> List[float]:
        ys: List[float] = []
        for e in self.msp:
            if e.dxftype() != "LINE":
                continue
            if not self.LAYER.search(e.dxf.layer or ""):
                continue
            dx = abs(e.dxf.end.x - e.dxf.start.x)
            dy = abs(e.dxf.end.y - e.dxf.start.y)
            if dx > 1e-9 and dy < dx * 0.15:
                ys.append((e.dxf.start.y + e.dxf.end.y) / 2.0)
        return self._cluster(ys)

    def _bands_from_map(self, amap: Dict[str, List[float]]) -> List[AxisBand]:
        bands = []
        for lab, vals in amap.items():
            vals = self._trim(vals)
            bands.append(AxisBand(lab, self._median(vals), len(vals)))
        bands.sort(key=lambda b: b.position_u)
        return bands

    @staticmethod
    def _median(vals: List[float]) -> float:
        vals = sorted(vals)
        n = len(vals)
        if n == 0:
            return 0.0
        if n % 2:
            return vals[n // 2]
        return 0.5 * (vals[n // 2 - 1] + vals[n // 2])

    def _trim(self, vals: List[float]) -> List[float]:
        if len(vals) <= 2:
            return vals
        med = self._median(vals)
        span = max(vals) - min(vals)
        tol = max(abs(med) * 0.05, 500.0)
        if span <= tol * 10:
            return vals
        return self._densest(vals)

    def _densest(self, vals: List[float], tol: float = 200.0) -> List[float]:
        vals = sorted(vals)
        best: List[float] = []
        cur = [vals[0]]
        for v in vals[1:]:
            if abs(v - cur[-1]) <= tol:
                cur.append(v)
            else:
                if len(cur) > len(best):
                    best = cur
                cur = [v]
        if len(cur) > len(best):
            best = cur
        return best or vals

    def _cluster(self, vals: List[float]) -> List[float]:
        if not vals:
            return []
        vals = sorted(vals)
        gaps = [vals[i + 1] - vals[i] for i in range(len(vals) - 1) if vals[i + 1] > vals[i]]
        tol = max(self._median(gaps) * 0.15, 1.0) if gaps else 50.0
        groups = [[vals[0]]]
        for v in vals[1:]:
            if abs(v - groups[-1][-1]) <= tol:
                groups[-1].append(v)
            else:
                groups.append([v])
        return [sum(g) / len(g) for g in groups]