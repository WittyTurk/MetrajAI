from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ezdxf import bbox

from ..contracts import (
    AnalysisWarning,
    DetectedElement,
    DrawingUnit,
    Geometry,
    ReviewStatus,
    SourceFile,
)
from ..units import unit_scale

FOUNDATION_WALL = re.compile(
    r"(?P<label>PZ\d{1,3})\s*\[[^]]+\]\s*"
    r"(?P<first>\d+(?:[.,]\d+)?)/(?P<height>\d+(?:[.,]\d+)?)/"
    r"(?P<third>\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    text = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(text.upper().replace("İ", "I").split())


def _layer(value: str) -> str:
    return _normalize(value).replace(" ", "")


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
    value: tuple[float, float, float, float],
    scale: float,
) -> tuple[float, float, float, float]:
    return tuple(round(item * scale, 6) for item in value)  # type: ignore[return-value]


def _dimensions(value: tuple[float, float, float, float]) -> tuple[float, float]:
    return abs(value[2] - value[0]), abs(value[3] - value[1])


def _center(value: tuple[float, float, float, float]) -> tuple[float, float]:
    return (value[0] + value[2]) / 2, (value[1] + value[3]) / 2


def _block_text(document, entity) -> str:
    try:
        block = document.blocks.get(entity.dxf.name)
    except Exception:
        return ""
    values: list[str] = []
    for child in block:
        if child.dxftype() == "TEXT":
            values.append(str(child.dxf.text).strip())
        elif child.dxftype() == "MTEXT":
            values.append(str(child.plain_text()).strip())
    return " ".join(value for value in values if value)


def _block_has_hatch(document, entity) -> bool:
    try:
        return any(child.dxftype() == "HATCH" for child in document.blocks.get(entity.dxf.name))
    except Exception:
        return False


def _identity(source: SourceFile, element_type: str, handles: list[str]) -> str:
    value = f"{source.sha256}|foundation-plan|{element_type}|{'|'.join(sorted(handles))}"
    return "elm_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


@dataclass
class FoundationCluster:
    root: tuple[float, float]
    raft_entities: list[Any]
    wall_entities: list[Any]
    raft_box: tuple[float, float, float, float]


@dataclass(frozen=True)
class FoundationPlanResult:
    elements: list[DetectedElement]
    warnings: list[AnalysisWarning]
    activated: bool


def _clusters(document, scale: float) -> list[FoundationCluster]:
    grouped: dict[tuple[float, float], dict[str, list[Any]]] = defaultdict(
        lambda: {"raft": [], "wall": []}
    )
    for entity in document.modelspace():
        if entity.dxftype() != "INSERT":
            continue
        category = {
            "RADYEDOSEMEKENARI": "raft",
            "PERDE": "wall",
        }.get(_layer(str(entity.dxf.layer)))
        if category is None:
            continue
        point = entity.dxf.insert
        root = round(float(point.x), 3), round(float(point.y), 3)
        grouped[root][category].append(entity)

    clusters: list[FoundationCluster] = []
    for root, rows in grouped.items():
        if len(rows["raft"]) < 4 or len(rows["wall"]) < 4:
            continue
        boxes = [value for entity in rows["raft"] if (value := _raw_bbox(entity))]
        if len(boxes) < 4:
            continue
        raw_box = (
            min(value[0] for value in boxes),
            min(value[1] for value in boxes),
            max(value[2] for value in boxes),
            max(value[3] for value in boxes),
        )
        raft_box = _scaled_box(raw_box, scale)
        width, height = _dimensions(raft_box)
        if not (5 <= width <= 250 and 5 <= height <= 250):
            continue
        clusters.append(
            FoundationCluster(
                root=root,
                raft_entities=rows["raft"],
                wall_entities=rows["wall"],
                raft_box=raft_box,
            )
        )
    return clusters


def _wall_annotations(document, cluster: FoundationCluster) -> list[tuple[Any, re.Match[str]]]:
    values: list[tuple[Any, re.Match[str]]] = []
    for entity in cluster.wall_entities:
        match = FOUNDATION_WALL.search(_normalize(_block_text(document, entity)))
        if match is not None:
            values.append((entity, match))
    return values


def _cluster_signature(document, cluster: FoundationCluster) -> tuple:
    width, height = _dimensions(cluster.raft_box)
    annotations = _wall_annotations(document, cluster)
    rows = sorted(
        (
            match.group("label").upper(),
            match.group("first"),
            match.group("height"),
            match.group("third"),
        )
        for _, match in annotations
    )
    return round(width, 3), round(height, 3), tuple(rows)


def _plan_title(document, box: tuple[float, float, float, float], scale: float) -> str:
    center = _center(box)
    titles: list[tuple[float, str]] = []
    for entity in document.modelspace():
        if entity.dxftype() == "TEXT":
            value = str(entity.dxf.text).strip()
        elif entity.dxftype() == "MTEXT":
            value = str(entity.plain_text()).strip()
        else:
            continue
        if "TEMEL" not in _normalize(value) or "PLANI" not in _normalize(value):
            continue
        point = entity.dxf.insert
        location = float(point.x) * scale, float(point.y) * scale
        titles.append((math.dist(center, location), value))
    return min(titles, default=(0.0, "TEMEL PLANI"))[1]


def _wall_elements(
    document,
    source: SourceFile,
    cluster: FoundationCluster,
    scale: float,
    copy_count: int,
    plan_title: str,
) -> list[DetectedElement]:
    hatch_rows: list[tuple[Any, tuple[float, float, float, float]]] = []
    for entity in cluster.wall_entities:
        if not _block_has_hatch(document, entity):
            continue
        raw_box = _raw_bbox(entity)
        if raw_box is not None:
            hatch_rows.append((entity, _scaled_box(raw_box, scale)))

    used_handles: set[str] = set()
    elements: list[DetectedElement] = []
    for annotation, match in _wall_annotations(document, cluster):
        first = float(match.group("first").replace(",", ".")) / 100
        third = float(match.group("third").replace(",", ".")) / 100
        thickness, length = sorted((first, third))
        height = float(match.group("height").replace(",", ".")) / 100
        annotation_box = _raw_bbox(annotation)
        annotation_center = (
            _center(_scaled_box(annotation_box, scale)) if annotation_box else (0, 0)
        )
        matching = []
        for hatch, hatch_box in hatch_rows:
            if str(hatch.dxf.handle) in used_handles:
                continue
            small, large = sorted(_dimensions(hatch_box))
            if abs(small - thickness) <= 0.03 and abs(large - length) <= 0.05:
                matching.append(
                    (math.dist(annotation_center, _center(hatch_box)), hatch, hatch_box)
                )
        if not matching:
            continue
        _, hatch, hatch_box = min(matching, key=lambda item: item[0])
        used_handles.add(str(hatch.dxf.handle))
        label = match.group("label").upper()
        handles = [str(annotation.dxf.handle), str(hatch.dxf.handle)]
        issues = ["review:translated_foundation_views_deduplicated"] if copy_count > 1 else []
        elements.append(
            DetectedElement(
                id=_identity(source, f"shear-wall:{label}", handles),
                source_id=source.id,
                discipline=source.discipline,
                element_type="shear_wall",
                floor="TEMEL",
                layer=str(hatch.dxf.layer),
                block_name=str(hatch.dxf.name),
                source_handle="+".join(handles),
                geometry=Geometry(
                    kind="explicit_foundation_wall_hatch",
                    points=[
                        (hatch_box[0], hatch_box[1]),
                        (hatch_box[2], hatch_box[1]),
                        (hatch_box[2], hatch_box[3]),
                        (hatch_box[0], hatch_box[3]),
                        (hatch_box[0], hatch_box[1]),
                    ],
                    bbox=hatch_box,
                ),
                measurements={
                    "length_m": round(length, 6),
                    "height_m": round(height, 6),
                    "thickness_m": round(thickness, 6),
                },
                properties={
                    "quantity_kind": "shear_wall",
                    "element_label": label,
                    "plan_title": plan_title,
                    "foundation_wall_evidence": {
                        "method": "explicit_foundation_wall_hatch_and_dimension_label",
                        "annotation_text": _block_text(document, annotation),
                        "annotation_handle": str(annotation.dxf.handle),
                        "hatch_handle": str(hatch.dxf.handle),
                        "translated_copy_count": copy_count,
                    },
                },
                required_inputs=["length_m", "thickness_m", "height_m"],
                confidence=0.9 if copy_count > 1 else 0.96,
                review_status=ReviewStatus.NEEDS_REVIEW if copy_count > 1 else ReviewStatus.PENDING,
                issues=issues,
            )
        )
    return elements


def extract_foundation_application_plans(
    document,
    source: SourceFile,
    chosen_unit: DrawingUnit,
) -> FoundationPlanResult:
    if chosen_unit == DrawingUnit.UNKNOWN:
        return FoundationPlanResult([], [], False)
    scale = unit_scale(chosen_unit)
    candidates = _clusters(document, scale)
    if not candidates:
        return FoundationPlanResult([], [], False)

    grouped: dict[tuple, list[FoundationCluster]] = defaultdict(list)
    for cluster in candidates:
        grouped[_cluster_signature(document, cluster)].append(cluster)

    elements: list[DetectedElement] = []
    skipped = 0
    for copies in grouped.values():
        representative = max(copies, key=lambda item: (item.raft_box[3], -item.raft_box[0]))
        skipped += len(copies) - 1
        copy_count = len(copies)
        box = representative.raft_box
        width, height = _dimensions(box)
        plan_title = _plan_title(document, box, scale)
        boundary_handles = sorted(
            str(entity.dxf.handle)
            for cluster in copies
            for entity in cluster.raft_entities
        )
        elements.append(
            DetectedElement(
                id=_identity(source, "raft", boundary_handles),
                source_id=source.id,
                discipline=source.discipline,
                element_type="raft",
                floor="TEMEL",
                layer="RadyeDöşemeKenarı",
                source_handle="+".join(
                    sorted(str(entity.dxf.handle) for entity in representative.raft_entities)
                ),
                geometry=Geometry(
                    kind="paired_explicit_raft_boundary_edges",
                    points=[
                        (box[0], box[1]),
                        (box[2], box[1]),
                        (box[2], box[3]),
                        (box[0], box[3]),
                        (box[0], box[1]),
                    ],
                    bbox=box,
                ),
                measurements={
                    "area_m2": round(width * height, 6),
                    "gross_area_m2": round(width * height, 6),
                    "void_area_m2": 0.0,
                    "void_count": 0.0,
                    "perimeter_m": round(2 * (width + height), 6),
                },
                properties={
                    "quantity_kind": "raft",
                    "element_label": "Radye temel",
                    "plan_title": plan_title,
                    "foundation_evidence": {
                        "method": "paired_exported_raft_boundary_edges",
                        "boundary_handles": boundary_handles,
                        "translated_copy_count": copy_count,
                        "translated_copy_bboxes": [cluster.raft_box for cluster in copies],
                        "thickness_note_handles": [],
                        "thickness_texts": [],
                        "opening_policy": "explicit_closed_opening_geometry_required",
                    },
                },
                required_inputs=["area_m2", "thickness_m", "perimeter_m"],
                confidence=0.78,
                review_status=ReviewStatus.NEEDS_REVIEW,
                issues=[
                    "missing:thickness_m",
                    "review:translated_foundation_views_deduplicated",
                ],
            )
        )
        elements.extend(
            _wall_elements(
                document,
                source,
                representative,
                scale,
                copy_count,
                plan_title,
            )
        )

    raft_count = sum(item.element_type == "raft" for item in elements)
    wall_count = sum(item.element_type == "shear_wall" for item in elements)
    warnings = [
        AnalysisWarning(
            code="FOUNDATION_APPLICATION_PLAN_PARSED",
            message=(
                f"Temel uygulama planından {raft_count} radye sınırı ve {wall_count} "
                f"ölçülü temel perdesi çıkarıldı; {skipped} aynı geometrili kopya plan "
                "yeniden sayılmadı."
            ),
            source_id=source.id,
            severity="info",
        )
    ]
    if raft_count:
        warnings.append(
            AnalysisWarning(
                code="FOUNDATION_THICKNESS_REQUIRED",
                message=(
                    "Radye sınırı okundu ancak açık radye kalınlığı bulunamadı. Kalınlık "
                    "kesit/temel detayından doğrulanmadan temel betonu kesin toplama giremez."
                ),
                source_id=source.id,
            )
        )
    return FoundationPlanResult(elements, warnings, True)
