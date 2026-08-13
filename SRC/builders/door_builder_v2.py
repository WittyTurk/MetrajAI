# -*- coding: utf-8 -*-
"""
Kapı builder — DXF birebir.

Kaynak:
  INSERT (KAPI / DOOR katmanı veya blok adı)
  - konum  = insert
  - rotation = insert
  - width/height = attr / TEXT / blok bbox; yoksa 0
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional

from SRC.models.door import Door
from SRC.models.point import Point


def _norm(s: str) -> str:
    return (
        (s or "")
        .upper()
        .replace("İ", "I")
        .replace("Ş", "S")
        .replace("Ğ", "G")
        .replace("Ü", "U")
        .replace("Ö", "O")
        .replace("Ç", "C")
    )


class DoorBuilderV2:
    LAYER_KEYS = ("KAPI", "DOOR", "DOOR_", "KAPILAR")
    BLOCK_KEYS = ("KAPI", "DOOR")
    SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*[x×X]\s*(\d+(?:[.,]\d+)?)")

    def __init__(
        self,
        project=None,
        raw_doors: Optional[Iterable[object]] = None,
        layer_names: Optional[List[str]] = None,
        unit_to_m: float = 0.001,
    ):
        self.project = project
        self.raw_doors = list(raw_doors) if raw_doors is not None else None
        self.layer_names = layer_names
        self.unit_to_m = unit_to_m
        self.doc = getattr(project, "document", None) if project else None
        self.msp = getattr(project, "modelspace", None) if project else None

    def build(self) -> list[Door]:
        print()
        print("=" * 55)
        print("DOOR BUILDER V2 (DXF birebir)")
        print("=" * 55)

        entities = self.raw_doors if self.raw_doors is not None else self._collect_from_dxf()
        print(f"Ham aday : {len(entities)}")

        doors: list[Door] = []
        for index, raw in enumerate(entities, start=1):
            door = self._entity_to_door(index, raw)
            if door is not None:
                doors.append(door)

        print(f"Kapı adedi : {len(doors)}")
        with_size = sum(1 for d in doors if d.width > 0 and d.height > 0)
        print(f"Ölçüsü DXF'ten : {with_size}")
        print(f"Ölçüsü yok (0) : {len(doors) - with_size}")
        for d in doors[:12]:
            print(
                f"  Door {d.id:3d}  W={d.width:.1f} H={d.height:.1f}  "
                f"@({d.position.x:.0f},{d.position.y:.0f})  {d.door_type or ''}"
            )
        if len(doors) > 12:
            print(f"  ... +{len(doors) - 12}")

        if self.project is not None and hasattr(self.project, "doors"):
            self.project.doors = doors
        return doors

    def _collect_from_dxf(self) -> list:
        if self.msp is None:
            return []
        result = []
        for e in self.msp:
            if e.dxftype() != "INSERT":
                continue
            layer = _norm(e.dxf.layer)
            block = _norm(e.dxf.name)
            layer_ok = any(k in layer for k in self.LAYER_KEYS)
            block_ok = any(k in block for k in self.BLOCK_KEYS)
            if self.layer_names:
                targets = {_norm(n) for n in self.layer_names}
                layer_ok = layer in targets or any(t in layer for t in targets)
            if layer_ok or block_ok:
                result.append(e)
        return result

    def _entity_to_door(self, index: int, raw) -> Optional[Door]:
        position = self._extract_position(raw)
        rotation = self._extract_float(raw, "rotation", default=None)
        if rotation is None:
            rotation = self._read_dxf_field(raw, "rotation") or 0.0
        try:
            rotation = float(rotation)
        except (TypeError, ValueError):
            rotation = 0.0

        width, height, source = self._extract_size(raw)
        door_type = getattr(getattr(raw, "dxf", None), "name", None)
        door_no = self._extract_text_attr(raw, ("NO", "NUMARA", "KAPI_NO", "MARK"))

        return Door(
            id=index,
            position=position,
            width=width,
            height=height,
            rotation=rotation,
            wall_id=None,
            room_ids=[],
            door_no=door_no,
            door_type=door_type or source,
            building_id=None,
            level_id=None,
            properties={"size_source": source},
            is_valid=True,
        )

    def _extract_size(self, raw) -> tuple[float, float, str]:
        w = self._extract_float(raw, "width", default=None)
        h = self._extract_float(raw, "height", default=None)
        if w is not None and h is not None and w > 0 and h > 0:
            return w, h, "attr"

        for t in self._block_texts(raw):
            m = self.SIZE_RE.search(t.replace(",", "."))
            if m:
                return float(m.group(1)), float(m.group(2)), "text"

        bbox = self._block_bbox(raw)
        if bbox is not None:
            bw, bh = bbox
            if bw > 0 and bh > 0:
                return bw, bh, "bbox"

        return 0.0, 0.0, "none"

    def _block_texts(self, raw) -> List[str]:
        name = getattr(getattr(raw, "dxf", None), "name", None)
        if not name or self.doc is None:
            return []
        block = self.doc.blocks.get(name)
        if block is None:
            return []
        out = []
        for e in block:
            if e.dxftype() == "TEXT":
                out.append(e.dxf.text.strip())
            elif e.dxftype() == "MTEXT":
                out.append((getattr(e, "text", "") or "").strip())
            elif e.dxftype() == "ATTRIB":
                out.append(getattr(e.dxf, "text", "") or "")
        try:
            for a in raw.attribs:
                out.append(a.dxf.text)
        except Exception:
            pass
        return out

    def _block_bbox(self, raw) -> Optional[tuple[float, float]]:
        name = getattr(getattr(raw, "dxf", None), "name", None)
        if not name or self.doc is None:
            return None
        block = self.doc.blocks.get(name)
        if block is None:
            return None
        xs, ys = [], []
        for e in block:
            if e.dxftype() == "LINE":
                xs += [e.dxf.start.x, e.dxf.end.x]
                ys += [e.dxf.start.y, e.dxf.end.y]
            elif e.dxftype() == "LWPOLYLINE":
                for p in e.get_points():
                    xs.append(float(p[0]))
                    ys.append(float(p[1]))
            elif e.dxftype() == "CIRCLE":
                xs += [e.dxf.center.x - e.dxf.radius, e.dxf.center.x + e.dxf.radius]
                ys += [e.dxf.center.y - e.dxf.radius, e.dxf.center.y + e.dxf.radius]
        if not xs or not ys:
            return None
        sx = float(getattr(raw.dxf, "xscale", 1.0) or 1.0)
        sy = float(getattr(raw.dxf, "yscale", 1.0) or 1.0)
        return abs(max(xs) - min(xs)) * abs(sx), abs(max(ys) - min(ys)) * abs(sy)

    def _extract_text_attr(self, raw, keys) -> Optional[str]:
        for t in self._block_texts(raw):
            up = _norm(t)
            for k in keys:
                if k in up:
                    return t.strip()
        return None

    def _extract_position(self, raw) -> Point:
        candidates = [
            self._read_field(raw, "position"),
            self._read_field(raw, "point"),
            self._read_field(raw, "center"),
            self._read_field(raw, "insert"),
            self._read_dxf_field(raw, "insert"),
        ]
        for candidate in candidates:
            point = self._to_point(candidate)
            if point is not None:
                return point
        x = self._extract_float(raw, "x", default=0.0) or 0.0
        y = self._extract_float(raw, "y", default=0.0) or 0.0
        return Point(x, y)

    def _extract_float(self, raw, field_name: str, default: float | None = 0.0):
        value = self._read_field(raw, field_name)
        if value is None:
            value = self._read_dxf_field(raw, field_name)
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _read_field(raw, field_name: str):
        if isinstance(raw, dict):
            return raw.get(field_name)
        return getattr(raw, field_name, None)

    @staticmethod
    def _read_dxf_field(raw, field_name: str):
        dxf = getattr(raw, "dxf", None)
        if dxf is None:
            return None
        return getattr(dxf, field_name, None)

    @staticmethod
    def _to_point(value) -> Point | None:
        if value is None:
            return None
        if isinstance(value, Point):
            return value
        x = getattr(value, "x", None)
        y = getattr(value, "y", None)
        if x is not None and y is not None:
            try:
                return Point(float(x), float(y))
            except (TypeError, ValueError):
                return None
        if isinstance(value, (tuple, list)) and len(value) >= 2:
            try:
                return Point(float(value[0]), float(value[1]))
            except (TypeError, ValueError):
                return None
        return None