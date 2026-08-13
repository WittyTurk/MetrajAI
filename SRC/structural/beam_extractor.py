# -*- coding: utf-8 -*-
"""
Kiriş extractor — DXF birebir.

Uzunluk önceliği:
  1) Modelspace LINE / LWPOLYLINE (Kiriş katmanı)
  2) INSERT'e en yakın çizgi
  3) Aks aralığı (AxisGrid)
  4) Yoksa length_m=0 + uyarı

Kesit / marka: INSERT blok TEXT → "KZ14  40/60"
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Optional, TYPE_CHECKING

from SRC.structural.models import Beam
from SRC.structural.axis_grid import AxisGridBuilder

if TYPE_CHECKING:
    from SRC.readers.dxf_reader import DXFReader


class BeamExtractor:
    LABEL_RE = re.compile(r"(KZ\d+|K\d+|B\d+)\s+(\d+)\s*/\s*(\d+)", re.I)
    SECTION_RE = re.compile(r"(\d+)\s*/\s*(\d+)")
    LAYER_HINTS = ["KİRİŞ", "KIRIS", "BEAM", "Kiriş"]

    def __init__(
        self,
        doc=None,
        reader: Optional["DXFReader"] = None,
        unit_to_m: Optional[float] = None,
        floor: str = "GENEL",
        snap_tol_m: float = 1.5,
        **kwargs,
    ):
        self.reader = reader
        if reader is not None:
            self.doc = reader.doc
            self.msp = reader.msp
            self.unit_to_m = reader.unit_to_m
        else:
            self.doc = doc
            self.msp = doc.modelspace() if doc is not None else None
            self.unit_to_m = unit_to_m if unit_to_m is not None else 0.01
        self.floor = floor
        self.snap_tol_m = snap_tol_m
        self.warnings: List[str] = []

    def extract(self) -> List[Beam]:
        print()
        print("=" * 55)
        print(f"BEAM EXTRACTOR (DXF birebir)  [kat: {self.floor}]")
        print("=" * 55)

        if self.msp is None:
            print("Modelspace yok.")
            return []

        plan_segs = self._collect_plan_segments()
        print(f"Plan çizgi/polyline   : {len(plan_segs)}")

        inserts = self._collect_inserts()
        print(f"Kiriş INSERT (kesitli): {len(inserts)}")

        beams: List[Beam] = []

        if inserts:
            used_seg = set()
            for ins in inserts:
                best_i, best_d, best_len = None, 1e18, 0.0
                for i, seg in enumerate(plan_segs):
                    d = self._dist_point_to_seg(ins["x"], ins["y"], seg)
                    if d < best_d:
                        best_d = d
                        best_i = i
                        best_len = seg["length_m"]

                length_m = 0.0
                from_geom = False
                tol_u = self.snap_tol_m / self.unit_to_m if self.unit_to_m > 0 else 150.0
                if best_i is not None and best_d <= tol_u:
                    length_m = best_len
                    from_geom = True
                    used_seg.add(best_i)

                if length_m < 0.3:
                    self.warnings.append(
                        f"Kiriş {ins.get('mark') or ins['block']}: plan uzunluğu okunamadı"
                    )
                    length_m = 0.0
                    from_geom = False

                beams.append(Beam(
                    id=0,
                    mark=ins.get("mark") or "",
                    section=ins["section"],
                    length_m=length_m,
                    x=ins["x"],
                    y=ins["y"],
                    floor=self.floor,
                    rebar_notes=ins.get("notes") or [],
                    source_block=ins.get("block") or "",
                    length_from_geometry=from_geom,
                ))
        else:
            for seg in plan_segs:
                if seg["length_m"] < 0.5:
                    continue
                beams.append(Beam(
                    id=0,
                    mark="",
                    section=(0.0, 0.0),
                    length_m=seg["length_m"],
                    x=seg["mx"],
                    y=seg["my"],
                    floor=self.floor,
                    length_from_geometry=True,
                ))

        beams = self._dedup(beams, tol_u=50.0)
        for i, b in enumerate(beams, start=1):
            b.id = i

        with_sec = [b for b in beams if b.section[0] > 0]
        print(f"Unique kiriş (kesitli): {len(with_sec)}")
        if self.warnings:
            print(f"Uyarı (plan boyu)    : {len(self.warnings)}")

        result = with_sec if with_sec else beams
        result = self._apply_axis_lengths(result)
        self._print_summary(result)
        return result

    def _collect_plan_segments(self) -> List[dict]:
        segs = []
        if self.reader is not None:
            for ln in self.reader.lines_on_layer(self.LAYER_HINTS):
                if ln["length_m"] < 0.1:
                    continue
                x1, y1 = ln["start"]
                x2, y2 = ln["end"]
                segs.append({
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "mx": (x1 + x2) / 2, "my": (y1 + y2) / 2,
                    "length_m": ln["length_m"], "layer": ln["layer"],
                })
            for pl in self.reader.polylines_on_layer(self.LAYER_HINTS, closed_only=False):
                if pl["closed"] or pl["length_m"] < 0.1:
                    continue
                pts = pl["points"]
                for i in range(len(pts) - 1):
                    x1, y1 = pts[i]
                    x2, y2 = pts[i + 1]
                    lm = math.hypot(x2 - x1, y2 - y1) * self.unit_to_m
                    if lm < 0.1:
                        continue
                    segs.append({
                        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "mx": (x1 + x2) / 2, "my": (y1 + y2) / 2,
                        "length_m": lm, "layer": pl["layer"],
                    })
            return segs

        for e in self.msp:
            layer = e.dxf.layer
            lu = layer.upper().replace("İ", "I").replace("Ş", "S")
            ok = any(
                h.upper().replace("İ", "I").replace("Ş", "S") in lu or layer == h
                for h in self.LAYER_HINTS
            )
            if not ok and "KIRIS" not in lu and "BEAM" not in lu:
                continue
            if e.dxftype() == "LINE":
                x1, y1 = e.dxf.start.x, e.dxf.start.y
                x2, y2 = e.dxf.end.x, e.dxf.end.y
                lm = math.hypot(x2 - x1, y2 - y1) * self.unit_to_m
                if lm < 0.1:
                    continue
                segs.append({
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "mx": (x1 + x2) / 2, "my": (y1 + y2) / 2,
                    "length_m": lm, "layer": layer,
                })
            elif e.dxftype() == "LWPOLYLINE" and not e.closed:
                pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
                for i in range(len(pts) - 1):
                    x1, y1 = pts[i]
                    x2, y2 = pts[i + 1]
                    lm = math.hypot(x2 - x1, y2 - y1) * self.unit_to_m
                    if lm < 0.1:
                        continue
                    segs.append({
                        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "mx": (x1 + x2) / 2, "my": (y1 + y2) / 2,
                        "length_m": lm, "layer": layer,
                    })
        return segs

    def _collect_inserts(self) -> List[dict]:
        raw = []
        for e in self.msp:
            if e.dxftype() != "INSERT":
                continue
            layer = e.dxf.layer
            lu = layer.upper().replace("İ", "I").replace("Ş", "S")
            ok = any(
                h.upper().replace("İ", "I").replace("Ş", "S") in lu or layer == h
                for h in self.LAYER_HINTS
            )
            if not ok and "KIRIS" not in lu and "BEAM" not in lu and layer != "Kiriş":
                continue
            mark, section, notes = self._read_block_section(e.dxf.name)
            if section is None:
                continue
            raw.append({
                "mark": mark or "",
                "section": section,
                "notes": notes,
                "x": e.dxf.insert.x,
                "y": e.dxf.insert.y,
                "block": e.dxf.name,
            })
        return raw

    def _read_block_section(self, block_name: str):
        block = self.doc.blocks.get(block_name) if self.doc else None
        if block is None:
            return None, None, []
        mark = None
        section = None
        notes = []
        for e in block:
            text = None
            if e.dxftype() == "TEXT":
                text = e.dxf.text.strip()
            elif e.dxftype() == "MTEXT":
                text = (getattr(e, "text", None) or "").strip()
                text = re.sub(r"\\[A-Za-z][^;]*;", "", text)
                text = re.sub(r"[{}]", "", text).strip()
            if not text:
                continue
            m = self.LABEL_RE.search(text)
            if m:
                mark = m.group(1).upper()
                a, b = float(m.group(2)), float(m.group(3))
                if 15 <= a <= 120 and 20 <= b <= 150:
                    section = (a, b)
            elif section is None:
                m2 = self.SECTION_RE.search(text)
                if m2:
                    a, b = float(m2.group(1)), float(m2.group(2))
                    if 15 <= a <= 120 and 20 <= b <= 150:
                        section = (a, b)
            up = text.upper()
            if "Ø" in text or "ETR" in up:
                notes.append(text)
        return mark, section, notes

    @staticmethod
    def _dist_point_to_seg(px, py, seg) -> float:
        x1, y1, x2, y2 = seg["x1"], seg["y1"], seg["x2"], seg["y2"]
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

    def _dedup(self, beams: List[Beam], tol_u: float = 50.0) -> List[Beam]:
        groups: List[Beam] = []
        for b in beams:
            placed = False
            for g in groups:
                if abs(b.x - g.x) <= tol_u and abs(b.y - g.y) <= tol_u:
                    if b.section[0] > g.section[0]:
                        g.section = b.section
                        g.mark = b.mark or g.mark
                    if b.length_m > g.length_m:
                        g.length_m = b.length_m
                        g.length_from_geometry = b.length_from_geometry
                    placed = True
                    break
            if not placed:
                groups.append(b)
        return groups

    def _apply_axis_lengths(self, beams: List[Beam]) -> List[Beam]:
        """Plan boyu yoksa aks aralığından uzunluk ata."""
        if self.doc is None:
            return beams
        need = [b for b in beams if b.length_m < 0.3 and b.section[0] > 0]
        if not need:
            return beams

        grid = AxisGridBuilder(self.doc, unit_to_m_hint=self.unit_to_m).build()
        if grid.total_x_m < 0.5 and grid.total_y_m < 0.5:
            self.warnings.append("Aks grid okunamadı; kiriş boyları boş kaldı")
            return beams

        x_spans = grid.x_spacings_m
        y_spans = grid.y_spacings_m
        avg_x = sum(x_spans) / len(x_spans) if x_spans else 0.0
        avg_y = sum(y_spans) / len(y_spans) if y_spans else 0.0
        default_span = avg_x if avg_x >= avg_y else avg_y
        if default_span < 0.5:
            default_span = max(avg_x, avg_y, grid.total_x_m, grid.total_y_m)

        for b in need:
            b.length_m = default_span
            b.length_from_geometry = False

        self.warnings.append(
            f"Aks grid ile {len(need)} kirişe boy atandı "
            f"(span={default_span:.2f} m; X={grid.x_spacings_m}, Y={grid.y_spacings_m})"
        )
        print(f"Aks grid boy ataması : {len(need)} kiriş × {default_span:.2f} m")
        return beams

    def _print_summary(self, beams: List[Beam]):
        sec = Counter(b.section for b in beams if b.section[0] > 0)
        print("\nKesit dağılımı:")
        for (a, b), n in sec.most_common():
            print(f"  {a:.0f}/{b:.0f}  →  {n} adet")
        total_len = sum(b.length_m for b in beams)
        geom_n = sum(1 for b in beams if b.length_from_geometry)
        print(f"Toplam kiriş   : {len(beams)}")
        print(f"Toplam uzunluk : {total_len:.2f} m")
        print(f"Geometriden    : {geom_n} / {len(beams)}")