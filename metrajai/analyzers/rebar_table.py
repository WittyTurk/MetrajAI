from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ezdxf import bbox

from ..contracts import (
    AnalysisWarning,
    DetectedElement,
    Discipline,
    Geometry,
    ReviewStatus,
    SourceFile,
)

BEAM_LABEL = re.compile(r"\bKZ\d{1,3}\b", re.IGNORECASE)
REQUIRED_HEADERS = ("Poz", "Adet", "Çap", "Uzunluk (cm)", "Ağırlık (Kg)")


@dataclass(frozen=True)
class VisibleText:
    value: str
    x: float
    y: float


@dataclass(frozen=True)
class RebarRow:
    position: int
    count: int
    diameter_mm: int
    length_cm: float
    declared_weight_kg: float

    @property
    def calculated_weight_kg(self) -> float:
        return self.length_cm / 100.0 * self.count * self.diameter_mm**2 / 162.0


@dataclass(frozen=True)
class RebarTable:
    entity: Any
    box: tuple[float, float, float, float]
    rows: tuple[RebarRow, ...]
    scope_labels: tuple[str, ...]
    scope_handle: str

    @property
    def declared_total_kg(self) -> float:
        return sum(row.declared_weight_kg for row in self.rows)

    @property
    def calculated_total_kg(self) -> float:
        return sum(row.calculated_weight_kg for row in self.rows)


def _visible_texts(entity) -> list[VisibleText]:
    values: list[VisibleText] = []
    try:
        children = entity.virtual_entities()
    except Exception:
        return values
    for child in children:
        if child.dxftype() == "TEXT":
            value = str(child.dxf.text).strip()
        elif child.dxftype() == "MTEXT":
            value = str(child.plain_text() or "").strip()
        else:
            continue
        if not value:
            continue
        point = child.dxf.insert
        values.append(VisibleText(value, float(point.x), float(point.y)))
    return values


def _box(entity) -> tuple[float, float, float, float] | None:
    try:
        extents = bbox.extents([entity], fast=True)
    except Exception:
        return None
    if not extents.has_data:
        return None
    return (
        float(extents.extmin.x),
        float(extents.extmin.y),
        float(extents.extmax.x),
        float(extents.extmax.y),
    )


def _box_distance(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    dx = max(first[0] - second[2], second[0] - first[2], 0.0)
    dy = max(first[1] - second[3], second[1] - first[3], 0.0)
    return math.hypot(dx, dy)


def _number(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def _table_rows(texts: list[VisibleText]) -> tuple[RebarRow, ...]:
    header_points: dict[str, VisibleText] = {}
    for header in REQUIRED_HEADERS:
        match = next((text for text in texts if text.value == header), None)
        if match is None:
            return ()
        header_points[header] = match

    grouped: dict[float, list[VisibleText]] = defaultdict(list)
    header_y = min(point.y for point in header_points.values())
    for text in texts:
        if text.y >= header_y - 0.5 or _number(text.value) is None:
            continue
        grouped[round(text.y, 1)].append(text)

    rows: list[RebarRow] = []
    for values in grouped.values():
        numeric_values = sorted(
            ((value.x, number) for value in values if (number := _number(value.value)) is not None),
            key=lambda item: item[0],
        )
        # The graphical "Tip" column contains geometry rather than text. A valid
        # schedule row therefore exposes exactly five numeric text cells in the
        # same left-to-right order as REQUIRED_HEADERS.
        if len(numeric_values) != len(REQUIRED_HEADERS):
            continue
        position, count, diameter, length_cm, weight = (number for _, number in numeric_values)
        if not (
            position.is_integer()
            and count.is_integer()
            and diameter.is_integer()
            and 1 <= position <= 999
            and 1 <= count <= 10000
            and 6 <= diameter <= 50
            and length_cm > 10
            and weight > 0
        ):
            continue
        rows.append(
            RebarRow(
                position=int(position),
                count=int(count),
                diameter_mm=int(diameter),
                length_cm=length_cm,
                declared_weight_kg=weight,
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.diameter_mm, row.position), reverse=True))


def _scope_candidates(
    document,
) -> list[tuple[Any, tuple[float, float, float, float], tuple[str, ...]]]:
    candidates = []
    for entity in document.modelspace().query("INSERT"):
        labels = tuple(
            sorted(
                {
                    match.group(0).upper()
                    for text in _visible_texts(entity)
                    for match in BEAM_LABEL.finditer(text.value)
                }
            )
        )
        entity_box = _box(entity)
        if entity_box is None:
            continue
        width = entity_box[2] - entity_box[0]
        height = entity_box[3] - entity_box[1]
        # A scope note is a compact one/two-line KZ list. Full reinforcement
        # detail blocks may also contain several KZ labels, but their tall
        # geometry must never be mistaken for a table scope.
        if len(labels) >= 2 and width >= max(height * 2, 1.0):
            candidates.append((entity, entity_box, labels))
    return candidates


def _rebar_tables(document) -> list[RebarTable]:
    scopes = _scope_candidates(document)
    tables: list[RebarTable] = []
    for entity in document.modelspace().query("INSERT"):
        texts = _visible_texts(entity)
        rows = _table_rows(texts)
        table_box = _box(entity)
        if not rows or table_box is None:
            continue
        nearby_scopes = sorted(
            (
                _box_distance(table_box, scope_box),
                scope_entity,
                labels,
            )
            for scope_entity, scope_box, labels in scopes
            if scope_entity is not entity and _box_distance(table_box, scope_box) <= 250
        )
        if not nearby_scopes:
            continue
        _, scope_entity, labels = nearby_scopes[0]
        tables.append(
            RebarTable(
                entity=entity,
                box=table_box,
                rows=rows,
                scope_labels=labels,
                scope_handle=str(scope_entity.dxf.handle),
            )
        )
    return tables


def _table_distance(table: RebarTable, plan_roots: list[tuple[float, float]]) -> float:
    center_x = (table.box[0] + table.box[2]) / 2.0
    center_y = (table.box[1] + table.box[3]) / 2.0
    return min(
        abs(center_y - root_y) + abs(center_x - root_x) * 0.05 for root_x, root_y in plan_roots
    )


def _identity(source: SourceFile, table_handle: str, position: int) -> str:
    digest = hashlib.sha1(
        f"{source.sha256}:beam_rebar:{table_handle}:{position}".encode()
    ).hexdigest()[:20]
    return f"elm_{digest}"


def _table_signature(table: RebarTable) -> tuple[tuple[int, int, int, float], ...]:
    return tuple((row.position, row.count, row.diameter_mm, row.length_cm) for row in table.rows)


def _revision_group(source: SourceFile, labels: tuple[str, ...]) -> str:
    digest = hashlib.sha1(
        f"{source.sha256}:beam_rebar_revision:{','.join(labels)}".encode()
    ).hexdigest()[:16]
    return f"rebar_revision_{digest}"


def extract_beam_rebar_table(
    document,
    source: SourceFile,
    plan_roots: list[tuple[float, float]],
    detected_beam_labels: set[str],
    geometry_scale: float,
) -> tuple[list[DetectedElement], list[AnalysisWarning]]:
    tables = _rebar_tables(document)
    beam_tables = [table for table in tables if set(table.scope_labels) & detected_beam_labels]
    if not beam_tables or not plan_roots:
        return [], []

    max_scope = max(len(set(table.scope_labels) & detected_beam_labels) for table in beam_tables)
    broad_tables = [
        table
        for table in beam_tables
        if len(set(table.scope_labels) & detected_beam_labels) == max_scope
    ]
    by_signature: dict[tuple[tuple[int, int, int, float], ...], RebarTable] = {}
    for table in broad_tables:
        signature = _table_signature(table)
        existing = by_signature.get(signature)
        if existing is None or _table_distance(table, plan_roots) < _table_distance(
            existing, plan_roots
        ):
            by_signature[signature] = table
    candidates = sorted(
        by_signature.values(),
        key=lambda table: _table_distance(table, plan_roots),
    )
    revision_required = len(candidates) > 1
    candidate_summaries = [
        {
            "label": chr(ord("A") + index),
            "table_handle": str(table.entity.dxf.handle),
            "declared_total_kg": round(table.declared_total_kg, 2),
            "calculated_total_kg": round(table.calculated_total_kg, 2),
            "row_count": len(table.rows),
            "scope_labels": list(table.scope_labels),
        }
        for index, table in enumerate(candidates)
    ]
    group = _revision_group(source, candidates[0].scope_labels)
    elements: list[DetectedElement] = []
    for candidate_index, table in enumerate(candidates):
        scaled_box: tuple[float, float, float, float] = (
            round(table.box[0] * geometry_scale, 6),
            round(table.box[1] * geometry_scale, 6),
            round(table.box[2] * geometry_scale, 6),
            round(table.box[3] * geometry_scale, 6),
        )
        table_handle = str(table.entity.dxf.handle)
        candidate_label = chr(ord("A") + candidate_index)
        for row in table.rows:
            difference = row.calculated_weight_kg - row.declared_weight_kg
            elements.append(
                DetectedElement(
                    id=_identity(source, table_handle, row.position),
                    source_id=source.id,
                    discipline=Discipline.STRUCTURAL,
                    element_type="rebar",
                    floor=source.floor,
                    layer=str(table.entity.dxf.layer),
                    block_name=str(table.entity.dxf.name),
                    source_handle=f"{table_handle}:poz-{row.position}",
                    geometry=Geometry(kind="rebar_schedule_row", bbox=scaled_box),
                    measurements={
                        "length_m": round(row.length_cm / 100.0, 6),
                        "count": float(row.count),
                        "diameter_mm": float(row.diameter_mm),
                    },
                    properties={
                        "quantity_kind": "rebar",
                        "element_label": (
                            f"Revizyon {candidate_label} · Kiriş donatısı · Poz {row.position}"
                        ),
                        "position_number": row.position,
                        "rebar_scope_labels": list(table.scope_labels),
                        "declared_weight_kg": row.declared_weight_kg,
                        "calculated_weight_kg": round(row.calculated_weight_kg, 4),
                        "weight_difference_kg": round(difference, 4),
                        "table_declared_total_kg": round(table.declared_total_kg, 2),
                        "table_calculated_total_kg": round(table.calculated_total_kg, 2),
                        "table_handle": table_handle,
                        "scope_handle": table.scope_handle,
                        "revision_group": group,
                        "revision_candidate_label": candidate_label,
                        "revision_selected": not revision_required,
                        "revision_candidates": candidate_summaries,
                        "evidence_method": "explicit_rebar_takeoff_table",
                    },
                    required_inputs=["length_m", "count", "diameter_mm"],
                    confidence=0.94,
                    review_status=(
                        ReviewStatus.NEEDS_REVIEW if revision_required else ReviewStatus.PENDING
                    ),
                    issues=(
                        ["blocking:rebar_revision_selection_required"] if revision_required else []
                    ),
                )
            )

    primary = candidates[0]
    if revision_required:
        alternatives = "; ".join(
            f"Revizyon {item['label']}: {item['declared_total_kg']:.2f} kg"
            for item in candidate_summaries
        )
        warnings = [
            AnalysisWarning(
                code="BEAM_REBAR_REVISION_REQUIRED",
                message=(
                    f"Aynı {primary.scope_labels[0]}–{primary.scope_labels[-1]} kapsamı için "
                    f"{len(candidates)} farklı donatı tablosu bulundu ({alternatives}). "
                    "Mühendis revizyonu seçmeden hiçbir donatı satırı kesin toplama giremez."
                ),
                source_id=source.id,
            )
        ]
    else:
        warnings = [
            AnalysisWarning(
                code="BEAM_REBAR_TABLE_LINKED",
                message=(
                    f"Kiriş donatı metraj tablosundan {len(primary.rows)} açık satır okundu; "
                    f"kapsam {primary.scope_labels[0]}–{primary.scope_labels[-1]}. "
                    f"Pafta toplamı {primary.declared_total_kg:.2f} kg, formülle yeniden "
                    f"hesaplanan net toplam {primary.calculated_total_kg:.2f} kg."
                ),
                source_id=source.id,
                severity="info",
            )
        ]
    missing_scope = sorted(detected_beam_labels - set(primary.scope_labels))
    if missing_scope:
        warnings.append(
            AnalysisWarning(
                code="BEAM_REBAR_SCOPE_PARTIAL",
                message=(
                    "Donatı tablosu adayları şu kirişleri kapsamıyor: "
                    + ", ".join(missing_scope)
                    + ". Bu elemanlar için detay geometrisi çözülmeden donatı miktarı "
                    "kesin toplama eklenmeyecek."
                ),
                source_id=source.id,
            )
        )
    return elements, warnings
