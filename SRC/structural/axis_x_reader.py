# -*- coding: utf-8 -*-
"""
X yönü aks taraması (düşey çizgiler → X konumu).
Etiket: 1,2,11a,6' veya A,B,B' — yönelim axis_grid'te.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ezdxf.document import Drawing


@dataclass
class AxisBand:
    label: str
    position_u: float
    samples: int = 1


@dataclass
class AxisDirectionResult:
    bands: List[AxisBand] = field(default_factory=list)
    source: str = ""

    @property
    def labels(self) -> List[str]:
        return [b.label for b in self.bands]

    @property
    def positions_u(self) -> List[float]:
        return [b.position_u for b in self.bands]

    @property
    def ok(self) -> bool:
        return len(self.bands) >= 2


NUM_LABEL = re.compile(r"^(\d{1,3})([A-Za-z])?(['\u2019])?$")
LETTER_LABEL = re.compile(r"^([A-Za-z]{1,2})(\d{0,2})(['\u2019])?$")


def normalize_label(raw: str) -> Optional[str]:
    t = (raw or "").strip().replace(" ", "").replace("\u2019", "'")
    if not t or len(t) > 5:
        return None
    if NUM_LABEL.match(t):
        return t.upper() if t[-1:].isalpha() else t
    if LETTER_LABEL.match(t) and not re.match(r"^\d", t):
        return t.upper()
    return None


def is_numeric_family(label: str) -> bool:
    return bool(re.match(r"^\d", label or ""))


def is_letter_family(label: str) -> bool:
    return bool(re.match(r"^[A-Za-z]", label or ""))


class AxisVerticalScanner:
    LAYER = re.compile(r"AKS|EKSEN|AXIS|AXES", re.I)

    def __init__(self, doc: "Drawing"):
        self.doc = doc
        self.msp = doc.modelspace()

    def scan(self) -> AxisDirectionResult:
        print("--- X (düşey bant) ---")
        by_label: Dict[str, List[float]] = defaultdict(list)
        for e in self.msp:
            if e.dxftype() != "TEXT":
                continue
            if not self.LAYER.search(e.dxf.layer or ""):
                continue
            lab = normalize_label(e.dxf.text or "")
            if not lab:
                continue
            by_label[lab].append(float(e.dxf.insert.x))

        if len(by_label) >= 2:
            bands = self._bands_from_map(by_label)
            print(f"  TEXT: {len(bands)} etiket  {[b.label for b in bands]}")
            return AxisDirectionResult(bands, "TEXT")

        xs = self._vertical_line_xs()
        if len(xs) >= 2:
            bands = [AxisBand(str(i + 1), x) for i, x in enumerate(xs)]
            print(f"  LINE: {len(bands)} düşey küme")
            return AxisDirectionResult(bands, "LINE")

        print("  X: yetersiz")
        return AxisDirectionResult([], "yok")

    def _vertical_line_xs(self) -> List[float]:
        xs: List[float] = []
        for e in self.msp:
            if e.dxftype() != "LINE":
                continue
            if not self.LAYER.search(e.dxf.layer or ""):
                continue
            dx = abs(e.dxf.end.x - e.dxf.start.x)
            dy = abs(e.dxf.end.y - e.dxf.start.y)
            if dy > 1e-9 and dx < dy * 0.15:
                xs.append((e.dxf.start.x + e.dxf.end.x) / 2.0)
        return self._cluster(xs)

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