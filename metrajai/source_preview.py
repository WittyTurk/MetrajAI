"""Read-only, bounded DXF linework for an engineer's source/element overlay."""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf
from ezdxf.path import from_hatch, make_path

from .contracts import DrawingUnit, SourceFile, SourceFormat
from .units import unit_scale

MAX_STROKES = 12_000
MAX_TEXTS = 600
MAX_POINTS_PER_STROKE = 2_048


def _walk(entities, *, depth: int = 0):
    if depth > 8:
        return
    for entity in entities:
        if entity.dxftype() in {"INSERT", "DIMENSION"}:
            try:
                yield from _walk(entity.virtual_entities(), depth=depth + 1)
            except Exception:
                continue
        else:
            yield entity


def _points(path, scale: float) -> list[list[float]]:
    tolerance = max(0.005 / scale, 0.05)
    result: list[list[float]] = []
    try:
        for point in path.flattening(distance=tolerance):
            x, y = float(point.x) * scale, float(point.y) * scale
            if not math.isfinite(x) or not math.isfinite(y) or max(abs(x), abs(y)) > 1_000_000:
                return []
            result.append([round(x, 6), round(y, 6)])
            if len(result) > MAX_POINTS_PER_STROKE:
                return []
    except Exception:
        return []
    return result if len(result) >= 2 else []


def _layer_role(layer: str) -> str:
    name = layer.upper()
    if "DUVAR" in name or "WALL" in name:
        return "wall"
    if any(token in name for token in ("KAPI", "PENCERE", "DOOR", "WINDOW")):
        return "opening"
    if any(token in name for token in ("ALAN", "MAHAL", "ROOM")):
        return "room"
    if any(token in name for token in ("OLCU", "ÖLÇÜ", "DIM", "AKS")):
        return "annotation"
    return "other"


def _raw_text(entity, scale: float) -> dict | None:
    kind = entity.dxftype()
    if kind not in {"TEXT", "MTEXT", "ATTRIB"}:
        return None
    try:
        value = str(entity.plain_text() if kind == "MTEXT" else entity.dxf.text).strip()
        insert = entity.dxf.insert
        x, y = float(insert.x) * scale, float(insert.y) * scale
        raw_height = float(entity.dxf.get("char_height" if kind == "MTEXT" else "height", 0))
    except Exception:
        return None
    if not value or not all(math.isfinite(item) for item in (x, y, raw_height)):
        return None
    if max(abs(x), abs(y)) > 1_000_000:
        return None
    return {
        "x": round(x, 6),
        "y": round(y, 6),
        "text": value.replace("\n", " ")[:100],
        "height_m": round(min(max(raw_height * scale, 0.06), 0.5), 4),
    }


def _overlaps_focus(
    points: list[list[float]], focus_bbox: tuple[float, float, float, float]
) -> bool:
    x1, y1, x2, y2 = focus_bbox
    return not (
        max(point[0] for point in points) < x1
        or min(point[0] for point in points) > x2
        or max(point[1] for point in points) < y1
        or min(point[1] for point in points) > y2
    )


def build_source_preview(
    source: SourceFile,
    path: str | Path,
    root_handle: str = "",
    stroke_offset: int = 0,
    focus_bbox: tuple[float, float, float, float] | None = None,
) -> dict:
    if source.source_format != SourceFormat.DXF:
        raise ValueError("Ham çizim önizlemesi yalnız DXF kaynakları için kullanılabilir")
    if stroke_offset < 0:
        raise ValueError("Önizleme çizgi başlangıcı negatif olamaz")
    if focus_bbox is not None and (
        len(focus_bbox) != 4
        or not all(math.isfinite(value) for value in focus_bbox)
        or focus_bbox[0] >= focus_bbox[2]
        or focus_bbox[1] >= focus_bbox[3]
    ):
        raise ValueError("Önizleme odak alanı geçersiz")
    unit = source.drawing_unit if source.unit_confirmed else source.detected_unit
    if unit == DrawingUnit.UNKNOWN:
        raise ValueError("Ham çizim önizlemesi için önce DXF birimini doğrulayın")
    scale = unit_scale(unit)
    document = ezdxf.readfile(path)
    modelspace = list(document.modelspace())
    if root_handle:
        roots = [item for item in modelspace if str(item.dxf.get("handle", "")) == root_handle]
        if len(roots) != 1:
            raise ValueError("Seçilen çizim bölgesi bu kaynakta bulunamadı")
    else:
        roots = modelspace

    strokes: list[dict] = []
    texts: list[dict] = []
    truncated = False
    stroke_index = 0
    for entity in _walk(roots):
        text = _raw_text(entity, scale)
        if text is not None:
            if focus_bbox is not None and not (
                focus_bbox[0] <= text["x"] <= focus_bbox[2]
                and focus_bbox[1] <= text["y"] <= focus_bbox[3]
            ):
                continue
            if stroke_offset == 0 and len(texts) < MAX_TEXTS:
                texts.append(text)
            elif stroke_offset == 0:
                truncated = True
            continue
        kind = entity.dxftype()
        if kind not in {
            "LINE",
            "LWPOLYLINE",
            "POLYLINE",
            "ARC",
            "CIRCLE",
            "ELLIPSE",
            "SPLINE",
            "HATCH",
        }:
            continue
        try:
            paths = list(from_hatch(entity)) if kind == "HATCH" else [make_path(entity)]
        except Exception:
            continue
        layer = str(entity.dxf.get("layer", ""))
        for path_item in paths:
            points = _points(path_item, scale)
            if points and (focus_bbox is None or _overlaps_focus(points, focus_bbox)):
                if stroke_index < stroke_offset:
                    stroke_index += 1
                    continue
                if len(strokes) >= MAX_STROKES:
                    truncated = True
                    break
                strokes.append({"points": points, "role": _layer_role(layer), "layer": layer})
                stroke_index += 1
        if truncated and len(strokes) >= MAX_STROKES:
            break

    coordinates = [point for stroke in strokes for point in stroke["points"]]
    if not coordinates:
        coordinates = [[item["x"], item["y"]] for item in texts]
    bounds = (
        [
            min(point[0] for point in coordinates),
            min(point[1] for point in coordinates),
            max(point[0] for point in coordinates),
            max(point[1] for point in coordinates),
        ]
        if coordinates
        else None
    )
    return {
        "source_id": source.id,
        "region_id": root_handle,
        "unit": unit.value,
        "bounds": bounds,
        "strokes": strokes,
        "texts": texts,
        "truncated": truncated,
        "next_offset": stroke_offset + len(strokes)
        if truncated and len(strokes) >= MAX_STROKES
        else None,
    }
