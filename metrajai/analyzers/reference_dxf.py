from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable
from typing import Any

from ezdxf import bbox
from ezdxf.path import from_hatch, make_path

from ..contracts import (
    AnalysisWarning,
    DetectedElement,
    DrawingUnit,
    Geometry,
    ReviewStatus,
    SourceFile,
)
from ..units import unit_scale

REFERENCE_APPID = "METRAJAI_REF"

REQUIRED_INPUTS: dict[str, tuple[str, ...]] = {
    "room": ("area_m2", "perimeter_m"),
    "wall": ("length_m", "height_m"),
    "door": ("count", "width_m", "height_m"),
    "window": ("count", "width_m", "height_m"),
    "column": ("width_m", "depth_m", "height_m"),
    "beam": ("length_m", "width_m", "height_m"),
    "shear_wall": ("length_m", "thickness_m", "height_m"),
    "slab": ("area_m2", "thickness_m"),
    "foundation": ("area_m2", "perimeter_m", "thickness_m"),
    "stair": ("plan_area_m2", "horizontal_run_m", "total_rise_m", "waist_thickness_m"),
}


def _walk(entities: Iterable, *, path: str = "", inherited_layer: str = "", depth: int = 0):
    if depth > 8:
        return
    for index, entity in enumerate(entities):
        handle = str(getattr(entity.dxf, "handle", "") or f"v{index}")
        current_path = f"{path}/{handle}" if path else handle
        own_layer = str(getattr(entity.dxf, "layer", "") or "")
        layer = inherited_layer if own_layer == "0" and inherited_layer else own_layer
        yield entity, current_path, layer
        if entity.dxftype() != "INSERT":
            continue
        try:
            children = list(entity.virtual_entities())
        except Exception:
            continue
        yield from _walk(children, path=current_path, inherited_layer=layer, depth=depth + 1)


def _metadata(entity) -> dict[str, str]:
    try:
        tags = entity.get_xdata(REFERENCE_APPID)
    except Exception:
        return {}
    values: dict[str, str] = {}
    for tag in tags:
        if tag.code != 1000:
            continue
        key, separator, value = str(tag.value).partition("=")
        if separator and key:
            values[key] = value
    return values


def _number(metadata: dict[str, str], key: str) -> float | None:
    value = metadata.get(key)
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def _geometry(entity, factor: float) -> Geometry:
    points: list[tuple[float, float]] = []
    try:
        if entity.dxftype() == "LWPOLYLINE":
            points = [
                (float(point.x) * factor, float(point.y) * factor)
                for point in make_path(entity).flattening(distance=max(0.001 / factor, 1e-6))
            ]
        elif entity.dxftype() == "HATCH":
            points = [
                (float(point.x) * factor, float(point.y) * factor)
                for path in from_hatch(entity)
                for point in path.flattening(distance=max(0.001 / factor, 1e-6))
            ]
        elif entity.dxftype() == "INSERT":
            point = entity.dxf.insert
            points = [(float(point.x) * factor, float(point.y) * factor)]
    except Exception:
        points = []
    try:
        bounds = bbox.extents([entity], fast=True)
    except Exception:
        bounds = None
    entity_box = None
    if bounds is not None and bounds.has_data:
        entity_box = (
            float(bounds.extmin.x) * factor,
            float(bounds.extmin.y) * factor,
            float(bounds.extmax.x) * factor,
            float(bounds.extmax.y) * factor,
        )
    return Geometry(kind=f"reference_{entity.dxftype().lower()}", points=points, bbox=entity_box)


def extract_reference_dxf(
    document,
    source: SourceFile,
    drawing_unit: DrawingUnit,
) -> tuple[list[DetectedElement], list[AnalysisWarning], bool]:
    """Read deterministic IFC-linked reference elements from DXF XDATA.

    This path is intentionally limited to laboratory DXFs carrying the registered
    ``METRAJAI_REF`` application id. Ordinary project drawings never enter it.
    """

    raw: list[tuple[Any, str, str, dict[str, str]]] = []
    for entity, path, layer in _walk(document.modelspace()):
        metadata = _metadata(entity)
        if metadata.get("guid") and metadata.get("type"):
            raw.append((entity, path, layer, metadata))
    if not raw:
        return [], [], False

    factor = unit_scale(drawing_unit) if drawing_unit != DrawingUnit.UNKNOWN else 1.0
    seen: set[str] = set()
    duplicate_count = 0
    elements: list[DetectedElement] = []
    for entity, path, layer, metadata in raw:
        reference_guid = metadata["guid"]
        if reference_guid in seen:
            duplicate_count += 1
            continue
        seen.add(reference_guid)
        if metadata.get("discipline") not in {"", source.discipline.value}:
            continue
        element_type = metadata["type"]
        required = list(REQUIRED_INPUTS.get(element_type, ()))
        measurements = {
            key: value
            for key in (
                "count",
                "length_m",
                "width_m",
                "depth_m",
                "height_m",
                "thickness_m",
                "area_m2",
                "perimeter_m",
                "plan_area_m2",
                "horizontal_run_m",
                "total_rise_m",
                "waist_thickness_m",
                "volume_m3",
            )
            if (value := _number(metadata, key)) is not None
        }
        if element_type in {"door", "window"}:
            measurements.setdefault("count", 1.0)
        missing = [key for key in required if measurements.get(key, 0.0) <= 0]
        issues = [f"missing:{key}" for key in missing]
        declared_unit = metadata.get("dxf_unit", "mm")
        if drawing_unit == DrawingUnit.UNKNOWN:
            issues.extend(
                ["unit_confirmation_required", "blocking:reference_unit_confirmation_required"]
            )
        elif declared_unit != drawing_unit.value:
            issues.append("blocking:drawing_unit_evidence_mismatch")
        status = ReviewStatus.PENDING if not issues else ReviewStatus.NEEDS_REVIEW
        identity = f"{source.sha256}|reference|{reference_guid}"
        elements.append(
            DetectedElement(
                id="elm_" + hashlib.sha256(identity.encode()).hexdigest()[:32],
                source_id=source.id,
                discipline=source.discipline,
                element_type=element_type,
                floor=metadata.get("storey", source.floor),
                layer=layer,
                block_name=str(getattr(entity.dxf, "name", "") or ""),
                source_handle=path,
                geometry=_geometry(entity, factor),
                measurements=measurements,
                properties={
                    "quantity_kind": element_type,
                    "reference_guid": reference_guid,
                    "reference_dataset": metadata.get("dataset", ""),
                    "reference_source_id": metadata.get("source", ""),
                    "reference_ifc_class": metadata.get("ifc_class", ""),
                    "reference_name": metadata.get("name", ""),
                    "reference_evidence": "ifc_xdata",
                },
                required_inputs=required,
                confidence=1.0 if not issues else 0.7,
                review_status=status,
                issues=issues,
            )
        )

    warnings = [
        AnalysisWarning(
            code="REFERENCE_DXF_METADATA_LINKED",
            message=(
                f"{len(elements)} kontrollü DXF elemanı IFC GlobalId kanıtıyla eşleştirildi."
            ),
            source_id=source.id,
            severity="info",
        )
    ]
    if duplicate_count:
        warnings.append(
            AnalysisWarning(
                code="REFERENCE_DXF_DUPLICATES_SKIPPED",
                message=(
                    f"Aynı IFC GlobalId değerini taşıyan {duplicate_count} kontrollü kopya "
                    "yeniden sayılmadı."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    if drawing_unit == DrawingUnit.UNKNOWN:
        warnings.append(
            AnalysisWarning(
                code="REFERENCE_DXF_UNIT_CONFIRMATION_REQUIRED",
                message=(
                    "Kontrollü DXF birimi eksik; IFC kanıtı saklandı ancak kesin miktarlar "
                    "kullanıcı birim onayına kadar kilitlendi."
                ),
                source_id=source.id,
                severity="error",
            )
        )
    elif any("blocking:drawing_unit_evidence_mismatch" in element.issues for element in elements):
        warnings.append(
            AnalysisWarning(
                code="REFERENCE_DXF_UNIT_EVIDENCE_MISMATCH",
                message=(
                    "DXF başlık birimi ile IFC türetim kanıtı çelişiyor; kesin miktarlar "
                    "kullanıcı birim onayına kadar kilitlendi."
                ),
                source_id=source.id,
                severity="error",
            )
        )
    return elements, warnings, True
