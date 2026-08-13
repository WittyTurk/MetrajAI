from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from enum import StrEnum

from pydantic import BaseModel, Field

from .contracts import DetectedElement, SourceFile

COMPARABLE_TYPES = {
    "column",
    "beam",
    "slab",
    "shear_wall",
    "raft",
    "foundation",
    "stair",
    "slab_opening",
}
MEASUREMENT_KEYS = {
    "column": ("width_m", "depth_m", "height_m"),
    "beam": ("length_m", "width_m", "height_m"),
    "slab": ("area_m2", "thickness_m", "void_area_m2"),
    "shear_wall": ("length_m", "thickness_m", "height_m", "void_area_m2"),
    "raft": ("area_m2", "perimeter_m", "thickness_m", "void_area_m2"),
    "foundation": ("area_m2", "perimeter_m", "thickness_m", "void_area_m2"),
    "stair": (
        "plan_area_m2",
        "horizontal_run_m",
        "total_rise_m",
        "waist_thickness_m",
        "step_volume_m3",
        "landing_volume_m3",
    ),
    "slab_opening": ("area_m2", "perimeter_m"),
}


class RevisionChangeKind(StrEnum):
    ADDED = "added"
    DELETED = "deleted"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


class RevisionElementChange(BaseModel):
    kind: RevisionChangeKind
    element_type: str
    floor: str
    label: str = ""
    old_element_id: str = ""
    new_element_id: str = ""
    old_measurements: dict[str, float] = Field(default_factory=dict)
    new_measurements: dict[str, float] = Field(default_factory=dict)
    changed_measurements: dict[str, tuple[float | None, float | None]] = Field(default_factory=dict)
    match_method: str = ""
    match_confidence: float = 0.0


class RevisionComparison(BaseModel):
    old_source_id: str
    new_source_id: str
    old_revision: str
    new_revision: str
    summary: dict[str, int]
    changes: list[RevisionElementChange]
    warnings: list[str] = Field(default_factory=list)


def _label(element: DetectedElement) -> str:
    return str(element.properties.get("element_label", "")).strip().upper()


def _center(element: DetectedElement) -> tuple[float, float] | None:
    box = element.geometry.bbox
    if box is None:
        return None
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _measurement_changes(
    old: DetectedElement,
    new: DetectedElement,
) -> dict[str, tuple[float | None, float | None]]:
    result: dict[str, tuple[float | None, float | None]] = {}
    for key in MEASUREMENT_KEYS[old.element_type]:
        old_value = old.measurements.get(key)
        new_value = new.measurements.get(key)
        if old_value is None and new_value is None:
            continue
        if old_value is None or new_value is None:
            result[key] = old_value, new_value
            continue
        tolerance = max(1e-4, abs(old_value) * 0.001)
        if abs(old_value - new_value) > tolerance:
            result[key] = old_value, new_value
    return result


def _change(
    old: DetectedElement | None,
    new: DetectedElement | None,
    *,
    method: str,
    confidence: float,
) -> RevisionElementChange:
    element = new or old
    assert element is not None
    changes: dict[str, tuple[float | None, float | None]]
    if old is None:
        kind = RevisionChangeKind.ADDED
        changes = {}
    elif new is None:
        kind = RevisionChangeKind.DELETED
        changes = {}
    else:
        changes = _measurement_changes(old, new)
        kind = RevisionChangeKind.MODIFIED if changes else RevisionChangeKind.UNCHANGED
    return RevisionElementChange(
        kind=kind,
        element_type=element.element_type,
        floor=element.floor,
        label=_label(element),
        old_element_id=old.id if old else "",
        new_element_id=new.id if new else "",
        old_measurements=dict(old.measurements) if old else {},
        new_measurements=dict(new.measurements) if new else {},
        changed_measurements=changes,
        match_method=method,
        match_confidence=confidence,
    )


def _translation(
    old: list[DetectedElement],
    new: list[DetectedElement],
) -> tuple[float, float]:
    old_centers = [point for item in old if (point := _center(item)) is not None]
    new_centers = [point for item in new if (point := _center(item)) is not None]
    if not old_centers or not new_centers:
        return 0.0, 0.0
    return (
        statistics.median(point[0] for point in new_centers)
        - statistics.median(point[0] for point in old_centers),
        statistics.median(point[1] for point in new_centers)
        - statistics.median(point[1] for point in old_centers),
    )


def _match_group(
    old: list[DetectedElement],
    new: list[DetectedElement],
) -> list[RevisionElementChange]:
    changes: list[RevisionElementChange] = []
    unmatched_old = {item.id: item for item in old}
    unmatched_new = {item.id: item for item in new}
    old_labels: dict[str, list[DetectedElement]] = defaultdict(list)
    new_labels: dict[str, list[DetectedElement]] = defaultdict(list)
    for item in old:
        if label := _label(item):
            old_labels[label].append(item)
    for item in new:
        if label := _label(item):
            new_labels[label].append(item)
    for label in sorted(set(old_labels) & set(new_labels)):
        if len(old_labels[label]) != 1 or len(new_labels[label]) != 1:
            continue
        old_item = old_labels[label][0]
        new_item = new_labels[label][0]
        changes.append(_change(old_item, new_item, method="unique_label", confidence=1.0))
        unmatched_old.pop(old_item.id)
        unmatched_new.pop(new_item.id)

    old_rest = list(unmatched_old.values())
    new_rest = list(unmatched_new.values())
    shift_x, shift_y = _translation(old_rest, new_rest)
    candidates: list[tuple[float, str, str]] = []
    for old_item in old_rest:
        old_center = _center(old_item)
        if old_center is None:
            continue
        aligned = old_center[0] + shift_x, old_center[1] + shift_y
        for new_item in new_rest:
            new_center = _center(new_item)
            if new_center is None:
                continue
            distance = math.dist(aligned, new_center)
            if distance <= 2.0:
                candidates.append((distance, old_item.id, new_item.id))
    for distance, old_id, new_id in sorted(candidates):
        if old_id not in unmatched_old or new_id not in unmatched_new:
            continue
        old_item = unmatched_old.pop(old_id)
        new_item = unmatched_new.pop(new_id)
        confidence = max(0.55, 0.95 - distance / 5.0)
        changes.append(
            _change(old_item, new_item, method="translated_geometry", confidence=confidence)
        )

    changes.extend(
        _change(item, None, method="unmatched", confidence=1.0) for item in unmatched_old.values()
    )
    changes.extend(
        _change(None, item, method="unmatched", confidence=1.0) for item in unmatched_new.values()
    )
    return changes


def compare_revisions(
    old_source: SourceFile,
    new_source: SourceFile,
    elements: list[DetectedElement],
) -> RevisionComparison:
    if old_source.id == new_source.id:
        raise ValueError("Revizyon karşılaştırması için iki farklı kaynak seçin")
    if old_source.discipline != new_source.discipline:
        raise ValueError("Karşılaştırılan kaynakların disiplinleri aynı olmalıdır")
    old_elements = [
        item
        for item in elements
        if item.source_id == old_source.id and item.element_type in COMPARABLE_TYPES
    ]
    new_elements = [
        item
        for item in elements
        if item.source_id == new_source.id and item.element_type in COMPARABLE_TYPES
    ]
    grouped_old: dict[tuple[str, str], list[DetectedElement]] = defaultdict(list)
    grouped_new: dict[tuple[str, str], list[DetectedElement]] = defaultdict(list)
    for item in old_elements:
        grouped_old[item.element_type, item.floor].append(item)
    for item in new_elements:
        grouped_new[item.element_type, item.floor].append(item)
    changes: list[RevisionElementChange] = []
    for key in sorted(set(grouped_old) | set(grouped_new)):
        changes.extend(_match_group(grouped_old[key], grouped_new[key]))
    order = {
        RevisionChangeKind.MODIFIED: 0,
        RevisionChangeKind.ADDED: 1,
        RevisionChangeKind.DELETED: 2,
        RevisionChangeKind.UNCHANGED: 3,
    }
    changes.sort(key=lambda item: (order[item.kind], item.element_type, item.floor, item.label))
    counts = Counter(item.kind.value for item in changes)
    warnings: list[str] = []
    if not old_elements or not new_elements:
        warnings.append(
            "Kaynaklardan en az birinde karşılaştırılabilir taşıyıcı eleman tespiti yok."
        )
    low_confidence = sum(
        item.match_method == "translated_geometry" and item.match_confidence < 0.8
        for item in changes
    )
    if low_confidence:
        warnings.append(
            f"{low_confidence} geometrik eşleşmenin güveni düşük; çizim üzerinde kontrol edin."
        )
    return RevisionComparison(
        old_source_id=old_source.id,
        new_source_id=new_source.id,
        old_revision=old_source.revision,
        new_revision=new_source.revision,
        summary={kind.value: counts[kind.value] for kind in RevisionChangeKind},
        changes=changes,
        warnings=warnings,
    )
