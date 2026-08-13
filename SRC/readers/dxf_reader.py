# -*- coding: utf-8 -*-
"""
Gelişmiş DXF Reader — mimari + statik + elektrik + mekanik + peyzaj.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import math
import re

import ezdxf
from ezdxf.document import Drawing


LAYER_CATALOG = {
    "architectural": [
        "DUVAR", "SIVA", "KAPI", "PENCERE", "MAHAL", "DOSEME", "DÖŞEME",
        "GOR", "GÖR", "ALAN", "TAVAN", "SUPURGELIK",
    ],
    "structural": [
        "KOLON", "KIRIS", "KİRİŞ", "PERDE", "RADYE", "AKS", "DOSEME", "DÖŞEME",
        "STATIK", "TEMEL",
    ],
    "electrical": [
        "E-", "ELEKTRIK", "ELEKTRİK", "PRIZ", "AYDINLATMA", "KABLO", "PANO",
        "E_PRIZ", "E_LAMBA", "E_KABLO", "E_PANO", "LIGHT", "SOCKET",
    ],
    "mechanical": [
        "M-", "MEKANIK", "MEKANİK", "BORU", "KANAL", "MENFEZ", "KLIMA", "KLİMA",
        "TESISAT", "TESİSAT", "HVAC", "PIPE", "DUCT",
    ],
    "landscape": [
        "PEYZAJ", "CEVRE", "ÇEVRE", "YESIL", "YEŞİL", "CIM", "ÇİM",
        "AGAC", "AĞAÇ", "BITKI", "BİTKİ", "YURUYUS", "YÜRÜYÜŞ", "YAYA",
        "KALDIRIM", "PARK", "BAHCE", "BAHÇE", "LANDSCAPE", "SITE",
        "BORDUR", "BORDÜR", "OTOPARK", "RIHTIM",
    ],
}


class DXFReader:

    def __init__(self, project=None, input_folder: str = "INPUT"):
        self.project = project
        self.input_folder = Path(input_folder)
        self.file_path: Optional[Path] = None
        self.doc: Optional[Drawing] = None
        self.msp = None
        self.unit_to_m: float = 0.001
        self.unit_name: str = "mm"

    def find_dxf(self) -> Path:
        files = list(self.input_folder.glob("*.dxf"))
        if not files:
            raise FileNotFoundError(f"{self.input_folder} içinde DXF yok.")
        self.file_path = files[0]
        return self.file_path

    def read(self, path: Optional[str] = None):
        if path:
            self.file_path = Path(path)
        else:
            self.find_dxf()

        self.doc = ezdxf.readfile(str(self.file_path))
        self.msp = self.doc.modelspace()
        self._detect_units()

        if self.project is not None:
            self.project.file_path = self.file_path
            self.project.document = self.doc
            self.project.modelspace = self.msp
            if hasattr(self.project, "unit_to_m"):
                self.project.unit_to_m = self.unit_to_m

        print(f"DXF açıldı: {self.file_path}")
        print(f"Birim     : {self.unit_name}  (unit_to_m={self.unit_to_m})")
        return self.msp

    def read_many(self, paths: List[Tuple[str, str]]) -> Dict[str, "DXFReader"]:
        result = {}
        for floor, path in paths:
            r = DXFReader(project=None, input_folder=self.input_folder)
            r.read(path)
            result[floor] = r
        return result

    def _detect_units(self):
        try:
            code = int(self.doc.header.get("$INSUNITS", 0))
        except Exception:
            code = 0
        mapping = {
            4: ("mm", 0.001),
            5: ("cm", 0.01),
            6: ("m", 1.0),
            1: ("inch", 0.0254),
        }
        if code in mapping:
            self.unit_name, self.unit_to_m = mapping[code]
            return
        lengths = []
        for e in self.msp:
            if e.dxftype() == "LINE":
                lengths.append(math.hypot(
                    e.dxf.end.x - e.dxf.start.x,
                    e.dxf.end.y - e.dxf.start.y,
                ))
            if len(lengths) > 200:
                break
        if lengths:
            avg = sum(lengths) / len(lengths)
            if avg > 500:
                self.unit_name, self.unit_to_m = "mm", 0.001
            elif avg > 5:
                self.unit_name, self.unit_to_m = "cm", 0.01
            else:
                self.unit_name, self.unit_to_m = "m", 1.0

    def entity_statistics(self) -> Dict[str, int]:
        stats: Dict[str, int] = {}
        for entity in self.msp:
            name = entity.dxftype()
            stats[name] = stats.get(name, 0) + 1
        return dict(sorted(stats.items(), key=lambda x: -x[1]))

    def layer_statistics(self) -> Dict[str, int]:
        stats: Dict[str, int] = {}
        for entity in self.msp:
            layer = entity.dxf.layer
            stats[layer] = stats.get(layer, 0) + 1
        return dict(sorted(stats.items(), key=lambda x: -x[1]))

    def print_summary(self):
        print("\n=== Entity tipleri ===")
        for k, v in self.entity_statistics().items():
            print(f"  {k:20} {v}")
        print("\n=== Katmanlar ===")
        for k, v in self.layer_statistics().items():
            print(f"  {k:40} {v}")

    def lines_on_layer(self, layer_names: List[str]) -> List[dict]:
        names = {n.upper() for n in layer_names}
        result = []
        for e in self.msp:
            if e.dxftype() != "LINE":
                continue
            layer_u = e.dxf.layer.upper().replace("İ", "I").replace("Ş", "S")
            if e.dxf.layer.upper() not in names and not any(n in layer_u for n in names):
                if e.dxf.layer not in layer_names:
                    continue
            x1, y1 = e.dxf.start.x, e.dxf.start.y
            x2, y2 = e.dxf.end.x, e.dxf.end.y
            length_u = math.hypot(x2 - x1, y2 - y1)
            result.append({
                "start": (x1, y1),
                "end": (x2, y2),
                "length_u": length_u,
                "length_m": length_u * self.unit_to_m,
                "layer": e.dxf.layer,
                "handle": e.dxf.handle,
            })
        return result

    def polylines_on_layer(self, layer_names: List[str], closed_only: bool = False) -> List[dict]:
        names = {n.upper() for n in layer_names}
        result = []
        for e in self.msp:
            if e.dxftype() != "LWPOLYLINE":
                continue
            layer_u = e.dxf.layer.upper().replace("İ", "I").replace("Ş", "S")
            if e.dxf.layer.upper() not in names and not any(n in layer_u for n in names):
                if e.dxf.layer not in layer_names:
                    continue
            if closed_only and not e.closed:
                continue
            pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
            length_u = 0.0
            for i in range(len(pts) - 1):
                length_u += math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
            if e.closed and len(pts) >= 2:
                length_u += math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1])
            area_u = abs(self._ring_area(pts)) if e.closed and len(pts) >= 3 else 0.0
            result.append({
                "points": pts,
                "closed": bool(e.closed),
                "length_u": length_u,
                "length_m": length_u * self.unit_to_m,
                "area_u": area_u,
                "area_m2": area_u * (self.unit_to_m ** 2),
                "layer": e.dxf.layer,
                "handle": e.dxf.handle,
            })
        return result

    def inserts_on_layer(self, layer_names: List[str]) -> List[dict]:
        names = {n.upper() for n in layer_names}
        result = []
        for e in self.msp:
            if e.dxftype() != "INSERT":
                continue
            layer_u = e.dxf.layer.upper().replace("İ", "I").replace("Ş", "S")
            if e.dxf.layer.upper() not in names and not any(n in layer_u for n in names):
                if e.dxf.layer not in layer_names:
                    continue
            block_info = self.inspect_block(e.dxf.name)
            result.append({
                "x": e.dxf.insert.x,
                "y": e.dxf.insert.y,
                "block": e.dxf.name,
                "layer": e.dxf.layer,
                "handle": e.dxf.handle,
                "texts": block_info["texts"],
                "max_segment_u": block_info["max_segment_u"],
                "max_segment_m": block_info["max_segment_u"] * self.unit_to_m,
                "closed_area_u": block_info["closed_area_u"],
                "closed_area_m2": block_info["closed_area_u"] * (self.unit_to_m ** 2),
            })
        return result

    def inspect_block(self, block_name: str) -> dict:
        texts = []
        max_seg = 0.0
        best_area = 0.0
        block = self.doc.blocks.get(block_name) if self.doc else None
        if block is None:
            return {"texts": texts, "max_segment_u": 0.0, "closed_area_u": 0.0}
        for e in block:
            if e.dxftype() == "TEXT":
                texts.append(e.dxf.text.strip())
            elif e.dxftype() == "MTEXT":
                t = getattr(e, "text", None) or ""
                t = re.sub(r"\\[A-Za-z][^;]*;", "", t)
                t = re.sub(r"[{}]", "", t).strip()
                if t:
                    texts.append(t)
            elif e.dxftype() == "LINE":
                max_seg = max(max_seg, math.hypot(
                    e.dxf.end.x - e.dxf.start.x,
                    e.dxf.end.y - e.dxf.start.y,
                ))
            elif e.dxftype() == "LWPOLYLINE":
                pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
                for i in range(len(pts) - 1):
                    max_seg = max(max_seg, math.hypot(
                        pts[i + 1][0] - pts[i][0],
                        pts[i + 1][1] - pts[i][1],
                    ))
                if getattr(e, "closed", False) and len(pts) >= 3:
                    best_area = max(best_area, abs(self._ring_area(pts)))
        return {"texts": texts, "max_segment_u": max_seg, "closed_area_u": best_area}

    def texts_on_layer(self, layer_names: Optional[List[str]] = None) -> List[dict]:
        names = {n.upper() for n in (layer_names or [])} if layer_names else None
        result = []
        for e in self.msp:
            if e.dxftype() not in ("TEXT", "MTEXT"):
                continue
            if names is not None:
                layer_u = e.dxf.layer.upper().replace("İ", "I")
                if e.dxf.layer.upper() not in names and not any(n in layer_u for n in names):
                    continue
            if e.dxftype() == "TEXT":
                text = e.dxf.text.strip()
                x, y = e.dxf.insert.x, e.dxf.insert.y
            else:
                text = getattr(e, "text", None) or ""
                text = re.sub(r"\\[A-Za-z][^;]*;", "", text)
                text = re.sub(r"[{}]", "", text).strip()
                x, y = e.dxf.insert.x, e.dxf.insert.y
            if not text:
                continue
            result.append({
                "text": text, "x": x, "y": y,
                "layer": e.dxf.layer, "type": e.dxftype(),
            })
        return result

    def dimensions(self) -> List[dict]:
        result = []
        for e in self.msp:
            if not e.dxftype().startswith("DIMENSION"):
                continue
            try:
                measurement = float(e.dxf.actual_measurement)
            except Exception:
                measurement = None
            text = ""
            try:
                text = e.dxf.text or ""
            except Exception:
                pass
            result.append({
                "measurement_u": measurement,
                "measurement_m": measurement * self.unit_to_m if measurement else None,
                "text": text,
                "layer": e.dxf.layer,
            })
        return result

    def layers_for_discipline(self, discipline: str) -> List[str]:
        keys = LAYER_CATALOG.get(discipline.lower(), [])
        keys_u = [k.upper().replace("İ", "I").replace("Ş", "S") for k in keys]
        found = []
        for layer in self.layer_statistics().keys():
            lu = layer.upper().replace("İ", "I").replace("Ş", "S")
            if any(k in lu or lu.startswith(k.rstrip("-")) for k in keys_u):
                found.append(layer)
        return found

    def by_discipline(self, discipline: str) -> dict:
        layers = self.layers_for_discipline(discipline)
        if not layers:
            return {
                "discipline": discipline,
                "layers": [],
                "lines": [],
                "polylines": [],
                "inserts": [],
                "texts": [],
            }
        return {
            "discipline": discipline,
            "layers": layers,
            "lines": self.lines_on_layer(layers),
            "polylines": self.polylines_on_layer(layers),
            "inserts": self.inserts_on_layer(layers),
            "texts": self.texts_on_layer(layers),
        }

    def count_blocks_on_layers(self, layer_names: List[str]) -> dict:
        from collections import Counter
        inserts = self.inserts_on_layer(layer_names)
        return dict(Counter(i["block"] for i in inserts))

    @staticmethod
    def _ring_area(pts: List[Tuple[float, float]]) -> float:
        n = len(pts)
        if n < 3:
            return 0.0
        a = 0.0
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            a += x1 * y2 - x2 * y1
        return a / 2.0