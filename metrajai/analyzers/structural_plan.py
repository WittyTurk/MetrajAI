from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ezdxf import bbox
from ezdxf.math import Vec3
from ezdxf.math import area as polygon_area
from ezdxf.path import from_hatch
from ezdxf.path.nesting import make_polygon_structure

from ..contracts import (
    AnalysisWarning,
    DetectedElement,
    DrawingUnit,
    Geometry,
    ReviewStatus,
    SourceFile,
)
from ..units import unit_scale
from .rebar_table import extract_beam_rebar_table

PLAN_TITLE_TOKEN = "KALIP PLANI"
PREFERRED_PLAN_TOKEN = "DONATISIZ KALIP PLANI"
ELEMENT_LABEL = re.compile(r"^[A-ZÇĞİÖŞÜ]{1,4}\d{1,3}$", re.IGNORECASE)
ELEVATION = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")
BEAM_SECTION = re.compile(
    r"(?P<label>[A-Z]{1,4}\d{1,3})\s*"
    r"(?P<width>\d+(?:[.,]\d+)?)\s*[/X]\s*"
    r"(?P<height>\d+(?:[.,]\d+)?)"
)
SLAB_LABEL = re.compile(r"^[A-Z]{1,3}\d{1,3}$")
SLAB_THICKNESS = re.compile(r"^D\s*=\s*(?P<value>\d+(?:[.,]\d+)?)$")


def _normalize(value: str) -> str:
    normalized = (
        value.upper()
        .replace("İ", "I")
        .replace("Ş", "S")
        .replace("Ğ", "G")
        .replace("Ü", "U")
        .replace("Ö", "O")
        .replace("Ç", "C")
    )
    return " ".join(normalized.split())


def _layer(value: str) -> str:
    return _normalize(value).replace(" ", "")


def _text(entity) -> str:
    if entity.dxftype() == "TEXT":
        return str(entity.dxf.text).strip()
    if entity.dxftype() == "MTEXT":
        return str(entity.plain_text()).strip()
    return ""


def _insert_point(entity) -> tuple[float, float]:
    point = entity.dxf.insert
    return float(point.x), float(point.y)


def _raw_bbox(entity) -> tuple[float, float, float, float] | None:
    try:
        box = bbox.extents([entity], fast=True)
    except Exception:
        return None
    if not box.has_data:
        return None
    return float(box.extmin.x), float(box.extmin.y), float(box.extmax.x), float(box.extmax.y)


def _dimensions(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return abs(box[2] - box[0]), abs(box[3] - box[1])


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0


def _scaled_box(
    box: tuple[float, float, float, float], scale: float | None
) -> tuple[float, float, float, float]:
    factor = scale or 1.0
    return tuple(round(value * factor, 6) for value in box)  # type: ignore[return-value]


def _block_texts(document, entity) -> list[str]:
    try:
        block = document.blocks.get(entity.dxf.name)
    except Exception:
        return []
    return [value for child in block if (value := _text(child))]


@dataclass
class PlanCluster:
    root: tuple[float, float]
    title: str
    columns: list
    beams: list
    slabs: list
    slab_edges: list


@dataclass
class PhysicalColumn:
    entity: Any
    raw_box: tuple[float, float, float, float]
    label: str


@dataclass
class BeamAnnotation:
    label: str
    section_width_m: float
    section_height_m: float
    raw_box: tuple[float, float, float, float]
    orientation: str
    text: str
    handle: str
    plan_title: str
    translated_from_sibling: bool = False


@dataclass
class SlabAnnotation:
    label: str
    thickness_m: float | None
    thickness_text: str
    raw_box: tuple[float, float, float, float]
    block_name: str
    handle: str


@dataclass
class BoundarySegment:
    start: tuple[float, float]
    end: tuple[float, float]
    handle: str
    layer: str


@dataclass(frozen=True)
class SlabOpening:
    raw_box: tuple[float, float, float, float]
    raw_area: float
    handle: str
    layer: str


@dataclass
class StructuralPlanResult:
    elements: list[DetectedElement]
    warnings: list[AnalysisWarning]
    activated: bool


def _plan_titles(document) -> list[tuple[str, tuple[float, float]]]:
    values: list[tuple[str, tuple[float, float]]] = []
    for entity in document.modelspace():
        value = _text(entity)
        if PLAN_TITLE_TOKEN not in _normalize(value):
            continue
        values.append((value, _insert_point(entity)))
    return values


def _candidate_clusters(document) -> list[PlanCluster]:
    grouped: dict[tuple[float, float], dict[str, list]] = defaultdict(
        lambda: {"columns": [], "beams": [], "slabs": [], "slab_edges": []}
    )
    for entity in document.modelspace():
        if entity.dxftype() != "INSERT":
            continue
        normalized_layer = _layer(entity.dxf.layer)
        category = {
            "KOLON": "columns",
            "KIRIS": "beams",
            "DOSEME": "slabs",
            "STATIKDOSEMEKENARI": "slab_edges",
        }.get(normalized_layer)
        if category is None:
            continue
        point = _insert_point(entity)
        root = round(point[0], 3), round(point[1], 3)
        grouped[root][category].append(entity)

    titles = _plan_titles(document)
    clusters: list[PlanCluster] = []
    for root, entities in grouped.items():
        if len(entities["columns"]) < 5 or len(entities["beams"]) < 5:
            continue
        nearby = sorted(
            (math.dist(root, point), title)
            for title, point in titles
            if math.dist(root, point) < 2500
        )
        if not nearby:
            continue
        clusters.append(
            PlanCluster(
                root=root,
                title=nearby[0][1],
                columns=entities["columns"],
                beams=entities["beams"],
                slabs=entities["slabs"],
                slab_edges=entities["slab_edges"],
            )
        )
    return clusters


def _cluster_fingerprint(cluster: PlanCluster) -> tuple:
    rows: list[tuple] = []
    for category, entities in (
        ("column", cluster.columns),
        ("beam", cluster.beams),
        ("slab", cluster.slabs),
        ("slab_edge", cluster.slab_edges),
    ):
        for entity in entities:
            box = _raw_bbox(entity)
            if box is None:
                continue
            rows.append(
                (
                    category,
                    *(round(box[index] - cluster.root[index % 2], 2) for index in range(4)),
                )
            )
    return _normalize(cluster.title), tuple(sorted(rows))


def _select_clusters(clusters: list[PlanCluster]) -> tuple[list[PlanCluster], int]:
    preferred = [
        cluster for cluster in clusters if PREFERRED_PLAN_TOKEN in _normalize(cluster.title)
    ]
    candidates = preferred or clusters
    selected: list[PlanCluster] = []
    seen: set[tuple] = set()
    for cluster in sorted(candidates, key=lambda item: (-item.root[1], item.root[0])):
        fingerprint = _cluster_fingerprint(cluster)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        selected.append(cluster)
    return selected, len(clusters) - len(selected)


def _suggest_unit(clusters: list[PlanCluster]) -> DrawingUnit | None:
    boxes = [
        box
        for cluster in clusters
        for entity in cluster.columns
        if (box := _raw_bbox(entity)) is not None
    ]
    if not boxes:
        return None
    extent = (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )
    raw_span = max(_dimensions(extent))
    scores: list[tuple[int, DrawingUnit]] = []
    for unit in (DrawingUnit.MM, DrawingUnit.CM, DrawingUnit.M):
        factor = unit_scale(unit)
        physical_columns = 0
        for box in boxes:
            small, large = sorted(value * factor for value in _dimensions(box))
            if 0.2 <= small <= 1.2 and small <= large <= 2.0 and large / small <= 4:
                physical_columns += 1
        building_span = raw_span * factor
        span_bonus = 20 if 5 <= building_span <= 100 else 0
        scores.append((physical_columns + span_bonus, unit))
    score, unit = max(scores, key=lambda item: item[0])
    return unit if score > 20 else None


def _label_points(document, entities: list) -> list[tuple[str, tuple[float, float]]]:
    labels: list[tuple[str, tuple[float, float]]] = []
    for entity in entities:
        box = _raw_bbox(entity)
        if box is None:
            continue
        for value in _block_texts(document, entity):
            normalized = value.strip().upper()
            if ELEMENT_LABEL.fullmatch(normalized):
                labels.append((normalized, _center(box)))
    return labels


def _nearest_label(
    point: tuple[float, float],
    labels: list[tuple[str, tuple[float, float]]],
    suggested_scale: float,
) -> str:
    if not labels:
        return ""
    distance, label = min(
        (math.dist(point, location) * suggested_scale, label) for label, location in labels
    )
    return label if distance <= 2.0 else ""


def _physical_columns(
    document,
    cluster: PlanCluster,
    suggested_scale: float,
) -> list[PhysicalColumn]:
    labels = _label_points(document, cluster.columns)
    columns: list[PhysicalColumn] = []
    for entity in cluster.columns:
        raw_box = _raw_bbox(entity)
        if raw_box is None:
            continue
        small, large = sorted(value * suggested_scale for value in _dimensions(raw_box))
        if not (0.2 <= small <= 1.2 and small <= large <= 2.0 and large / small <= 4):
            continue
        columns.append(
            PhysicalColumn(
                entity=entity,
                raw_box=raw_box,
                label=_nearest_label(_center(raw_box), labels, suggested_scale),
            )
        )
    return columns


def _beam_annotations(document, cluster: PlanCluster) -> list[BeamAnnotation]:
    annotations: list[BeamAnnotation] = []
    for entity in cluster.beams:
        raw_box = _raw_bbox(entity)
        if raw_box is None:
            continue
        width, height = _dimensions(raw_box)
        orientation = "horizontal" if width >= height else "vertical"
        for value in _block_texts(document, entity):
            normalized = _normalize(value).replace("×", "X")
            match = BEAM_SECTION.search(normalized)
            if match is None:
                continue
            section_width = float(match.group("width").replace(",", ".")) / 100.0
            section_height = float(match.group("height").replace(",", ".")) / 100.0
            if not (0.15 <= section_width <= 1.5 and 0.2 <= section_height <= 2.5):
                continue
            annotations.append(
                BeamAnnotation(
                    label=match.group("label"),
                    section_width_m=round(section_width, 4),
                    section_height_m=round(section_height, 4),
                    raw_box=raw_box,
                    orientation=orientation,
                    text=value.strip(),
                    handle=str(entity.dxf.handle),
                    plan_title=cluster.title,
                )
            )
    return annotations


def _physical_column_signature(
    document,
    cluster: PlanCluster,
    suggested_scale: float,
) -> tuple[tuple[float, float, float, float], ...]:
    """Identify sibling plan views by their physical column layout."""
    rows: list[tuple[float, float, float, float]] = []
    for column in _physical_columns(document, cluster, suggested_scale):
        box = column.raw_box
        rows.append(
            (
                round(box[0] - cluster.root[0], 2),
                round(box[1] - cluster.root[1], 2),
                round(box[2] - cluster.root[0], 2),
                round(box[3] - cluster.root[1], 2),
            )
        )
    return tuple(sorted(rows))


def _beam_annotations_with_sibling_evidence(
    document,
    cluster: PlanCluster,
    all_clusters: list[PlanCluster],
    suggested_scale: float,
) -> list[BeamAnnotation]:
    """Complete sparse formwork labels from the matching reinforced plan view.

    The label geometry is translated only when the physical column layout is
    identical. This keeps the relationship geometric and project-independent.
    """
    annotations = _beam_annotations(document, cluster)
    seen_labels = {annotation.label for annotation in annotations}
    signature = _physical_column_signature(document, cluster, suggested_scale)
    if not signature:
        return annotations

    for sibling in all_clusters:
        if (
            sibling is cluster
            or _physical_column_signature(document, sibling, suggested_scale) != signature
        ):
            continue
        offset_x = cluster.root[0] - sibling.root[0]
        offset_y = cluster.root[1] - sibling.root[1]
        for annotation in _beam_annotations(document, sibling):
            if annotation.label in seen_labels:
                continue
            box = annotation.raw_box
            annotations.append(
                BeamAnnotation(
                    label=annotation.label,
                    section_width_m=annotation.section_width_m,
                    section_height_m=annotation.section_height_m,
                    raw_box=(
                        box[0] + offset_x,
                        box[1] + offset_y,
                        box[2] + offset_x,
                        box[3] + offset_y,
                    ),
                    orientation=annotation.orientation,
                    text=annotation.text,
                    handle=annotation.handle,
                    plan_title=annotation.plan_title,
                    translated_from_sibling=True,
                )
            )
            seen_labels.add(annotation.label)
    return annotations


def _slab_annotations(document, cluster: PlanCluster) -> list[SlabAnnotation]:
    annotations: list[SlabAnnotation] = []
    for entity in cluster.slabs:
        raw_box = _raw_bbox(entity)
        if raw_box is None:
            continue
        values = [value.strip() for value in _block_texts(document, entity)]
        label = next(
            (value.upper() for value in values if SLAB_LABEL.fullmatch(_normalize(value))),
            "",
        )
        if not label:
            continue
        thickness_m = None
        thickness_text = ""
        for value in values:
            match = SLAB_THICKNESS.fullmatch(_normalize(value).replace(",", "."))
            if match is None:
                continue
            raw_value = float(match.group("value"))
            candidate = raw_value / 100.0 if raw_value <= 100 else raw_value / 1000.0
            if 0.05 <= candidate <= 1.0:
                thickness_m = round(candidate, 4)
                thickness_text = value
                break
        annotations.append(
            SlabAnnotation(
                label=label,
                thickness_m=thickness_m,
                thickness_text=thickness_text,
                raw_box=raw_box,
                block_name=str(entity.dxf.name),
                handle=str(entity.dxf.handle),
            )
        )
    return annotations


def _insert_segments(entity, suggested_scale: float) -> list[BoundarySegment]:
    try:
        children = list(entity.virtual_entities())
    except Exception:
        return []
    segments: list[BoundarySegment] = []
    tolerance = 0.005 / suggested_scale
    for child in children:
        if child.dxftype() == "LINE":
            points = [child.dxf.start, child.dxf.end]
        elif child.dxftype() == "LWPOLYLINE":
            points = [Vec3(point[0], point[1], 0) for point in child.get_points("xy")]
            if bool(getattr(child, "closed", False)) and points:
                points.append(points[0])
        else:
            continue
        for first, second in zip(points, points[1:], strict=False):
            if abs(first.x - second.x) > tolerance and abs(first.y - second.y) > tolerance:
                continue
            segments.append(
                BoundarySegment(
                    start=(float(first.x), float(first.y)),
                    end=(float(second.x), float(second.y)),
                    handle=str(entity.dxf.handle),
                    layer=str(entity.dxf.layer),
                )
            )
    return segments


def _slab_boundary_segments(
    cluster: PlanCluster,
    physical_columns: list[PhysicalColumn],
    suggested_scale: float,
) -> list[BoundarySegment]:
    segments = [
        segment
        for entity in [*cluster.beams, *cluster.slab_edges]
        for segment in _insert_segments(entity, suggested_scale)
    ]
    for column in physical_columns:
        x1, y1, x2, y2 = column.raw_box
        handle = str(column.entity.dxf.handle)
        segments.extend(
            [
                BoundarySegment((x1, y1), (x2, y1), handle, "Kolon"),
                BoundarySegment((x2, y1), (x2, y2), handle, "Kolon"),
                BoundarySegment((x2, y2), (x1, y2), handle, "Kolon"),
                BoundarySegment((x1, y2), (x1, y1), handle, "Kolon"),
            ]
        )
    return segments


def _slab_rectangle(
    annotation: SlabAnnotation,
    segments: list[BoundarySegment],
    suggested_scale: float,
) -> tuple[tuple[float, float, float, float], list[BoundarySegment]] | None:
    point_x, point_y = _center(annotation.raw_box)
    tolerance = 0.01 / suggested_scale
    vertical = [
        segment
        for segment in segments
        if abs(segment.start[0] - segment.end[0]) <= tolerance
        and min(segment.start[1], segment.end[1]) - tolerance
        <= point_y
        <= max(segment.start[1], segment.end[1]) + tolerance
    ]
    horizontal = [
        segment
        for segment in segments
        if abs(segment.start[1] - segment.end[1]) <= tolerance
        and min(segment.start[0], segment.end[0]) - tolerance
        <= point_x
        <= max(segment.start[0], segment.end[0]) + tolerance
    ]
    left = max(
        (segment for segment in vertical if segment.start[0] < point_x - tolerance),
        key=lambda segment: segment.start[0],
        default=None,
    )
    right = min(
        (segment for segment in vertical if segment.start[0] > point_x + tolerance),
        key=lambda segment: segment.start[0],
        default=None,
    )
    bottom = max(
        (segment for segment in horizontal if segment.start[1] < point_y - tolerance),
        key=lambda segment: segment.start[1],
        default=None,
    )
    top = min(
        (segment for segment in horizontal if segment.start[1] > point_y + tolerance),
        key=lambda segment: segment.start[1],
        default=None,
    )
    if left is None or right is None or bottom is None or top is None:
        return None
    raw_box = (left.start[0], bottom.start[1], right.start[0], top.start[1])
    width_m, height_m = (value * suggested_scale for value in _dimensions(raw_box))
    if not (0.2 <= width_m <= 40 and 0.2 <= height_m <= 40):
        return None
    return raw_box, [left, right, bottom, top]


def _nested_hatch_area(items, level: int = 0) -> float:
    total = 0.0
    for item in items:
        if isinstance(item, list):
            total += _nested_hatch_area(item, level + 1)
        else:
            vertices = list(item.flattening(distance=0.1))
            sign = 1.0 if level % 2 else -1.0
            total += sign * abs(float(polygon_area(vertices)))
    return total


def _slab_openings(document) -> list[SlabOpening]:
    tokens = ("BOSLUK", "SAFT", "ASANSOR", "MERDIVEN", "OPENING", "VOID")
    openings: list[SlabOpening] = []
    seen: set[tuple[float, float, float, float]] = set()
    for entity in document.modelspace():
        if entity.dxftype() not in {"LWPOLYLINE", "HATCH", "INSERT"}:
            continue
        layer = str(entity.dxf.layer)
        if not any(token in _layer(layer) for token in tokens):
            continue
        raw_box = _raw_bbox(entity)
        if raw_box is None:
            continue
        width, height = _dimensions(raw_box)
        if width <= 0 or height <= 0:
            continue
        raw_area = width * height
        if entity.dxftype() == "LWPOLYLINE" and bool(getattr(entity, "closed", False)):
            points = [(float(point[0]), float(point[1])) for point in entity.get_points("xy")]
            if len(points) >= 3:
                raw_area = abs(
                    sum(
                        first[0] * second[1] - second[0] * first[1]
                        for first, second in zip(points, points[1:] + points[:1], strict=True)
                    )
                    / 2.0
                )
        elif entity.dxftype() == "HATCH":
            try:
                raw_area = _nested_hatch_area(make_polygon_structure(list(from_hatch(entity))))
            except Exception:
                continue
        if raw_area <= 0:
            continue
        fingerprint = (
            round(raw_box[0], 4),
            round(raw_box[1], 4),
            round(raw_box[2], 4),
            round(raw_box[3], 4),
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        openings.append(
            SlabOpening(
                raw_box=raw_box,
                raw_area=raw_area,
                handle=str(entity.dxf.handle),
                layer=layer,
            )
        )
    return openings


def _openings_inside_panel(
    raw_box: tuple[float, float, float, float],
    openings: list[SlabOpening],
) -> list[SlabOpening]:
    panel_area = abs((raw_box[2] - raw_box[0]) * (raw_box[3] - raw_box[1]))
    result: list[SlabOpening] = []
    for opening in openings:
        box = opening.raw_box
        center_x, center_y = _center(box)
        if not (raw_box[0] < center_x < raw_box[2] and raw_box[1] < center_y < raw_box[3]):
            continue
        if not (
            raw_box[0] <= box[0]
            and raw_box[1] <= box[1]
            and box[2] <= raw_box[2]
            and box[3] <= raw_box[3]
        ):
            continue
        if opening.raw_area >= panel_area * 0.8:
            continue
        result.append(opening)
    return result


def _height_evidence(document) -> tuple[list[float], set[str]]:
    elevations: set[float] = set()
    labels: set[str] = set()
    for entity in document.modelspace():
        value = _text(entity).strip()
        if not value:
            continue
        if _layer(entity.dxf.layer) == "KESITKOT" and ELEVATION.fullmatch(value.replace(",", ".")):
            elevations.add(float(value.replace(",", ".")))
        normalized = value.upper()
        if ELEMENT_LABEL.fullmatch(normalized):
            labels.add(normalized)
    ordered = sorted(elevations)
    differences = sorted(
        {
            round(high - low, 4)
            for index, low in enumerate(ordered)
            for high in ordered[index + 1 :]
            if 0.3 <= high - low <= 10
        }
    )
    return differences, labels


def _identity(source: SourceFile, element_type: str, handles: list[str]) -> str:
    value = "|".join((source.sha256, source.floor, element_type, *handles))
    return "elm_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _column_elements(
    source: SourceFile,
    cluster: PlanCluster,
    physical_columns: list[PhysicalColumn],
    chosen_scale: float | None,
    height_candidates: list[float],
    height_labels: set[str],
    unit_mismatch: bool,
) -> list[DetectedElement]:
    elements: list[DetectedElement] = []
    for record in physical_columns:
        entity = record.entity
        raw_box = record.raw_box
        scaled = _scaled_box(raw_box, chosen_scale)
        width, depth = sorted(_dimensions(scaled))
        label = record.label
        measurements = {"width_m": round(width, 6), "depth_m": round(depth, 6)}
        matched_heights = height_candidates if label and label in height_labels else []
        if len(matched_heights) == 1 and not unit_mismatch:
            measurements["height_m"] = matched_heights[0]
        issues = []
        if "height_m" not in measurements:
            issues.append("missing:height_m")
        if unit_mismatch:
            issues.append("blocking:unit_mismatch_suspected")
        handle = str(entity.dxf.handle)
        elements.append(
            DetectedElement(
                id=_identity(source, "column", [handle]),
                source_id=source.id,
                discipline=source.discipline,
                element_type="column",
                floor=source.floor,
                layer=entity.dxf.layer,
                block_name=str(entity.dxf.name),
                source_handle=handle,
                geometry=Geometry(
                    kind="closed_outline",
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
                    "quantity_kind": "column",
                    "element_label": label,
                    "plan_title": cluster.title,
                    "height_candidates_m": height_candidates,
                    "height_evidence_labels": sorted(height_labels),
                },
                required_inputs=["width_m", "depth_m", "height_m"],
                confidence=0.9 if label and not unit_mismatch else 0.72,
                review_status=ReviewStatus.NEEDS_REVIEW,
                issues=issues,
            )
        )
    return elements


def _beam_pairs(cluster: PlanCluster, suggested_scale: float) -> list[tuple]:
    by_orientation: dict[str, list[tuple]] = {"vertical": [], "horizontal": []}
    for entity in cluster.beams:
        box = _raw_bbox(entity)
        if box is None:
            continue
        width, height = _dimensions(box)
        if width <= 1e-5 and height * suggested_scale >= 0.5:
            by_orientation["vertical"].append((entity, (box[0], box[1], box[3])))
        elif height <= 1e-5 and width * suggested_scale >= 0.5:
            by_orientation["horizontal"].append((entity, (box[1], box[0], box[2])))

    pairs: list[tuple] = []
    for orientation, segments in by_orientation.items():
        used: set[int] = set()
        for index, (entity, first) in enumerate(segments):
            if index in used:
                continue
            choices: list[tuple] = []
            for other_index, (other, second) in enumerate(segments):
                if other_index <= index or other_index in used:
                    continue
                separation = abs(first[0] - second[0]) * suggested_scale
                length = max(first[2] - first[1], second[2] - second[1]) * suggested_scale
                end_error = (
                    abs(first[1] - second[1]) + abs(first[2] - second[2])
                ) * suggested_scale
                if 0.15 <= separation <= 0.8 and 0.5 <= length <= 30 and end_error <= 0.03:
                    choices.append((end_error, separation, other_index, other, second))
            if not choices:
                continue
            _, _, other_index, other, second = min(choices, key=lambda item: (item[0], item[1]))
            used.update((index, other_index))
            raw_box = (
                min(first[0], second[0]) if orientation == "vertical" else min(first[1], second[1]),
                min(first[1], second[1]) if orientation == "vertical" else min(first[0], second[0]),
                max(first[0], second[0]) if orientation == "vertical" else max(first[2], second[2]),
                max(first[2], second[2]) if orientation == "vertical" else max(first[0], second[0]),
            )
            pairs.append((entity, other, raw_box, orientation))
    return pairs


def _match_beam_annotation(
    raw_box: tuple[float, float, float, float],
    orientation: str,
    annotations: list[BeamAnnotation],
    used_handles: set[str],
    suggested_scale: float,
) -> BeamAnnotation | None:
    center = _center(raw_box)
    choices: list[tuple[float, BeamAnnotation]] = []
    for annotation in annotations:
        if annotation.handle in used_handles or annotation.orientation != orientation:
            continue
        annotation_center = _center(annotation.raw_box)
        outside_x = max(raw_box[0] - annotation_center[0], 0, annotation_center[0] - raw_box[2])
        outside_y = max(raw_box[1] - annotation_center[1], 0, annotation_center[1] - raw_box[3])
        outside = math.hypot(outside_x, outside_y) * suggested_scale
        if outside > 0.75:
            continue
        distance = math.dist(center, annotation_center) * suggested_scale
        choices.append((outside * 10 + distance, annotation))
    if not choices:
        return None
    annotation = min(choices, key=lambda item: item[0])[1]
    used_handles.add(annotation.handle)
    return annotation


def inspect_structural_unit(document) -> tuple[DrawingUnit | None, list[str], DrawingUnit | None]:
    """Suggest a drawing unit only when plan geometry agrees with written sections.

    Column sizes and building span provide a candidate, but are not proof on
    their own. Independent beam section labels must corroborate the candidate.
    """
    clusters = _candidate_clusters(document)
    selected, _ = _select_clusters(clusters)
    geometric_candidate = _suggest_unit(selected)
    if geometric_candidate is None:
        return None, [], None

    scale = unit_scale(geometric_candidate)
    label_checks: dict[str, list[bool]] = defaultdict(list)
    for cluster in selected:
        annotations = _beam_annotations_with_sibling_evidence(document, cluster, clusters, scale)
        used_handles: set[str] = set()
        for _, _, raw_box, orientation in _beam_pairs(cluster, scale):
            annotation = _match_beam_annotation(
                raw_box, orientation, annotations, used_handles, scale
            )
            if annotation is None:
                continue
            label = f"{annotation.label}:{annotation.section_width_m:g}"
            raw_width = (
                raw_box[3] - raw_box[1] if orientation == "horizontal" else raw_box[2] - raw_box[0]
            )
            label_checks[label].append(
                abs(raw_width * scale - annotation.section_width_m)
                <= max(0.015, annotation.section_width_m * 0.06)
            )

    agreeing_count = sum(all(checks) for checks in label_checks.values())
    matched_count = len(label_checks)
    if matched_count >= 3 and agreeing_count / matched_count >= 0.8:
        return (
            geometric_candidate,
            [
                f"{agreeing_count}/{matched_count} farklı kiriş kesit etiketi çizim "
                f"genişliğiyle {geometric_candidate.value} biriminde eşleşiyor",
                "Kolon ölçüleri ve bina açıklığı aynı birimi destekliyor",
            ],
            geometric_candidate,
        )
    return (
        None,
        [
            f"Kolon geometrisi {geometric_candidate.value} birimini düşündürüyor; "
            f"yazılı kiriş kesitleri yeterince doğrulamadı ({agreeing_count}/{matched_count})"
        ],
        geometric_candidate,
    )


def _ranges_overlap(
    first: tuple[float, float],
    second: tuple[float, float],
) -> bool:
    return min(first[1], second[1]) >= max(first[0], second[0])


def _beam_supports(
    raw_box: tuple[float, float, float, float],
    orientation: str,
    physical_columns: list[PhysicalColumn],
    suggested_scale: float,
) -> tuple[PhysicalColumn, PhysicalColumn] | None:
    if orientation == "horizontal":
        overlapping = [
            column
            for column in physical_columns
            if _ranges_overlap(
                (raw_box[1], raw_box[3]),
                (column.raw_box[1], column.raw_box[3]),
            )
        ]
        left = min(
            overlapping,
            key=lambda column: abs(column.raw_box[2] - raw_box[0]),
            default=None,
        )
        right = min(
            overlapping,
            key=lambda column: abs(column.raw_box[0] - raw_box[2]),
            default=None,
        )
        if left is None or right is None:
            return None
        errors = (
            abs(left.raw_box[2] - raw_box[0]) * suggested_scale,
            abs(right.raw_box[0] - raw_box[2]) * suggested_scale,
        )
    else:
        overlapping = [
            column
            for column in physical_columns
            if _ranges_overlap(
                (raw_box[0], raw_box[2]),
                (column.raw_box[0], column.raw_box[2]),
            )
        ]
        left = min(
            overlapping,
            key=lambda column: abs(column.raw_box[3] - raw_box[1]),
            default=None,
        )
        right = min(
            overlapping,
            key=lambda column: abs(column.raw_box[1] - raw_box[3]),
            default=None,
        )
        if left is None or right is None:
            return None
        errors = (
            abs(left.raw_box[3] - raw_box[1]) * suggested_scale,
            abs(right.raw_box[1] - raw_box[3]) * suggested_scale,
        )
    if max(errors) > 0.15 or left.entity.dxf.handle == right.entity.dxf.handle:
        return None
    return left, right


def _length_evidence(
    raw_box: tuple[float, float, float, float],
    orientation: str,
    supports: tuple[PhysicalColumn, PhysicalColumn] | None,
    scale: float | None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "policy": "clear_between_support_faces",
        "geometry": "paired_beam_outline_edges",
    }
    if supports is None or scale is None:
        return evidence
    first, second = supports
    if orientation == "horizontal":
        first_center = _center(first.raw_box)[0]
        second_center = _center(second.raw_box)[0]
        gross = second.raw_box[2] - first.raw_box[0]
    else:
        first_center = _center(first.raw_box)[1]
        second_center = _center(second.raw_box)[1]
        gross = second.raw_box[3] - first.raw_box[1]
    evidence.update(
        {
            "support_labels": [first.label, second.label],
            "support_handles": [str(first.entity.dxf.handle), str(second.entity.dxf.handle)],
            "axis_length_m": round(abs(second_center - first_center) * scale, 6),
            "gross_support_extent_m": round(abs(gross) * scale, 6),
        }
    )
    return evidence


def _beam_elements(
    source: SourceFile,
    cluster: PlanCluster,
    physical_columns: list[PhysicalColumn],
    annotations: list[BeamAnnotation],
    chosen_scale: float | None,
    suggested_unit: DrawingUnit,
    unit_mismatch: bool,
) -> list[DetectedElement]:
    suggested_scale = unit_scale(suggested_unit)
    elements: list[DetectedElement] = []
    used_annotation_handles: set[str] = set()
    for first, second, raw_box, orientation in _beam_pairs(cluster, suggested_scale):
        scaled = _scaled_box(raw_box, chosen_scale)
        spans = sorted(_dimensions(scaled))
        suggested_spans = sorted(value * suggested_scale for value in _dimensions(raw_box))
        annotation = _match_beam_annotation(
            raw_box,
            orientation,
            annotations,
            used_annotation_handles,
            suggested_scale,
        )
        supports = _beam_supports(
            raw_box,
            orientation,
            physical_columns,
            suggested_scale,
        )
        measurements = {"width_m": round(spans[0], 6), "length_m": round(spans[1], 6)}
        section_width_matches = bool(
            annotation and abs(annotation.section_width_m - suggested_spans[0]) <= 0.03
        )
        if annotation and section_width_matches:
            measurements["height_m"] = annotation.section_height_m
        issues: list[str] = []
        if "height_m" not in measurements:
            issues.append("missing:height_m")
        if annotation and not section_width_matches:
            issues.append("blocking:beam_section_width_mismatch")
        if unit_mismatch:
            issues.append("blocking:unit_mismatch_suspected")
        handles = sorted((str(first.dxf.handle), str(second.dxf.handle)))
        section_evidence = None
        if annotation:
            section_evidence = {
                "element_label": annotation.label,
                "section_text": annotation.text,
                "section_width_m": annotation.section_width_m,
                "section_height_m": annotation.section_height_m,
                "annotation_handle": annotation.handle,
                "source_plan_title": annotation.plan_title,
                "method": (
                    "matching_reinforced_plan_beam_label"
                    if annotation.translated_from_sibling
                    else "plan_beam_label"
                ),
            }
        status = ReviewStatus.PENDING if not issues else ReviewStatus.NEEDS_REVIEW
        confidence = 0.7
        if annotation and section_width_matches:
            confidence = 0.96 if supports else 0.9
        if unit_mismatch:
            confidence = min(confidence, 0.72)
        elements.append(
            DetectedElement(
                id=_identity(source, "beam", handles),
                source_id=source.id,
                discipline=source.discipline,
                element_type="beam",
                floor=source.floor,
                layer=first.dxf.layer,
                block_name=f"{first.dxf.name}+{second.dxf.name}",
                source_handle="+".join(handles),
                geometry=Geometry(
                    kind=f"paired_{orientation}_edges",
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
                    "quantity_kind": "beam",
                    "element_label": annotation.label if annotation else "",
                    "plan_title": cluster.title,
                    "source_handles": handles,
                    "beam_section_evidence": section_evidence,
                    "length_evidence": _length_evidence(
                        raw_box,
                        orientation,
                        supports,
                        chosen_scale,
                    ),
                },
                required_inputs=["length_m", "width_m", "height_m"],
                confidence=confidence,
                review_status=status,
                issues=issues,
            )
        )
    return elements


def _slab_elements(
    source: SourceFile,
    cluster: PlanCluster,
    annotations: list[SlabAnnotation],
    segments: list[BoundarySegment],
    chosen_scale: float | None,
    suggested_scale: float,
    unit_mismatch: bool,
    openings: list[SlabOpening],
) -> list[DetectedElement]:
    elements: list[DetectedElement] = []
    for annotation in annotations:
        rectangle = _slab_rectangle(annotation, segments, suggested_scale)
        raw_box = rectangle[0] if rectangle else annotation.raw_box
        boundaries = rectangle[1] if rectangle else []
        scaled = _scaled_box(raw_box, chosen_scale)
        panel_openings = _openings_inside_panel(raw_box, openings) if rectangle else []
        measurements: dict[str, float] = {}
        if rectangle and chosen_scale is not None:
            width, height = _dimensions(scaled)
            gross_area = width * height
            void_area = min(
                sum(item.raw_area for item in panel_openings) * chosen_scale**2,
                gross_area,
            )
            measurements.update(
                {
                    "area_m2": round(gross_area - void_area, 6),
                    "gross_area_m2": round(gross_area, 6),
                    "void_area_m2": round(void_area, 6),
                    "void_count": float(len(panel_openings)),
                    "perimeter_m": round(2 * (width + height), 6),
                }
            )
        if annotation.thickness_m is not None:
            measurements["thickness_m"] = annotation.thickness_m
        issues: list[str] = []
        if rectangle is None:
            issues.append("missing:area_m2")
        if annotation.thickness_m is None:
            issues.append("missing:thickness_m")
        if unit_mismatch:
            issues.append("blocking:unit_mismatch_suspected")
        confidence = 0.96 if rectangle and annotation.thickness_m is not None else 0.65
        if unit_mismatch:
            confidence = min(confidence, 0.72)
        elements.append(
            DetectedElement(
                id=_identity(source, "slab", [annotation.handle]),
                source_id=source.id,
                discipline=source.discipline,
                element_type="slab",
                floor=source.floor,
                layer="Döşeme",
                block_name=annotation.block_name,
                source_handle=annotation.handle,
                geometry=Geometry(
                    kind="inferred_rectangular_panel",
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
                    "plan_title": cluster.title,
                    "slab_evidence": {
                        "label": annotation.label,
                        "label_handle": annotation.handle,
                        "thickness_text": annotation.thickness_text,
                        "boundary_handles": [boundary.handle for boundary in boundaries],
                        "boundary_layers": [boundary.layer for boundary in boundaries],
                        "method": "label_point_cardinal_rays_to_structural_faces",
                        "void_count": len(panel_openings),
                        "void_area_m2": measurements.get("void_area_m2", 0.0),
                        "gross_area_m2": measurements.get("gross_area_m2", 0.0),
                        "void_handles": [item.handle for item in panel_openings],
                        "void_layers": [item.layer for item in panel_openings],
                    },
                },
                required_inputs=["area_m2", "thickness_m"],
                confidence=confidence,
                review_status=ReviewStatus.PENDING if not issues else ReviewStatus.NEEDS_REVIEW,
                issues=issues,
            )
        )
    return elements


def _reconcile_beam_formwork(
    beams: list[DetectedElement],
    slabs: list[DetectedElement],
) -> int:
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
        source_handles = beam.properties.get("source_handles", [])
        if not isinstance(source_handles, list) or len(source_handles) != 2:
            continue
        length = beam.measurements.get("length_m")
        width = beam.measurements.get("width_m")
        height = beam.measurements.get("height_m")
        if length is None or width is None or height is None:
            continue
        adjacent_thicknesses = [
            max(thicknesses_by_boundary.get(str(handle), [0.0])) for handle in source_handles
        ]
        exposed_depths = [
            round(max(height - thickness, 0.0), 6) if thickness > 0 else height
            for thickness in adjacent_thicknesses
        ]
        formwork_area = round((width + sum(exposed_depths)) * length, 6)
        beam.measurements["formwork_area_m2"] = formwork_area
        beam.properties["formwork_evidence"] = {
            "policy": "soffit_plus_exposed_sides_after_slab_deduction",
            "side_handles": [str(handle) for handle in source_handles],
            "adjacent_slab_thicknesses_m": adjacent_thicknesses,
            "exposed_side_depths_m": exposed_depths,
            "soffit_width_m": width,
            "length_m": length,
        }
        if "formwork_area_m2" not in beam.required_inputs:
            beam.required_inputs.append("formwork_area_m2")
        reconciled += 1
    return reconciled


def extract_structural_plans(
    document,
    source: SourceFile,
    chosen_unit: DrawingUnit,
) -> StructuralPlanResult:
    clusters = _candidate_clusters(document)
    if not clusters or not any(
        PREFERRED_PLAN_TOKEN in _normalize(cluster.title) for cluster in clusters
    ):
        return StructuralPlanResult([], [], False)

    selected, skipped_clusters = _select_clusters(clusters)
    suggested_unit = _suggest_unit(selected)
    if suggested_unit is None:
        return StructuralPlanResult([], [], False)
    chosen_scale = None if chosen_unit == DrawingUnit.UNKNOWN else unit_scale(chosen_unit)
    unit_mismatch = chosen_unit not in (DrawingUnit.UNKNOWN, suggested_unit)
    suggested_scale = unit_scale(suggested_unit)
    height_candidates, height_labels = _height_evidence(document)
    elements: list[DetectedElement] = []
    reconciled_beam_formwork_count = 0
    sibling_beam_annotation_count = 0
    slab_openings = _slab_openings(document)
    for cluster in selected:
        physical_columns = _physical_columns(document, cluster, suggested_scale)
        beam_annotations = _beam_annotations_with_sibling_evidence(
            document,
            cluster,
            clusters,
            suggested_scale,
        )
        sibling_beam_annotation_count += sum(
            annotation.translated_from_sibling for annotation in beam_annotations
        )
        slab_annotations = _slab_annotations(document, cluster)
        slab_segments = _slab_boundary_segments(
            cluster,
            physical_columns,
            suggested_scale,
        )
        elements.extend(
            _column_elements(
                source,
                cluster,
                physical_columns,
                chosen_scale,
                height_candidates,
                height_labels,
                unit_mismatch,
            )
        )
        cluster_slabs = _slab_elements(
            source,
            cluster,
            slab_annotations,
            slab_segments,
            chosen_scale,
            suggested_scale,
            unit_mismatch,
            slab_openings,
        )
        cluster_beams = _beam_elements(
            source,
            cluster,
            physical_columns,
            beam_annotations,
            chosen_scale,
            suggested_unit,
            unit_mismatch,
        )
        reconciled_beam_formwork_count += _reconcile_beam_formwork(
            cluster_beams,
            cluster_slabs,
        )
        elements.extend(cluster_slabs)
        elements.extend(cluster_beams)

    detected_beam_labels = {
        str(element.properties.get("element_label", ""))
        for element in elements
        if element.element_type == "beam" and element.properties.get("element_label")
    }
    rebar_elements, rebar_warnings = extract_beam_rebar_table(
        document,
        source,
        [cluster.root for cluster in selected],
        detected_beam_labels,
        chosen_scale or suggested_scale,
    )
    elements.extend(rebar_elements)

    raw_column_count = sum(len(cluster.columns) for cluster in clusters)
    raw_beam_count = sum(len(cluster.beams) for cluster in clusters)
    column_count = sum(element.element_type == "column" for element in elements)
    beam_count = sum(element.element_type == "beam" for element in elements)
    slab_count = sum(element.element_type == "slab" for element in elements)
    complete_slab_count = sum(
        element.element_type == "slab" and not element.missing_inputs() for element in elements
    )
    slab_void_count = sum(
        int(element.measurements.get("void_count", 0))
        for element in elements
        if element.element_type == "slab"
    )
    beam_section_count = sum(
        element.element_type == "beam"
        and bool(element.properties.get("beam_section_evidence"))
        and "height_m" in element.measurements
        for element in elements
    )
    warnings = [
        AnalysisWarning(
            code="STRUCTURAL_PLAN_FILTER_APPLIED",
            message=(
                f"Kalıp planı ayrıştırıldı: {raw_column_count} kolon katmanı bloğundan "
                f"{column_count} fiziksel kolon; {raw_beam_count} kiriş katmanı bloğundan "
                f"{beam_count} fiziksel kiriş açıklığı tutuldu."
            ),
            source_id=source.id,
            severity="info",
        )
    ]
    if skipped_clusters:
        warnings.append(
            AnalysisWarning(
                code="REPEATED_STRUCTURAL_PLANS_SKIPPED",
                message=(
                    f"Aynı geometriyi taşıyan {skipped_clusters} tekrar/donatılı plan bölgesi "
                    "eleman adetlerine yeniden eklenmedi."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    if beam_section_count:
        warnings.append(
            AnalysisWarning(
                code="BEAM_SECTIONS_LINKED",
                message=(
                    f"{beam_section_count}/{beam_count} fiziksel kiriş, plan üzerindeki "
                    "kiriş etiketi ve b/h kesitiyle eşleştirildi. Uzunluk kolon yüzleri "
                    "arasındaki net açıklık olarak saklandı."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    if sibling_beam_annotation_count:
        warnings.append(
            AnalysisWarning(
                code="SIBLING_REINFORCED_PLAN_EVIDENCE_LINKED",
                message=(
                    f"Donatısız kalıp planında yazılmayan {sibling_beam_annotation_count} "
                    "kiriş etiketi/kesiti, aynı kolon geometrisine sahip donatılı plan "
                    "görünümünden koordinat dönüşümüyle bağlandı."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    if beam_section_count < beam_count:
        warnings.append(
            AnalysisWarning(
                code="BEAM_SECTION_REVIEW_REQUIRED",
                message=(
                    f"{beam_count - beam_section_count} kiriş için güvenilir plan etiketi "
                    "ve kesit eşleşmesi kurulamadı; kesit yüksekliği otomatik doldurulmadı."
                ),
                source_id=source.id,
            )
        )
    if slab_count:
        warnings.append(
            AnalysisWarning(
                code="SLAB_PANELS_LINKED",
                message=(
                    f"{complete_slab_count}/{slab_count} döşeme etiketi, kalınlık yazısı ve "
                    "kiriş/kolon/dış kenar yüzlerinden kurulan net panel sınırıyla eşleştirildi."
                ),
                source_id=source.id,
                severity="info" if complete_slab_count == slab_count else "warning",
            )
        )
    if slab_void_count:
        warnings.append(
            AnalysisWarning(
                code="SLAB_OPENINGS_DEDUCTED",
                message=(
                    f"Döşeme panellerinde {slab_void_count} şaft/merdiven/boşluk sınırı "
                    "algılandı ve net alanlardan ayrı iz kaydıyla düşüldü."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    if reconciled_beam_formwork_count:
        warnings.append(
            AnalysisWarning(
                code="BEAM_FORMWORK_RECONCILED",
                message=(
                    f"{reconciled_beam_formwork_count} kirişin alt ve yan kalıbı hesaplandı; "
                    "komşu döşemenin kapattığı kalınlık kiriş yan yüzünden düşüldü."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    if column_count:
        warnings.append(
            AnalysisWarning(
                code="COLUMN_FORMWORK_GROSS_POLICY",
                message=(
                    "Kolon kalıbı brüt çevre × kat yüksekliği politikasıyla hesaplanıyor; "
                    "kolon-kiriş/döşeme birleşim yüzleri bu aşamada düşülmedi. Bu satırlar "
                    "net kalıp kabul edilmeden önce mühendis tarafından doğrulanmalı."
                ),
                source_id=source.id,
            )
        )
    if unit_mismatch:
        warnings.append(
            AnalysisWarning(
                code="UNIT_MISMATCH_SUSPECTED",
                message=(
                    f"Pafta geometrisi {suggested_unit.value} birimine uyuyor; seçili birim "
                    f"{chosen_unit.value}. Birim düzeltilmeden elemanlar onaylanamaz."
                ),
                source_id=source.id,
                severity="error",
            )
        )
    warnings.extend(rebar_warnings)
    labels_in_elements = {str(element.properties.get("element_label", "")) for element in elements}
    if height_candidates and not labels_in_elements.intersection(height_labels):
        warnings.append(
            AnalysisWarning(
                code="UNMATCHED_SECTION_HEIGHT_EVIDENCE",
                message=(
                    "Kesit kotlarından "
                    + ", ".join(f"{value:g} m" for value in height_candidates)
                    + " yükseklik adayı okundu; ancak kesitteki "
                    + ", ".join(sorted(height_labels))
                    + " etiketleri plan kolon/kiriş etiketleriyle eşleşmediği için değerler "
                    "kesin hesaba otomatik uygulanmadı."
                ),
                source_id=source.id,
            )
        )
    return StructuralPlanResult(elements, warnings, True)
