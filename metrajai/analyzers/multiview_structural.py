from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal

from ezdxf import bbox
from ezdxf.math import area as polygon_area
from ezdxf.path import make_path

from ..contracts import (
    AnalysisWarning,
    DetectedElement,
    DrawingUnit,
    Geometry,
    ReviewStatus,
    SourceFile,
)
from ..units import unit_scale

ViewKind = Literal["formwork", "foundation", "rebar", "column_application"]

ELEVATION = re.compile(r"(?P<value>[+-]\s*\d+(?:[.,]\d+)?)")
BEAM_LABEL = re.compile(
    r"(?P<label>[A-Z]{1,5}\d+[A-Z0-9-]*)\s*"
    r"\(?\s*(?P<width>\d+(?:[.,]\d+)?)\s*/\s*"
    r"(?P<height>\d+(?:[.,]\d+)?)\s*\)?",
    re.IGNORECASE,
)
SLAB_LABEL = re.compile(r"^[A-Z]{1,3}\d{1,3}$", re.IGNORECASE)
SLAB_THICKNESS = re.compile(r"^(?:D=)?(?P<value>\d+(?:[.,]\d+)?)CM$", re.IGNORECASE)
STAIR_LABEL = re.compile(
    r"\b(?P<label>M\d+)\s+MERDIVENI\s+(?P<count>\d+)\s*"
    r"\(\s*(?P<tread>\d+(?:[.,]\d+)?)\s*/\s*(?P<riser>\d+(?:[.,]\d+)?)\s*\)",
    re.IGNORECASE,
)
STAIR_THICKNESS = re.compile(
    r"(?:H|D|PLAK(?:\s+KALINLIGI)?)\s*[=:]?\s*(?P<value>\d+(?:[.,]\d+)?)\s*CM",
    re.IGNORECASE,
)
FOUNDATION_THICKNESS = re.compile(
    r"(?:RADYE\s+TEMEL\s*)?(?:H\s*=\s*)?(?P<value>\d+(?:[.,]\d+)?)\s*CM",
    re.IGNORECASE,
)
OPENING_LAYER_TOKENS = ("BOSLUK", "SAFT", "ASANSOR BOSLUGU")


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(text.upper().replace("×", "X").split())


def _text(entity) -> str:
    if entity.dxftype() == "TEXT":
        return str(entity.dxf.text).strip()
    if entity.dxftype() == "MTEXT":
        return str(entity.plain_text()).strip()
    return ""


def _text_point(entity) -> tuple[float, float]:
    point = entity.dxf.insert
    return float(point.x), float(point.y)


def _raw_bbox(entity) -> tuple[float, float, float, float] | None:
    try:
        value = bbox.extents([entity], fast=True)
    except Exception:
        return None
    if not value.has_data:
        return None
    return (
        float(value.extmin.x),
        float(value.extmin.y),
        float(value.extmax.x),
        float(value.extmax.y),
    )


def _scaled_box(
    raw_box: tuple[float, float, float, float], scale: float
) -> tuple[float, float, float, float]:
    return tuple(round(value * scale, 6) for value in raw_box)  # type: ignore[return-value]


def _closed_geometry(entity, scale: float) -> ClosedGeometry | None:
    if entity.dxftype() != "LWPOLYLINE" or not bool(getattr(entity, "closed", False)):
        return None
    try:
        raw_vertices = list(make_path(entity).flattening(distance=max(0.005 / scale, 1e-6)))
        raw_points = [(float(point.x), float(point.y)) for point in raw_vertices]
    except Exception:
        raw_points = [(float(point[0]), float(point[1])) for point in entity.get_points("xy")]
    if len(raw_points) < 3:
        return None
    if raw_points[0] == raw_points[-1]:
        raw_points.pop()
    if len(raw_points) < 3:
        return None
    scaled_points = tuple((round(x * scale, 6), round(y * scale, 6)) for x, y in raw_points)
    try:
        area_m2 = abs(float(polygon_area(scaled_points)))
    except Exception:
        area_m2 = abs(
            sum(
                first[0] * second[1] - second[0] * first[1]
                for first, second in zip(
                    scaled_points,
                    scaled_points[1:] + scaled_points[:1],
                    strict=True,
                )
            )
            / 2.0
        )
    perimeter_m = sum(
        math.dist(first, second)
        for first, second in zip(
            scaled_points,
            scaled_points[1:] + scaled_points[:1],
            strict=True,
        )
    )
    xs = [point[0] for point in scaled_points]
    ys = [point[1] for point in scaled_points]
    return ClosedGeometry(
        entity=entity,
        handle=str(entity.dxf.handle),
        layer=str(entity.dxf.layer),
        points=scaled_points,
        bbox=(min(xs), min(ys), max(xs), max(ys)),
        area_m2=round(area_m2, 6),
        perimeter_m=round(perimeter_m, 6),
    )


def _contains_box(
    outer: tuple[float, float, float, float],
    inner: tuple[float, float, float, float],
    *,
    clearance: float = 0.005,
) -> bool:
    return (
        outer[0] + clearance <= inner[0]
        and outer[1] + clearance <= inner[1]
        and inner[2] <= outer[2] - clearance
        and inner[3] <= outer[3] - clearance
    )


def _boxes_overlap_ratio(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    width = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    height = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    intersection = width * height
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    smaller = min(first_area, second_area)
    return intersection / smaller if smaller > 0 else 0.0


def _identity(source: SourceFile, floor: str, element_type: str, handles: list[str]) -> str:
    value = "|".join((source.sha256, floor, element_type, *sorted(handles)))
    return "elm_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _floor_name(elevation_m: float | None, kind: ViewKind) -> str:
    if kind == "foundation":
        return "TEMEL"
    if elevation_m is None:
        return "GENEL"
    return f"{elevation_m:+.2f} Kotu"


@dataclass
class StructuralPlanView:
    id: str
    title: str
    title_handle: str
    kind: ViewKind
    origin: tuple[float, float]
    raw_x_min: float
    raw_x_max: float
    elevation_m: float | None
    floor: str

    def contains_raw_x(self, value: float) -> bool:
        return self.raw_x_min <= value < self.raw_x_max


@dataclass(frozen=True)
class AxisLine:
    entity: Any
    handle: str
    orientation: Literal["horizontal", "vertical"]
    fixed: float
    start: float
    end: float


@dataclass(frozen=True)
class BeamPair:
    first: AxisLine
    second: AxisLine
    orientation: Literal["horizontal", "vertical"]
    raw_box: tuple[float, float, float, float]
    separation: float
    overlap: float


@dataclass(frozen=True)
class BeamAnnotation:
    entity: Any
    handle: str
    label: str
    width_m: float
    height_m: float
    text: str
    point: tuple[float, float]
    orientation: Literal["horizontal", "vertical"]


@dataclass(frozen=True)
class SlabAnnotation:
    entity: Any
    handle: str
    label: str
    point: tuple[float, float]
    thickness_m: float | None
    thickness_text: str


@dataclass(frozen=True)
class ClosedGeometry:
    entity: Any
    handle: str
    layer: str
    points: tuple[tuple[float, float], ...]
    bbox: tuple[float, float, float, float]
    area_m2: float
    perimeter_m: float


@dataclass
class MultiviewStructuralResult:
    elements: list[DetectedElement]
    warnings: list[AnalysisWarning]
    views: list[StructuralPlanView]
    activated: bool
    blocked: bool = False


def _classify_title(value: str) -> tuple[ViewKind, float | None] | None:
    key = normalize(value)
    if "PLAN" not in key or "MERDIVEN" in key:
        return None
    if "KOLON" in key and "APLIKASYON" in key:
        return "column_application", None
    if "DONATI" in key:
        kind: ViewKind = "rebar"
    elif "KALIP" in key and "TEMEL" in key:
        kind = "foundation"
    elif "KALIP" in key:
        kind = "formwork"
    else:
        return None
    match = ELEVATION.search(key)
    elevation = None
    if match is not None:
        elevation = float(match.group("value").replace(" ", "").replace(",", "."))
    return kind, elevation


def discover_structural_plan_views(document) -> list[StructuralPlanView]:
    candidates: list[tuple[Any, ViewKind, float | None, tuple[float, float], str]] = []
    for entity in document.modelspace():
        value = _text(entity)
        classified = _classify_title(value)
        if classified is None:
            continue
        kind, elevation = classified
        candidates.append((entity, kind, elevation, _text_point(entity), value))
    if len(candidates) < 3:
        return []

    title_band = [
        point[1]
        for _, kind, _, point, _ in candidates
        if kind in {"formwork", "foundation", "rebar"}
    ]
    if not title_band:
        return []
    median_y = sorted(title_band)[len(title_band) // 2]
    candidates = [row for row in candidates if abs(row[3][1] - median_y) <= 650.0]
    candidates.sort(key=lambda row: row[3][0])
    if len(candidates) < 3:
        return []

    # Column application titles often omit the elevations even though the neighboring
    # formwork title contains them. Link only to the next explicit floor title.
    for index, row in enumerate(candidates):
        entity, kind, elevation, point, value = row
        if kind != "column_application" or elevation is not None:
            continue
        for sibling in candidates[index + 1 :]:
            if sibling[1] not in {"formwork", "foundation"}:
                continue
            if sibling[3][0] - point[0] > 20000:
                break
            elevation = sibling[2]
            candidates[index] = (entity, kind, elevation, point, value)
            break

    xs = [row[3][0] for row in candidates]
    boundaries = [xs[0] - max((xs[1] - xs[0]) / 2, 1000.0)]
    boundaries.extend((xs[index] + xs[index + 1]) / 2 for index in range(len(xs) - 1))
    boundaries.append(xs[-1] + max((xs[-1] - xs[-2]) / 2, 1000.0))

    views: list[StructuralPlanView] = []
    for index, (entity, kind, elevation, point, value) in enumerate(candidates):
        handle = str(entity.dxf.handle)
        view_id = (
            "view_"
            + hashlib.sha256(f"{handle}|{kind}|{point[0]:.6f}|{point[1]:.6f}".encode()).hexdigest()[
                :16
            ]
        )
        views.append(
            StructuralPlanView(
                id=view_id,
                title=value,
                title_handle=handle,
                kind=kind,
                origin=point,
                raw_x_min=boundaries[index],
                raw_x_max=boundaries[index + 1],
                elevation_m=elevation,
                floor=_floor_name(elevation, kind),
            )
        )
    return views


def _axis_line(entity, view: StructuralPlanView, scale: float) -> AxisLine | None:
    if entity.dxftype() != "LINE" or normalize(entity.dxf.layer) != "KIRIS":
        return None
    start = (float(entity.dxf.start.x), float(entity.dxf.start.y))
    end = (float(entity.dxf.end.x), float(entity.dxf.end.y))
    center_x = (start[0] + end[0]) / 2
    if not view.contains_raw_x(center_x):
        return None
    dx = abs(end[0] - start[0])
    dy = abs(end[1] - start[1])
    tolerance = 0.01 / scale
    if dx <= tolerance and dy * scale >= 0.5:
        return AxisLine(
            entity,
            str(entity.dxf.handle),
            "vertical",
            (start[0] + end[0]) / 2,
            min(start[1], end[1]),
            max(start[1], end[1]),
        )
    if dy <= tolerance and dx * scale >= 0.5:
        return AxisLine(
            entity,
            str(entity.dxf.handle),
            "horizontal",
            (start[1] + end[1]) / 2,
            min(start[0], end[0]),
            max(start[0], end[0]),
        )
    return None


def _beam_pairs(lines: list[AxisLine], scale: float) -> list[BeamPair]:
    pairs: list[BeamPair] = []
    for index, first in enumerate(lines):
        for second in lines[index + 1 :]:
            if first.orientation != second.orientation:
                continue
            separation = abs(first.fixed - second.fixed)
            separation_m = separation * scale
            if not 0.15 <= separation_m <= 1.5:
                continue
            overlap_start = max(first.start, second.start)
            overlap_end = min(first.end, second.end)
            overlap = overlap_end - overlap_start
            if overlap * scale < 0.5:
                continue
            end_error = (abs(first.start - second.start) + abs(first.end - second.end)) * scale
            if end_error > 0.06:
                continue
            low_fixed, high_fixed = sorted((first.fixed, second.fixed))
            if first.orientation == "horizontal":
                raw_box = (overlap_start, low_fixed, overlap_end, high_fixed)
            else:
                raw_box = (low_fixed, overlap_start, high_fixed, overlap_end)
            pairs.append(
                BeamPair(
                    first=first,
                    second=second,
                    orientation=first.orientation,
                    raw_box=raw_box,
                    separation=separation,
                    overlap=overlap,
                )
            )
    return pairs


def _annotation_orientation(entity) -> Literal["horizontal", "vertical"]:
    rotation = float(entity.dxf.get("rotation", 0.0)) % 180.0
    return "vertical" if 45.0 <= rotation <= 135.0 else "horizontal"


def _beam_annotations(document, view: StructuralPlanView) -> list[BeamAnnotation]:
    annotations: list[BeamAnnotation] = []
    for entity in document.modelspace():
        if entity.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        if "KIRIS" not in normalize(entity.dxf.layer):
            continue
        point = _text_point(entity)
        if not view.contains_raw_x(point[0]):
            continue
        value = _text(entity)
        match = BEAM_LABEL.search(normalize(value))
        if match is None:
            continue
        label = match.group("label").upper()
        if not label.startswith("K"):
            continue
        width_m = float(match.group("width").replace(",", ".")) / 100.0
        height_m = float(match.group("height").replace(",", ".")) / 100.0
        if not (0.15 <= width_m <= 1.5 and 0.2 <= height_m <= 2.5):
            continue
        annotations.append(
            BeamAnnotation(
                entity=entity,
                handle=str(entity.dxf.handle),
                label=label,
                width_m=round(width_m, 4),
                height_m=round(height_m, 4),
                text=value,
                point=point,
                orientation=_annotation_orientation(entity),
            )
        )
    return annotations


def _pair_score(
    pair: BeamPair,
    annotation: BeamAnnotation,
    scale: float,
) -> float | None:
    if pair.orientation != annotation.orientation:
        return None
    width_error = abs(pair.separation * scale - annotation.width_m)
    if width_error > 0.035:
        return None
    if pair.orientation == "horizontal":
        projected = annotation.point[0]
        perpendicular = abs(annotation.point[1] - (pair.raw_box[1] + pair.raw_box[3]) / 2)
        start, end = pair.raw_box[0], pair.raw_box[2]
    else:
        projected = annotation.point[1]
        perpendicular = abs(annotation.point[0] - (pair.raw_box[0] + pair.raw_box[2]) / 2)
        start, end = pair.raw_box[1], pair.raw_box[3]
    outside = max(start - projected, 0.0, projected - end)
    if outside * scale > 0.75 or perpendicular * scale > 1.5:
        return None
    return width_error * 100 + outside * scale * 10 + perpendicular * scale


def _beam_elements(
    source: SourceFile,
    view: StructuralPlanView,
    pairs: list[BeamPair],
    annotations: list[BeamAnnotation],
    scale: float,
) -> list[DetectedElement]:
    assignments: list[tuple[float, BeamPair, BeamAnnotation]] = []
    for annotation in annotations:
        choices = [
            (score, pair)
            for pair in pairs
            if (score := _pair_score(pair, annotation, scale)) is not None
        ]
        if choices:
            score, pair = min(choices, key=lambda item: item[0])
            assignments.append((score, pair, annotation))

    best_by_pair: dict[tuple[str, str], tuple[float, BeamPair, BeamAnnotation]] = {}
    for assignment in assignments:
        score, pair, _ = assignment
        key = (
            min(pair.first.handle, pair.second.handle),
            max(pair.first.handle, pair.second.handle),
        )
        if key not in best_by_pair or score < best_by_pair[key][0]:
            best_by_pair[key] = assignment

    elements: list[DetectedElement] = []
    for _, pair, annotation in best_by_pair.values():
        handles = [pair.first.handle, pair.second.handle, annotation.handle]
        scaled = _scaled_box(pair.raw_box, scale)
        length_m = round(pair.overlap * scale, 6)
        width_m = round(pair.separation * scale, 6)
        elements.append(
            DetectedElement(
                id=_identity(source, view.floor, "beam", handles),
                source_id=source.id,
                discipline=source.discipline,
                element_type="beam",
                floor=view.floor,
                layer=str(pair.first.entity.dxf.layer),
                source_handle="+".join(handles),
                geometry=Geometry(
                    kind=f"paired_{pair.orientation}_edges",
                    points=[
                        (scaled[0], scaled[1]),
                        (scaled[2], scaled[1]),
                        (scaled[2], scaled[3]),
                        (scaled[0], scaled[3]),
                        (scaled[0], scaled[1]),
                    ],
                    bbox=scaled,
                ),
                measurements={
                    "length_m": length_m,
                    "width_m": width_m,
                    "height_m": annotation.height_m,
                },
                properties={
                    "quantity_kind": "beam",
                    "element_label": annotation.label,
                    "plan_view_id": view.id,
                    "plan_title": view.title,
                    "view_kind": view.kind,
                    "elevation_m": view.elevation_m,
                    "source_handles": [pair.first.handle, pair.second.handle],
                    "beam_face_evidence": {
                        "orientation": pair.orientation,
                        "side_faces": [
                            {
                                "handle": pair.first.handle,
                                "coordinate_m": round(pair.first.fixed * scale, 6),
                            },
                            {
                                "handle": pair.second.handle,
                                "coordinate_m": round(pair.second.fixed * scale, 6),
                            },
                        ],
                    },
                    "beam_section_evidence": {
                        "element_label": annotation.label,
                        "annotation_handle": annotation.handle,
                        "section_text": annotation.text,
                        "section_width_m": annotation.width_m,
                        "section_height_m": annotation.height_m,
                        "method": "direct_plan_label_matched_to_paired_edges",
                    },
                    "length_evidence": {
                        "policy": "drawn_clear_paired_edge_overlap",
                        "length_m": length_m,
                    },
                },
                required_inputs=["length_m", "width_m", "height_m"],
                confidence=0.96,
                review_status=ReviewStatus.PENDING,
            )
        )
    return elements


def _slab_annotations(document, view: StructuralPlanView, scale: float) -> list[SlabAnnotation]:
    labels: list[tuple[Any, str, tuple[float, float]]] = []
    thicknesses: list[tuple[Any, float, str, tuple[float, float]]] = []
    for entity in document.modelspace():
        if entity.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        if normalize(entity.dxf.layer) != "DOSEME ADI":
            continue
        point = _text_point(entity)
        if not view.contains_raw_x(point[0]):
            continue
        value = normalize(_text(entity)).replace(" ", "")
        if SLAB_LABEL.fullmatch(value):
            labels.append((entity, value, point))
            continue
        match = SLAB_THICKNESS.fullmatch(value)
        if match is None:
            continue
        thickness_m = float(match.group("value").replace(",", ".")) / 100.0
        if 0.05 <= thickness_m <= 1.0:
            thicknesses.append((entity, thickness_m, _text(entity), point))

    result: list[SlabAnnotation] = []
    max_distance = 0.75 / scale
    for entity, label, point in labels:
        nearest = sorted(
            (
                (math.dist(point, thickness_point), thickness, text)
                for _, thickness, text, thickness_point in thicknesses
            ),
            key=lambda item: item[0],
        )
        thickness = None
        thickness_text = ""
        if nearest and nearest[0][0] <= max_distance:
            _, thickness, thickness_text = nearest[0]
        result.append(
            SlabAnnotation(
                entity=entity,
                handle=str(entity.dxf.handle),
                label=label,
                point=point,
                thickness_m=thickness,
                thickness_text=thickness_text,
            )
        )
    return result


def _slab_rectangle(
    annotation: SlabAnnotation,
    lines: list[AxisLine],
    scale: float,
) -> tuple[tuple[float, float, float, float], list[AxisLine]] | None:
    x, y = annotation.point
    tolerance = 0.02 / scale
    vertical = [
        line
        for line in lines
        if line.orientation == "vertical" and line.start - tolerance <= y <= line.end + tolerance
    ]
    horizontal = [
        line
        for line in lines
        if line.orientation == "horizontal" and line.start - tolerance <= x <= line.end + tolerance
    ]
    left = max(
        (line for line in vertical if line.fixed < x - tolerance),
        key=lambda item: item.fixed,
        default=None,
    )
    right = min(
        (line for line in vertical if line.fixed > x + tolerance),
        key=lambda item: item.fixed,
        default=None,
    )
    bottom = max(
        (line for line in horizontal if line.fixed < y - tolerance),
        key=lambda item: item.fixed,
        default=None,
    )
    top = min(
        (line for line in horizontal if line.fixed > y + tolerance),
        key=lambda item: item.fixed,
        default=None,
    )
    if any(item is None for item in (left, right, bottom, top)):
        return None
    assert left is not None and right is not None and bottom is not None and top is not None
    raw_box = (left.fixed, bottom.fixed, right.fixed, top.fixed)
    width_m = (right.fixed - left.fixed) * scale
    height_m = (top.fixed - bottom.fixed) * scale
    if not (0.2 <= width_m <= 40 and 0.2 <= height_m <= 40):
        return None
    return raw_box, [left, right, bottom, top]


def _opening_geometries(
    document,
    view: StructuralPlanView,
    scale: float,
) -> list[ClosedGeometry]:
    candidates: list[ClosedGeometry] = []
    for entity in document.modelspace():
        layer = normalize(entity.dxf.layer)
        if "YAZI" in layer or "OLCU" in layer:
            continue
        if not any(token in layer for token in OPENING_LAYER_TOKENS):
            continue
        geometry = _closed_geometry(entity, scale)
        if geometry is None:
            continue
        center_x_raw = ((geometry.bbox[0] + geometry.bbox[2]) / 2) / scale
        if not view.contains_raw_x(center_x_raw):
            continue
        width = geometry.bbox[2] - geometry.bbox[0]
        height = geometry.bbox[3] - geometry.bbox[1]
        if not (0.02 <= geometry.area_m2 <= 50 and width <= 15 and height <= 15):
            continue
        candidates.append(geometry)

    # Some sheets contain coincident copies on annotation/detail layers. Keep only
    # one physical opening when their extents substantially coincide.
    selected: list[ClosedGeometry] = []
    for candidate in sorted(candidates, key=lambda item: (item.bbox, item.handle)):
        if any(_boxes_overlap_ratio(candidate.bbox, item.bbox) >= 0.98 for item in selected):
            continue
        selected.append(candidate)
    return selected


def _slab_elements(
    source: SourceFile,
    view: StructuralPlanView,
    annotations: list[SlabAnnotation],
    lines: list[AxisLine],
    openings: list[ClosedGeometry],
    scale: float,
) -> list[DetectedElement]:
    elements: list[DetectedElement] = []
    seen_boxes: set[tuple[float, float, float, float]] = set()
    for annotation in annotations:
        rectangle = _slab_rectangle(annotation, lines, scale)
        if rectangle is None:
            continue
        raw_box, boundaries = rectangle
        fingerprint = (
            round(raw_box[0], 3),
            round(raw_box[1], 3),
            round(raw_box[2], 3),
            round(raw_box[3], 3),
        )
        if fingerprint in seen_boxes:
            continue
        seen_boxes.add(fingerprint)
        scaled = _scaled_box(raw_box, scale)
        width_m = scaled[2] - scaled[0]
        height_m = scaled[3] - scaled[1]
        gross_area = round(width_m * height_m, 6)
        contained_openings = [
            opening for opening in openings if _contains_box(scaled, opening.bbox)
        ]
        void_area = round(sum(opening.area_m2 for opening in contained_openings), 6)
        if void_area >= gross_area * 0.9:
            contained_openings = []
            void_area = 0.0
        measurements = {
            "area_m2": round(gross_area - void_area, 6),
            "gross_area_m2": gross_area,
            "void_area_m2": void_area,
            "void_count": float(len(contained_openings)),
            "perimeter_m": round(2 * (width_m + height_m), 6),
            "void_perimeter_m": round(
                sum(opening.perimeter_m for opening in contained_openings), 6
            ),
        }
        issues: list[str] = []
        if annotation.thickness_m is None:
            issues.append("missing:thickness_m")
        else:
            measurements["thickness_m"] = annotation.thickness_m
        elements.append(
            DetectedElement(
                id=_identity(source, view.floor, "slab", [annotation.handle]),
                source_id=source.id,
                discipline=source.discipline,
                element_type="slab",
                floor=view.floor,
                layer=str(annotation.entity.dxf.layer),
                source_handle=annotation.handle,
                geometry=Geometry(
                    kind="label_bounded_orthogonal_panel",
                    points=[
                        (scaled[0], scaled[1]),
                        (scaled[2], scaled[1]),
                        (scaled[2], scaled[3]),
                        (scaled[0], scaled[3]),
                        (scaled[0], scaled[1]),
                    ],
                    bbox=scaled,
                ),
                measurements=measurements,
                properties={
                    "quantity_kind": "slab",
                    "element_label": annotation.label,
                    "plan_view_id": view.id,
                    "plan_title": view.title,
                    "view_kind": view.kind,
                    "elevation_m": view.elevation_m,
                    "slab_evidence": {
                        "label": annotation.label,
                        "label_handle": annotation.handle,
                        "thickness_text": annotation.thickness_text,
                        "boundary_handles": [line.handle for line in boundaries],
                        "boundary_layers": [str(line.entity.dxf.layer) for line in boundaries],
                        "method": "label_point_cardinal_rays_to_drawn_beam_faces",
                        "opening_policy": "explicit_opening_geometry_required",
                        "void_count": len(contained_openings),
                        "void_area_m2": void_area,
                        "opening_handles": [opening.handle for opening in contained_openings],
                        "opening_layers": [opening.layer for opening in contained_openings],
                    },
                },
                required_inputs=["area_m2", "thickness_m"],
                confidence=0.94 if not issues else 0.7,
                review_status=ReviewStatus.PENDING if not issues else ReviewStatus.NEEDS_REVIEW,
                issues=issues,
            )
        )
    return elements


def _foundation_shape_signature(geometry: ClosedGeometry) -> tuple[tuple[float, float], ...]:
    min_x = min(point[0] for point in geometry.points)
    min_y = min(point[1] for point in geometry.points)
    return tuple(
        sorted((round(x - min_x, 3), round(y - min_y, 3)) for x, y in geometry.points)
    )


def _foundation_elements(
    document,
    source: SourceFile,
    view: StructuralPlanView,
    scale: float,
) -> list[DetectedElement]:
    thickness_notes: list[tuple[str, str, tuple[float, float], float]] = []
    for entity in document.modelspace():
        if entity.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        raw_point = _text_point(entity)
        if not view.contains_raw_x(raw_point[0]):
            continue
        value = _text(entity)
        text_key = normalize(value).replace(" ", "")
        if "RADYETEMEL" not in text_key and not text_key.startswith("H="):
            continue
        match = FOUNDATION_THICKNESS.search(normalize(value))
        if match is None:
            continue
        thickness = float(match.group("value").replace(",", ".")) / 100.0
        if 0.1 <= thickness <= 3.0:
            thickness_notes.append(
                (
                    str(entity.dxf.handle),
                    value,
                    (raw_point[0] * scale, raw_point[1] * scale),
                    round(thickness, 6),
                )
            )

    candidates: list[tuple[ClosedGeometry, float, list[tuple[str, str]]]] = []
    for entity in document.modelspace():
        geometry = _closed_geometry(entity, scale)
        if geometry is None:
            continue
        center_x_raw = ((geometry.bbox[0] + geometry.bbox[2]) / 2) / scale
        if not view.contains_raw_x(center_x_raw):
            continue
        width = geometry.bbox[2] - geometry.bbox[0]
        height = geometry.bbox[3] - geometry.bbox[1]
        bbox_area = width * height
        if not (
            50 <= geometry.area_m2 <= 20000
            and 5 <= width <= 250
            and 5 <= height <= 250
            and bbox_area > 0
            and geometry.area_m2 / bbox_area >= 0.35
        ):
            continue
        inside_notes = [
            (handle, text, thickness)
            for handle, text, point, thickness in thickness_notes
            if (
                geometry.bbox[0] <= point[0] <= geometry.bbox[2]
                and geometry.bbox[1] <= point[1] <= geometry.bbox[3]
            )
        ]
        if not inside_notes:
            continue
        thickness_values = {note[2] for note in inside_notes}
        if len(thickness_values) != 1:
            continue
        thickness = next(iter(thickness_values))
        evidence = [(handle, text) for handle, text, _ in inside_notes]
        candidates.append((geometry, thickness, evidence))

    grouped: dict[
        tuple[tuple[tuple[float, float], ...], float, float, float],
        list[tuple[ClosedGeometry, list[tuple[str, str]]]],
    ] = defaultdict(list)
    for geometry, thickness, evidence in candidates:
        group_key = (
            _foundation_shape_signature(geometry),
            round(geometry.area_m2, 3),
            round(geometry.perimeter_m, 3),
            thickness,
        )
        grouped[group_key].append((geometry, evidence))

    elements: list[DetectedElement] = []
    for group_key, copies in grouped.items():
        _, _, _, thickness = group_key
        representative, _ = min(
            copies,
            key=lambda item: math.dist(
                (
                    (item[0].bbox[0] + item[0].bbox[2]) / 2,
                    (item[0].bbox[1] + item[0].bbox[3]) / 2,
                ),
                (view.origin[0] * scale, view.origin[1] * scale),
            ),
        )
        handles = sorted(geometry.handle for geometry, _ in copies)
        note_rows = sorted(
            {(handle, text) for _, evidence in copies for handle, text in evidence}
        )
        copy_count = len(copies)
        issues = ["review:translated_foundation_views_deduplicated"] if copy_count > 1 else []
        elements.append(
            DetectedElement(
                id=_identity(source, view.floor, "raft", handles),
                source_id=source.id,
                discipline=source.discipline,
                element_type="raft",
                floor=view.floor,
                layer=representative.layer,
                source_handle="+".join(handles),
                geometry=Geometry(
                    kind="explicit_closed_raft_boundary",
                    points=list(representative.points) + [representative.points[0]],
                    bbox=representative.bbox,
                ),
                measurements={
                    "area_m2": representative.area_m2,
                    "gross_area_m2": representative.area_m2,
                    "void_area_m2": 0.0,
                    "void_count": 0.0,
                    "perimeter_m": representative.perimeter_m,
                    "thickness_m": thickness,
                },
                properties={
                    "quantity_kind": "raft",
                    "plan_view_id": view.id,
                    "plan_title": view.title,
                    "view_kind": view.kind,
                    "elevation_m": view.elevation_m,
                    "foundation_evidence": {
                        "method": "closed_boundary_with_contained_explicit_thickness_notes",
                        "boundary_handles": handles,
                        "translated_copy_count": copy_count,
                        "translated_copy_bboxes": [geometry.bbox for geometry, _ in copies],
                        "thickness_note_handles": [handle for handle, _ in note_rows],
                        "thickness_texts": [text for _, text in note_rows],
                        "opening_policy": "explicit_closed_opening_geometry_required",
                    },
                },
                required_inputs=["area_m2", "thickness_m", "perimeter_m"],
                confidence=0.88 if copy_count > 1 else 0.96,
                review_status=(
                    ReviewStatus.NEEDS_REVIEW if copy_count > 1 else ReviewStatus.PENDING
                ),
                issues=issues,
            )
        )
    return elements


def _stair_plan_elements(
    document,
    source: SourceFile,
    scale: float,
) -> tuple[list[DetectedElement], int]:
    scopes: list[tuple[Any, str, tuple[float, float]]] = []
    annotations: list[tuple[Any, re.Match[str], str, tuple[float, float]]] = []
    stair_geometries: list[ClosedGeometry] = []
    thickness_notes: list[tuple[Any, float, tuple[float, float], str]] = []
    for entity in document.modelspace():
        layer_key = normalize(str(entity.dxf.layer))
        if entity.dxftype() == "LWPOLYLINE" and "MERDIVEN" in layer_key:
            geometry = _closed_geometry(entity, scale)
            if geometry is not None and 0.5 <= geometry.area_m2 <= 100:
                stair_geometries.append(geometry)
        if entity.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        value = _text(entity)
        key = normalize(value)
        point = _text_point(entity)
        if "KOTLARI ARASI MERDIVEN" in key:
            scopes.append((entity, value, point))
        if "MERDIVEN" not in normalize(entity.dxf.layer):
            continue
        match = STAIR_LABEL.search(key)
        if match is not None:
            annotations.append((entity, match, value, point))
        thickness_match = STAIR_THICKNESS.search(key)
        if thickness_match is not None and "MERDIVEN" in layer_key:
            thickness_notes.append(
                (
                    entity,
                    float(thickness_match.group("value").replace(",", ".")) / 100.0,
                    point,
                    value,
                )
            )

    elements: list[DetectedElement] = []
    unresolved_typical = 0
    max_scope_distance = 15.0 / scale
    for entity, match, value, point in annotations:
        nearby_scopes = sorted(
            (
                (math.dist(point, scope_point), scope_entity, scope_text)
                for scope_entity, scope_text, scope_point in scopes
                if abs(point[0] - scope_point[0]) <= 4.0 / scale
            ),
            key=lambda item: item[0],
        )
        if not nearby_scopes or nearby_scopes[0][0] > max_scope_distance:
            continue
        _, scope_entity, scope_text = nearby_scopes[0]
        elevations = [
            float(item.group("value").replace(" ", "").replace(",", "."))
            for item in ELEVATION.finditer(normalize(scope_text))
        ]
        label = match.group("label").upper()
        step_count = int(match.group("count"))
        tread_m = float(match.group("tread").replace(",", ".")) / 100.0
        riser_m = float(match.group("riser").replace(",", ".")) / 100.0
        declared_rise = round(step_count * riser_m, 6)
        issues: list[str] = []
        floor = "TIP MERDIVEN · KAT TEKRARI TANIMSIZ"
        total_rise = declared_rise
        lower_level = None
        upper_level = None
        if len(elevations) >= 2:
            lower_level, upper_level = elevations[0], elevations[1]
            total_rise = round(abs(upper_level - lower_level), 6)
            floor = f"{lower_level:+.2f} → {upper_level:+.2f} Merdiveni"
            if abs(total_rise - declared_rise) > 0.03:
                issues.append("blocking:stair_rise_evidence_conflict")
        else:
            issues.append("blocking:stair_floor_repeat_required")
            unresolved_typical += 1

        annotation_handle = str(entity.dxf.handle)
        scope_handle = str(scope_entity.dxf.handle)
        point_m = (round(point[0] * scale, 6), round(point[1] * scale, 6))
        geometry_candidates = sorted(
            (
                (
                    math.dist(
                        point_m,
                        (
                            (geometry.bbox[0] + geometry.bbox[2]) / 2,
                            (geometry.bbox[1] + geometry.bbox[3]) / 2,
                        ),
                    ),
                    geometry,
                )
                for geometry in stair_geometries
            ),
            key=lambda item: item[0],
        )
        matched_geometry = (
            geometry_candidates[0][1]
            if geometry_candidates and geometry_candidates[0][0] <= 12.0
            else None
        )
        nearby_thickness = sorted(
            (
                (math.dist(point, note_point) * scale, note_entity, thickness, note_text)
                for note_entity, thickness, note_point, note_text in thickness_notes
            ),
            key=lambda item: item[0],
        )
        thickness_note = (
            nearby_thickness[0]
            if nearby_thickness and nearby_thickness[0][0] <= 12.0
            else None
        )
        measurements: dict[str, float] = {
            "step_count": float(step_count),
            "tread_m": round(tread_m, 6),
            "riser_m": round(riser_m, 6),
            "total_rise_m": total_rise,
        }
        geometry_handles: list[str] = []
        element_geometry = Geometry(
            kind="stair_plan_annotation",
            points=[point_m],
            bbox=(
                point_m[0] - 0.1,
                point_m[1] - 0.1,
                point_m[0] + 0.1,
                point_m[1] + 0.1,
            ),
        )
        stair_width = None
        if matched_geometry is not None:
            geometry_handles.append(matched_geometry.handle)
            spans = sorted(
                (
                    matched_geometry.bbox[2] - matched_geometry.bbox[0],
                    matched_geometry.bbox[3] - matched_geometry.bbox[1],
                )
            )
            stair_width = spans[0]
            measurements.update(
                {
                    "plan_area_m2": matched_geometry.area_m2,
                    "horizontal_run_m": spans[1],
                    "stair_width_m": stair_width,
                }
            )
            element_geometry = Geometry(
                kind="explicit_closed_stair_boundary",
                points=list(matched_geometry.points) + [matched_geometry.points[0]],
                bbox=matched_geometry.bbox,
            )
        else:
            issues.extend(["missing:plan_area_m2", "missing:horizontal_run_m"])
        thickness_handle = ""
        thickness_text = ""
        if thickness_note is not None:
            _, note_entity, waist_thickness, thickness_text = thickness_note
            thickness_handle = str(note_entity.dxf.handle)
            measurements["waist_thickness_m"] = round(waist_thickness, 6)
            if stair_width is not None:
                inclined_length = math.hypot(measurements["horizontal_run_m"], total_rise)
                measurements.update(
                    {
                        "step_volume_m3": round(
                            0.5 * stair_width * tread_m * riser_m * step_count, 6
                        ),
                        "riser_formwork_m2": round(stair_width * riser_m * step_count, 6),
                        "side_formwork_m2": round(
                            2 * inclined_length * waist_thickness, 6
                        ),
                    }
                )
        else:
            issues.append("missing:waist_thickness_m")
        identity_handles = [annotation_handle, scope_handle, *geometry_handles]
        if thickness_handle:
            identity_handles.append(thickness_handle)
        elements.append(
            DetectedElement(
                id=_identity(
                    source,
                    floor,
                    "stair",
                    identity_handles,
                ),
                source_id=source.id,
                discipline=source.discipline,
                element_type="stair",
                floor=floor,
                layer=str(entity.dxf.layer),
                source_handle="+".join(identity_handles),
                geometry=element_geometry,
                measurements=measurements,
                properties={
                    "quantity_kind": "stair",
                    "element_label": label,
                    "view_kind": "stair_plan",
                    "plan_title": scope_text,
                    "calculation_policy": (
                        "inclined_waist_slab_requires_explicit_plan_area_run_and_thickness"
                    ),
                    "stair_evidence": {
                        "label": label,
                        "annotation_handle": annotation_handle,
                        "annotation_text": value,
                        "scope_handle": scope_handle,
                        "scope_text": scope_text,
                        "step_count": step_count,
                        "tread_m": round(tread_m, 6),
                        "riser_m": round(riser_m, 6),
                        "declared_step_rise_m": declared_rise,
                        "lower_level_m": lower_level,
                        "upper_level_m": upper_level,
                        "repeat_definition_required": len(elevations) < 2,
                        "boundary_handle": matched_geometry.handle if matched_geometry else "",
                        "boundary_area_m2": (
                            matched_geometry.area_m2 if matched_geometry else None
                        ),
                        "thickness_note_handle": thickness_handle,
                        "thickness_text": thickness_text,
                        "step_volume_policy": (
                            "0.5 * stair_width * tread * riser * step_count"
                            if "step_volume_m3" in measurements
                            else "not_calculated_without_boundary_and_thickness"
                        ),
                    },
                },
                required_inputs=[
                    "plan_area_m2",
                    "horizontal_run_m",
                    "total_rise_m",
                    "waist_thickness_m",
                ],
                confidence=0.82 if len(elevations) >= 2 else 0.68,
                review_status=ReviewStatus.NEEDS_REVIEW,
                issues=issues,
            )
        )
    return elements, unresolved_typical


def _has_parallel_beam_beyond(
    beam: DetectedElement,
    missing_coordinate: float,
    present_coordinate: float,
    beams: list[DetectedElement],
) -> bool:
    evidence = beam.properties.get("beam_face_evidence")
    box = beam.geometry.bbox
    if not isinstance(evidence, dict) or box is None:
        return True
    orientation = evidence.get("orientation")
    if orientation not in {"horizontal", "vertical"}:
        return True
    negative_side = missing_coordinate < present_coordinate
    view_id = beam.properties.get("plan_view_id")
    for other in beams:
        if other.id == beam.id or other.properties.get("plan_view_id") != view_id:
            continue
        other_evidence = other.properties.get("beam_face_evidence")
        other_box = other.geometry.bbox
        if not isinstance(other_evidence, dict) or other_box is None:
            continue
        if other_evidence.get("orientation") != orientation:
            continue
        if orientation == "horizontal":
            overlap = min(box[2], other_box[2]) - max(box[0], other_box[0])
            beyond = (
                other_box[3] < missing_coordinate - 0.02
                if negative_side
                else other_box[1] > missing_coordinate + 0.02
            )
        else:
            overlap = min(box[3], other_box[3]) - max(box[1], other_box[1])
            beyond = (
                other_box[2] < missing_coordinate - 0.02
                if negative_side
                else other_box[0] > missing_coordinate + 0.02
            )
        if overlap >= 0.5 and beyond:
            return True
    return False


def _reconcile_beam_formwork(beams: list[DetectedElement], slabs: list[DetectedElement]) -> int:
    thicknesses_by_boundary: dict[str, list[float]] = defaultdict(list)
    for slab in slabs:
        thickness = slab.measurements.get("thickness_m")
        evidence = slab.properties.get("slab_evidence")
        if thickness is None or not isinstance(evidence, dict):
            continue
        handles = evidence.get("boundary_handles", [])
        if not isinstance(handles, list):
            continue
        for handle in handles:
            thicknesses_by_boundary[str(handle)].append(thickness)

    reconciled = 0
    for beam in beams:
        if "formwork_area_m2" not in beam.required_inputs:
            beam.required_inputs.append("formwork_area_m2")
        handles = beam.properties.get("source_handles", [])
        if not isinstance(handles, list) or len(handles) != 2:
            continue
        face_evidence = beam.properties.get("beam_face_evidence")
        side_faces = face_evidence.get("side_faces", []) if isinstance(face_evidence, dict) else []
        coordinates: dict[str, float] = {}
        for item in side_faces:
            if not isinstance(item, dict):
                continue
            handle = item.get("handle")
            coordinate = item.get("coordinate_m")
            if handle is None or not isinstance(coordinate, int | float):
                continue
            coordinates[str(handle)] = float(coordinate)
        adjacent_by_handle = {
            str(handle): max(thicknesses_by_boundary[str(handle)])
            for handle in handles
            if str(handle) in thicknesses_by_boundary
        }
        length = beam.measurements["length_m"]
        width = beam.measurements["width_m"]
        height = beam.measurements["height_m"]
        exposed: list[float]
        policy: str
        side_conditions: list[str]
        if len(adjacent_by_handle) == 2:
            adjacent = [adjacent_by_handle[str(handle)] for handle in handles]
            exposed = [round(max(height - thickness, 0.0), 6) for thickness in adjacent]
            policy = "soffit_plus_two_sides_with_explicit_adjacent_slab_deduction"
            side_conditions = ["adjacent_slab", "adjacent_slab"]
        elif len(adjacent_by_handle) == 1 and len(coordinates) == 2:
            present_handle = next(iter(adjacent_by_handle))
            missing_handle = next(
                str(handle) for handle in handles if str(handle) != present_handle
            )
            if _has_parallel_beam_beyond(
                beam,
                coordinates[missing_handle],
                coordinates[present_handle],
                beams,
            ):
                adjacent = []
                exposed = []
                policy = ""
                side_conditions = []
            else:
                slab_thickness = adjacent_by_handle[present_handle]
                adjacent = [slab_thickness]
                exposed = [round(max(height - slab_thickness, 0.0), 6), height]
                policy = "soffit_plus_slab_side_deduction_plus_proven_exterior_side"
                side_conditions = ["adjacent_slab", "exterior_envelope"]
        else:
            adjacent = []
            exposed = []
            policy = ""
            side_conditions = []

        if not policy:
            beam.issues.append("missing:formwork_area_m2")
            beam.review_status = ReviewStatus.NEEDS_REVIEW
            beam.confidence = min(beam.confidence, 0.75)
            continue
        beam.measurements["formwork_area_m2"] = round((width + sum(exposed)) * length, 6)
        beam.properties["formwork_evidence"] = {
            "policy": policy,
            "side_handles": handles,
            "adjacent_slab_thicknesses_m": adjacent,
            "exposed_side_depths_m": exposed,
            "side_conditions": side_conditions,
        }
        reconciled += 1
    return reconciled


def _unit_score(document, views: list[StructuralPlanView], unit: DrawingUnit) -> int:
    scale = unit_scale(unit)
    score = 0
    for view in views[:4]:
        lines = [
            line
            for entity in document.modelspace()
            if (line := _axis_line(entity, view, scale)) is not None
        ]
        pairs = _beam_pairs(lines, scale)
        for annotation in _beam_annotations(document, view):
            if any(_pair_score(pair, annotation, scale) is not None for pair in pairs):
                score += 1
    return score


def _labeled_signature(element: DetectedElement) -> tuple[float, ...]:
    keys: tuple[str, ...]
    if element.element_type == "beam":
        keys = ("length_m", "width_m", "height_m")
    else:
        keys = ("area_m2", "thickness_m")
    return tuple(round(element.measurements.get(key, -1.0), 3) for key in keys)


def _deduplicate_labeled_elements(
    elements: list[DetectedElement],
) -> tuple[list[DetectedElement], int, int]:
    selected: list[DetectedElement] = []
    seen: dict[tuple[str, str, str], DetectedElement] = {}
    skipped = 0
    conflicts: set[tuple[str, str, str]] = set()
    for element in elements:
        label = str(element.properties.get("element_label", "")).strip().upper()
        if element.element_type not in {"beam", "slab"} or not label:
            selected.append(element)
            continue
        key = (element.floor, element.element_type, label)
        previous = seen.get(key)
        if previous is None:
            seen[key] = element
            selected.append(element)
            continue
        if _labeled_signature(previous) == _labeled_signature(element):
            skipped += 1
            continue
        conflicts.add(key)
        for candidate in (previous, element):
            if "blocking:duplicate_label_conflict" not in candidate.issues:
                candidate.issues.append("blocking:duplicate_label_conflict")
            candidate.review_status = ReviewStatus.NEEDS_REVIEW
            candidate.confidence = min(candidate.confidence, 0.6)
        selected.append(element)
    return selected, skipped, len(conflicts)


def extract_multiview_structural_plans(
    document,
    source: SourceFile,
    chosen_unit: DrawingUnit,
) -> MultiviewStructuralResult:
    views = discover_structural_plan_views(document)
    formwork_views = [view for view in views if view.kind in {"formwork", "foundation"}]
    if len(formwork_views) < 2 or chosen_unit == DrawingUnit.UNKNOWN:
        return MultiviewStructuralResult([], [], views, False)

    scores = {
        unit: _unit_score(document, formwork_views, unit)
        for unit in (DrawingUnit.MM, DrawingUnit.CM, DrawingUnit.M)
    }
    suggested_unit, suggested_score = max(scores.items(), key=lambda item: item[1])
    if suggested_score >= 5 and suggested_unit != chosen_unit:
        warning = AnalysisWarning(
            code="UNIT_MISMATCH_SUSPECTED",
            message=(
                f"DXF birimi {chosen_unit.value} olarak okunuyor; ancak çizilmiş kiriş "
                f"kenar aralıkları ve kesit etiketleri {suggested_score} eşleşmeyle "
                f"{suggested_unit.value} birimini gösteriyor. Birimi kullanıcı olarak "
                "doğrulamadan bu çoklu paftadan miktar üretilmedi."
            ),
            source_id=source.id,
            severity="error",
        )
        return MultiviewStructuralResult([], [warning], views, True, blocked=True)
    scale = unit_scale(chosen_unit)

    elements: list[DetectedElement] = []
    for view in formwork_views:
        lines = [
            line
            for entity in document.modelspace()
            if (line := _axis_line(entity, view, scale)) is not None
        ]
        pairs = _beam_pairs(lines, scale)
        annotations = _beam_annotations(document, view)
        beams = _beam_elements(source, view, pairs, annotations, scale)
        slab_annotations = _slab_annotations(document, view, scale)
        openings = _opening_geometries(document, view, scale)
        slabs = _slab_elements(source, view, slab_annotations, lines, openings, scale)
        _reconcile_beam_formwork(beams, slabs)
        elements.extend(beams)
        elements.extend(slabs)
        if view.kind == "foundation":
            elements.extend(_foundation_elements(document, source, view, scale))

    stair_elements, unresolved_typical_stairs = _stair_plan_elements(document, source, scale)
    elements.extend(stair_elements)

    elements, duplicate_count, conflict_count = _deduplicate_labeled_elements(elements)
    if not elements:
        return MultiviewStructuralResult([], [], views, False)
    floor_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for element in elements:
        floor_counts[element.floor][element.element_type] += 1
        if element.element_type == "beam" and "formwork_area_m2" in element.measurements:
            floor_counts[element.floor]["reconciled_formwork"] += 1
    floor_summaries = [
        (
            f"{floor}: {counts['beam']} kiriş, {counts['slab']} döşeme, "
            f"{counts['raft']} radye, {counts['stair']} merdiven, "
            f"{counts['reconciled_formwork']} kirişte "
            "döşeme/dış cephe kanıtlı kalıp"
        )
        for floor, counts in sorted(floor_counts.items())
    ]
    warnings = [
        AnalysisWarning(
            code="MULTIVIEW_STRUCTURAL_PLANS_PARSED",
            message=(
                f"{len(views)} ana statik pafta bölgesi ve {len(formwork_views)} kalıp/temel "
                "görünümü kotlarına göre ayrıştırıldı. " + "; ".join(floor_summaries)
            ),
            source_id=source.id,
            severity="info",
        ),
        AnalysisWarning(
            code="MULTIVIEW_ENGINEER_REVIEW_REQUIRED",
            message=(
                "Kirişler çizilmiş çift kenar + kesit etiketiyle, döşemeler etiket noktası + "
                "çevreleyen gerçek kiriş yüzleriyle üretildi. Boşluklar yalnız kapalı ve panel "
                "içinde kalan açık boşluk geometrisinden düşüldü; bütün adaylar mühendis "
                "onayı bekler."
            ),
            source_id=source.id,
        ),
    ]
    if stair_elements:
        warnings.append(
            AnalysisWarning(
                code="STAIR_PLAN_ANNOTATIONS_LINKED",
                message=(
                    f"{len(stair_elements)} merdiven adayı açık merdiven etiketi, basamak/rıht "
                    "ölçüsü ve en yakın kot-aralığı başlığıyla bağlandı. Plan alanı, yatay koşu "
                    "ve plak kalınlığı okunmadan merdiven miktarı üretilmeyecek."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    if unresolved_typical_stairs:
        warnings.append(
            AnalysisWarning(
                code="TYPICAL_STAIR_REPEAT_REQUIRED",
                message=(
                    f"{unresolved_typical_stairs} tip merdiven etiketi açık kat aralığı "
                    "taşımıyor. Kullanıcı kat tekrarlarını tanımlayana kadar bu adaylar kesin "
                    "metraja kapalıdır."
                ),
                source_id=source.id,
                severity="warning",
            )
        )
    if duplicate_count:
        warnings.append(
            AnalysisWarning(
                code="DUPLICATE_PLAN_ELEMENTS_SKIPPED",
                message=(
                    f"Aynı kat, eleman etiketi ve ölçüleri taşıyan {duplicate_count} "
                    "çevrilmiş/kopyalanmış plan elemanı miktarlara yeniden eklenmedi."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    if conflict_count:
        warnings.append(
            AnalysisWarning(
                code="DUPLICATE_ELEMENT_LABEL_CONFLICT",
                message=(
                    f"{conflict_count} kat/eleman etiketinde farklı ölçüler bulundu; "
                    "bu adaylar engelleyici inceleme durumuna alındı."
                ),
                source_id=source.id,
                severity="error",
            )
        )
    return MultiviewStructuralResult(elements, warnings, views, True)


def _view_for_element(
    element: DetectedElement,
    views: list[StructuralPlanView],
    scale: float,
) -> StructuralPlanView | None:
    box = element.geometry.bbox
    if box is None:
        return None
    raw_center_x = ((box[0] + box[2]) / 2) / scale
    return next((view for view in views if view.contains_raw_x(raw_center_x)), None)


def _previous_elevation(view: StructuralPlanView, views: list[StructuralPlanView]) -> float | None:
    elevations = sorted(
        {
            candidate.elevation_m
            for candidate in views
            if candidate.kind in {"formwork", "foundation"}
            and candidate.elevation_m is not None
            and view.elevation_m is not None
            and candidate.elevation_m < view.elevation_m
        }
    )
    return elevations[-1] if elevations else None


def filter_multiview_generic_elements(
    elements: list[DetectedElement],
    views: list[StructuralPlanView],
    source: SourceFile,
    scale: float,
) -> tuple[list[DetectedElement], list[AnalysisWarning]]:
    application_floors = {view.floor for view in views if view.kind == "column_application"}
    selected: list[DetectedElement] = []
    discarded = 0
    seen: set[tuple[str, str, tuple[float, float, float, float]]] = set()
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for element in elements:
        view = _view_for_element(element, views, scale)
        if view is None:
            discarded += 1
            continue
        allowed = False
        if element.element_type == "column":
            allowed = view.kind == "column_application" or (
                view.kind == "formwork" and view.floor not in application_floors
            )
        elif element.element_type == "shear_wall":
            allowed = view.kind in {"formwork", "foundation"}
        elif element.element_type == "stair":
            layer = normalize(element.layer)
            allowed = view.kind in {"formwork", "foundation"} and not any(
                token in layer for token in ("HATIL", "YAZI", "OLCU")
            )
        elif element.element_type in {"raft", "foundation"}:
            allowed = view.kind == "foundation"
        elif element.element_type == "rebar":
            allowed = view.kind == "rebar"
        if not allowed:
            discarded += 1
            continue
        box = element.geometry.bbox
        assert box is not None
        relative_box = (
            round(box[0] - view.origin[0] * scale, 4),
            round(box[1] - view.origin[1] * scale, 4),
            round(box[2] - view.origin[0] * scale, 4),
            round(box[3] - view.origin[1] * scale, 4),
        )
        fingerprint = (
            view.id,
            element.element_type,
            relative_box,
        )
        if fingerprint in seen:
            discarded += 1
            continue
        seen.add(fingerprint)
        element.floor = view.floor
        element.properties.update(
            {
                "plan_view_id": view.id,
                "plan_title": view.title,
                "view_kind": view.kind,
                "elevation_m": view.elevation_m,
            }
        )
        if element.element_type in {"column", "shear_wall"} and view.elevation_m is not None:
            lower = _previous_elevation(view, views)
            if lower is not None:
                height = round(view.elevation_m - lower, 6)
                if 0.3 <= height <= 10:
                    element.measurements["height_m"] = height
                    element.issues = [
                        issue for issue in element.issues if issue != "missing:height_m"
                    ]
                    element.properties["level_height_evidence"] = {
                        "lower_level_m": lower,
                        "upper_level_m": view.elevation_m,
                        "method": "difference_between_explicit_formwork_plan_elevations",
                    }
        counts[view.floor][element.element_type] += 1
        selected.append(element)

    summary = "; ".join(
        f"{floor}: " + ", ".join(f"{kind}={count}" for kind, count in sorted(kinds.items()))
        for floor, kinds in sorted(counts.items())
    )
    warning = AnalysisWarning(
        code="MULTIVIEW_SOURCE_OWNERSHIP_APPLIED",
        message=(
            "Kolonlar kolon aplikasyon, kiriş/döşeme/perdeler kalıp, donatı ise donatı "
            f"bölgelerine bağlandı; {discarded} detay veya yanlış-pafta adayı çıkarıldı. "
            f"{summary or 'Güvenli ek fiziksel aday bulunmadı.'}"
        ),
        source_id=source.id,
        severity="info",
    )
    return selected, [warning]
