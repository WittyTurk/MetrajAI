from __future__ import annotations

import hashlib
import math
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.math import area as polygon_area
from ezdxf.path import from_hatch, make_path
from ezdxf.path.nesting import make_polygon_structure

from ..contracts import (
    AnalysisWarning,
    DetectedElement,
    Discipline,
    DrawingUnit,
    Geometry,
    ReviewStatus,
    SheetKind,
    SourceFile,
)
from ..units import unit_from_insunits, unit_scale
from .multiview_structural import (
    MultiviewStructuralResult,
    extract_multiview_structural_plans,
    filter_multiview_generic_elements,
)
from .structural_plan import extract_structural_plans


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(character for character in text if not unicodedata.combining(character)).upper()
    return " ".join(text.split())


@dataclass(frozen=True)
class DetectionRule:
    element_type: str
    tokens: tuple[str, ...]
    entity_types: tuple[str, ...]
    required_inputs: tuple[str, ...]
    quantity_kind: str


RULES: dict[Discipline, tuple[DetectionRule, ...]] = {
    Discipline.STRUCTURAL: (
        DetectionRule(
            "column",
            ("KOLON", "COLUMN"),
            ("LWPOLYLINE", "INSERT"),
            ("width_m", "depth_m", "height_m"),
            "column",
        ),
        DetectionRule(
            "beam",
            ("KIRIS", "BEAM"),
            ("LWPOLYLINE",),
            ("length_m", "width_m", "height_m"),
            "beam",
        ),
        DetectionRule(
            "shear_wall",
            ("PERDE", "SHEAR"),
            ("LWPOLYLINE",),
            ("length_m", "thickness_m", "height_m"),
            "shear_wall",
        ),
        DetectionRule(
            "slab", ("DOSEME", "SLAB"), ("LWPOLYLINE", "HATCH"), ("area_m2", "thickness_m"), "slab"
        ),
        DetectionRule(
            "raft",
            ("RADYE", "RAFT"),
            ("LWPOLYLINE", "HATCH"),
            ("area_m2", "perimeter_m", "thickness_m"),
            "raft",
        ),
        DetectionRule(
            "foundation",
            ("TEMEL", "FOUNDATION", "FOOTING", "MUNFERIT", "TEKIL", "SUREKLI"),
            ("LWPOLYLINE", "HATCH"),
            ("area_m2", "perimeter_m", "thickness_m"),
            "foundation",
        ),
        DetectionRule(
            "stair",
            ("MERDIVEN", "STAIR"),
            ("LWPOLYLINE", "HATCH"),
            ("plan_area_m2", "horizontal_run_m", "total_rise_m", "waist_thickness_m"),
            "stair",
        ),
        DetectionRule(
            "rebar",
            ("DONATI", "REBAR"),
            ("LINE", "LWPOLYLINE", "INSERT"),
            ("length_m", "count", "diameter_mm"),
            "rebar",
        ),
    ),
    Discipline.ARCHITECTURAL: (
        DetectionRule(
            "wall",
            ("DUVAR", "WALL", "SIVA"),
            ("LINE", "LWPOLYLINE"),
            ("length_m", "height_m"),
            "wall",
        ),
        DetectionRule("door", ("KAPI", "DOOR"), ("INSERT",), ("count",), "count"),
        DetectionRule("window", ("PENCERE", "WINDOW"), ("INSERT",), ("count",), "count"),
        DetectionRule(
            "room",
            ("MAHAL", "ODA", "ROOM", "ALAN"),
            ("LWPOLYLINE", "HATCH"),
            ("area_m2", "perimeter_m"),
            "room",
        ),
        DetectionRule(
            "finish_area",
            ("KAPLAMA", "TAVAN", "ZEMIN", "FLOOR FINISH", "CEILING"),
            ("LWPOLYLINE", "HATCH"),
            ("area_m2",),
            "area",
        ),
    ),
    Discipline.LANDSCAPE: (
        DetectionRule(
            "landscape_area",
            ("PEYZAJ", "CIM", "YESIL", "PARK", "BAHCE", "ALAN"),
            ("LWPOLYLINE", "HATCH"),
            ("area_m2",),
            "area",
        ),
        DetectionRule(
            "landscape_linear",
            ("BORDUR", "YOL", "YURUYUS", "KALDIRIM", "DRENAJ", "ALTYAPI", "HAT"),
            ("LINE", "LWPOLYLINE"),
            ("length_m",),
            "length",
        ),
        DetectionRule(
            "landscape_item",
            ("AGAC", "BITKI", "FURNITURE", "ROGAR", "EKIPMAN", "MOBILYA"),
            ("INSERT",),
            ("count",),
            "count",
        ),
    ),
    Discipline.MECHANICAL: (
        DetectionRule("pipe", ("BORU", "PIPE"), ("LINE", "LWPOLYLINE"), ("length_m",), "length"),
        DetectionRule("duct", ("KANAL", "DUCT"), ("LINE", "LWPOLYLINE"), ("length_m",), "length"),
        DetectionRule(
            "mechanical_equipment", ("CIHAZ", "EQUIP", "MEKANIK"), ("INSERT",), ("count",), "count"
        ),
        DetectionRule(
            "mechanical_fitting",
            ("FITTING", "DIRSEK", "TE", "REDUKSIYON", "VANA"),
            ("INSERT",),
            ("count",),
            "count",
        ),
    ),
    Discipline.ELECTRICAL: (
        DetectionRule("cable", ("KABLO", "CABLE"), ("LINE", "LWPOLYLINE"), ("length_m",), "length"),
        DetectionRule(
            "cable_tray", ("TAVA", "TRAY"), ("LINE", "LWPOLYLINE"), ("length_m",), "length"
        ),
        DetectionRule("light", ("AYDINLATMA", "LIGHT", "LAMBA"), ("INSERT",), ("count",), "count"),
        DetectionRule("socket", ("PRIZ", "SOCKET"), ("INSERT",), ("count",), "count"),
        DetectionRule("panel", ("PANO", "PANEL"), ("INSERT",), ("count",), "count"),
        DetectionRule(
            "electrical_item",
            ("ANAHTAR", "SENSOR", "DETEKTOR", "CIHAZ"),
            ("INSERT",),
            ("count",),
            "count",
        ),
    ),
}


class DxfAnalyzer:
    """Conservative DXF detector: never invents missing physical dimensions."""

    def analyze(
        self,
        source: SourceFile,
        source_path: str | Path,
    ) -> tuple[list[DetectedElement], list[AnalysisWarning], DrawingUnit]:
        path = Path(source_path)
        if path.suffix.lower() != ".dxf":
            return (
                [],
                [
                    AnalysisWarning(
                        code="SCHEDULE_ONLY",
                        message=(
                            f"{source.original_name} çizelge/referans olarak saklandı; "
                            "tek başına geometrik miktar üretmez."
                        ),
                        source_id=source.id,
                        severity="info",
                    )
                ],
                source.detected_unit,
            )

        document = ezdxf.readfile(path)
        detected_unit = unit_from_insunits(document.header.get("$INSUNITS", 0))
        if source.discipline == Discipline.STRUCTURAL and source.sheet_kind in {
            SheetKind.DETAIL,
            SheetKind.SECTION,
            SheetKind.ELEVATION,
            SheetKind.OTHER,
        }:
            return (
                [],
                [
                    AnalysisWarning(
                        code="REFERENCE_SHEET_EXCLUDED_FROM_COUNTS",
                        message=(
                            f"{source.original_name} '{source.sheet_kind.value}' paftası "
                            "olarak eşlendi; açıklama ve detay geometrileri fiziksel eleman "
                            "adedine eklenmedi."
                        ),
                        source_id=source.id,
                        severity="info",
                    )
                ],
                detected_unit,
            )
        chosen_unit = source.drawing_unit if source.unit_confirmed else detected_unit
        warnings: list[AnalysisWarning] = []
        if chosen_unit == DrawingUnit.UNKNOWN:
            warnings.append(
                AnalysisWarning(
                    code="UNIT_CONFIRMATION_REQUIRED",
                    message=(
                        f"{source.original_name}: DXF birimi eksik veya desteklenmiyor. "
                        "Metraj onayından önce mm, cm veya m seçin."
                    ),
                    source_id=source.id,
                    severity="error",
                )
            )
            scale: float | None = None
        else:
            scale = unit_scale(chosen_unit)

        if source.discipline == Discipline.ARCHITECTURAL:
            warnings.append(
                AnalysisWarning(
                    code="ARCHITECTURAL_ENGINE_REVIEW_MODE",
                    message=(
                        f"{source.original_name} içindeki açık duvar merkez hatları, mahal ve "
                        "kaplama sınırları inceleme adayı olarak çıkarıldı. Mühendis onayı "
                        "olmayan mimari elemanlar kesin metraja girmez."
                    ),
                    source_id=source.id,
                    severity="info",
                )
            )

        elements: list[DetectedElement] = []
        generic_elements: list[DetectedElement] = []
        specialized_types: set[str] = set()
        specialized_activated = False
        multiview = MultiviewStructuralResult([], [], [], False)
        if source.discipline == Discipline.STRUCTURAL:
            structural = extract_structural_plans(document, source, chosen_unit)
            if structural.activated:
                specialized_activated = True
                elements.extend(structural.elements)
                warnings.extend(structural.warnings)
                specialized_types.update(("column", "beam", "slab"))
                if any(element.element_type == "rebar" for element in structural.elements):
                    specialized_types.add("rebar")
            elif scale is not None:
                multiview = extract_multiview_structural_plans(
                    document,
                    source,
                    chosen_unit,
                )
                if multiview.activated:
                    specialized_activated = True
                    elements.extend(multiview.elements)
                    warnings.extend(multiview.warnings)
                    specialized_types.update(element.element_type for element in multiview.elements)
        for entity in document.modelspace():
            rule = self._match_rule(source.discipline, entity.dxf.layer, entity.dxftype())
            if rule is None or rule.element_type in specialized_types:
                continue
            element = self._element_from_entity(entity, source, rule, scale)
            if element is not None:
                generic_elements.append(element)

        if source.discipline == Discipline.STRUCTURAL and scale is not None:
            region_warnings: list[AnalysisWarning]
            if multiview.blocked:
                generic_elements = []
                region_warnings = []
            elif multiview.activated:
                generic_elements, region_warnings = filter_multiview_generic_elements(
                    generic_elements,
                    multiview.views,
                    source,
                    scale,
                )
            elif not specialized_activated:
                generic_elements, region_warnings = self._filter_multi_view_structural_regions(
                    document,
                    source,
                    generic_elements,
                    scale,
                )
            else:
                region_warnings = []
            warnings.extend(region_warnings)
        elements.extend(generic_elements)

        if source.discipline == Discipline.STRUCTURAL:
            if not any(element.element_type == "rebar" for element in elements):
                warnings.append(
                    AnalysisWarning(
                        code="REBAR_SOURCE_MISSING",
                        message=(
                            "Açık bir donatı geometrisi/çizelgesi algılanmadı. "
                            "Motor genel kabullerden donatı tahmini yapmayacak."
                        ),
                        source_id=source.id,
                    )
                )
            for required_type in ("column", "beam", "slab"):
                if not any(element.element_type == required_type for element in elements):
                    warnings.append(
                        AnalysisWarning(
                            code=f"{required_type.upper()}_NOT_DETECTED",
                            message=(
                                f"{source.original_name} içinde {required_type} "
                                "elemanı algılanmadı."
                            ),
                            source_id=source.id,
                        )
                    )

        if not elements:
            warnings.append(
                AnalysisWarning(
                    code="NO_ELEMENTS_DETECTED",
                    message=(
                        f"{source.original_name} içinde mevcut katman kurallarıyla eşleşen "
                        f"{source.discipline.value} elemanı bulunamadı. Katman eşlemesini "
                        "gözden geçirin."
                    ),
                    source_id=source.id,
                )
            )
        return elements, warnings, detected_unit

    @staticmethod
    def _filter_multi_view_structural_regions(
        document,
        source: SourceFile,
        elements: list[DetectedElement],
        scale: float,
    ) -> tuple[list[DetectedElement], list[AnalysisWarning]]:
        titles: list[tuple[str, tuple[float, float]]] = []
        for entity in document.modelspace():
            if entity.dxftype() == "TEXT":
                value = str(entity.dxf.text).strip()
            elif entity.dxftype() == "MTEXT":
                value = str(entity.plain_text()).strip()
            else:
                continue
            normalized = normalize_name(value)
            if "KALIP" not in normalized or "PLAN" not in normalized:
                continue
            if any(token in normalized for token in ("MERDIVEN", "DETAY", "KALIP ALMA")):
                continue
            point = entity.dxf.insert
            titles.append((value, (float(point.x) * scale, float(point.y) * scale)))
        if len(titles) < 2:
            return elements, []

        physical_types = {
            "column",
            "beam",
            "slab",
            "raft",
            "foundation",
            "shear_wall",
            "stair",
        }
        groups: dict[int, list[DetectedElement]] = {index: [] for index in range(len(titles))}
        unassigned: list[DetectedElement] = []
        for element in elements:
            if element.element_type not in physical_types or element.geometry.bbox is None:
                unassigned.append(element)
                continue
            box = element.geometry.bbox
            center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            distance, index = min(
                (math.dist(center, point), index) for index, (_, point) in enumerate(titles)
            )
            if distance <= 40.0:
                groups[index].append(element)
            else:
                unassigned.append(element)

        confirmed: list[tuple[int, list[DetectedElement]]] = []
        for index, group in groups.items():
            column_count = sum(item.element_type == "column" for item in group)
            foundation_count = sum(item.element_type in {"raft", "foundation"} for item in group)
            if column_count >= 4 or foundation_count >= 1:
                confirmed.append((index, group))

        selected: list[DetectedElement] = []
        seen: set[tuple[str, tuple]] = set()
        duplicate_region_count = 0
        for index, group in sorted(confirmed, key=lambda item: titles[item[0]][1][0]):
            title, origin = titles[index]
            rows: list[tuple] = []
            for element in group:
                candidate_box = element.geometry.bbox
                if candidate_box is None:
                    continue
                rows.append(
                    (
                        element.element_type,
                        round(candidate_box[0] - origin[0], 2),
                        round(candidate_box[1] - origin[1], 2),
                        round(candidate_box[2] - origin[0], 2),
                        round(candidate_box[3] - origin[1], 2),
                    )
                )
            fingerprint = (normalize_name(title), tuple(sorted(rows)))
            if fingerprint in seen:
                duplicate_region_count += 1
                continue
            seen.add(fingerprint)
            for element in group:
                element.properties["plan_region_title"] = title
                element.properties["plan_region_origin_m"] = list(origin)
            selected.extend(group)

        discarded = sum(len(group) for group in groups.values()) - len(selected)
        discarded += sum(item.element_type in physical_types for item in unassigned)
        selected.extend(item for item in unassigned if item.element_type not in physical_types)
        warnings = [
            AnalysisWarning(
                code="MULTI_VIEW_PLAN_REGIONS_FILTERED",
                message=(
                    f"{len(titles)} kalıp planı başlığından {len(confirmed)} kanıtlı fiziksel "
                    f"plan bölgesi ayrıştırıldı; plan bölgesine bağlanamayan {discarded} "
                    "açıklama/detay geometrisi eleman adaylarından çıkarıldı."
                ),
                source_id=source.id,
                severity="info" if confirmed else "warning",
            )
        ]
        if duplicate_region_count:
            warnings.append(
                AnalysisWarning(
                    code="DUPLICATE_PLAN_REGIONS_SKIPPED",
                    message=(
                        f"Aynı başlık ve yerel geometriyi taşıyan {duplicate_region_count} "
                        "kopya plan bölgesi miktarlara yeniden eklenmedi."
                    ),
                    source_id=source.id,
                    severity="info",
                )
            )
        return selected, warnings

    @staticmethod
    def _match_rule(
        discipline: Discipline,
        layer: str,
        entity_type: str,
    ) -> DetectionRule | None:
        normalized_layer = normalize_name(layer)
        for rule in RULES[discipline]:
            if entity_type not in rule.entity_types:
                continue
            if any(normalize_name(token) in normalized_layer for token in rule.tokens):
                return rule
        return None

    def _element_from_entity(
        self,
        entity,
        source: SourceFile,
        rule: DetectionRule,
        scale: float | None,
    ) -> DetectedElement | None:
        raw_points = self._points(entity, scale)
        geometry = Geometry(
            kind=entity.dxftype().lower(),
            points=raw_points,
            bbox=self._bbox(entity, scale),
        )
        measurements: dict[str, float] = {}
        issues: list[str] = []
        if scale is None:
            issues.append("unit_confirmation_required")
        else:
            measurements.update(self._measure(entity, raw_points, geometry.bbox, scale))
        if rule.quantity_kind == "count":
            measurements["count"] = 1.0

        if rule.element_type == "column" and geometry.bbox is not None:
            x1, y1, x2, y2 = geometry.bbox
            small, large = sorted((abs(x2 - x1), abs(y2 - y1)))
            if scale is None:
                pass
            elif not (0.1 <= small <= 2.0 and small <= large <= 4.0 and large / small <= 6):
                return None
            else:
                measurements["width_m"] = small
                measurements["depth_m"] = large
        elif rule.element_type == "beam" and entity.dxftype() == "LWPOLYLINE":
            if geometry.bbox is None or not bool(getattr(entity, "closed", False)):
                return None
            x1, y1, x2, y2 = geometry.bbox
            spans = sorted((abs(x2 - x1), abs(y2 - y1)))
            if not (0.1 <= spans[0] <= 1.5 and 0.5 <= spans[1] <= 50):
                return None
            measurements["width_m"] = spans[0]
            measurements["length_m"] = spans[1]
        elif (
            rule.element_type == "wall"
            and entity.dxftype() == "LWPOLYLINE"
            and bool(getattr(entity, "closed", False))
        ):
            # A closed wall outline does not prove its center line or opening policy.
            # Keep it out until a paired-boundary wall detector is available.
            return None
        elif rule.element_type == "shear_wall" and geometry.bbox is not None:
            small, large = sorted(
                (
                    abs(geometry.bbox[2] - geometry.bbox[0]),
                    abs(geometry.bbox[3] - geometry.bbox[1]),
                )
            )
            if 0.1 <= small <= 1.5 and large >= max(0.5, small * 1.5):
                measurements["thickness_m"] = small
                measurements["length_m"] = large
        elif rule.element_type == "stair":
            plan_area = measurements.get("area_m2")
            if plan_area is not None:
                measurements["plan_area_m2"] = plan_area
            if geometry.bbox is not None:
                spans = sorted(
                    (
                        abs(geometry.bbox[2] - geometry.bbox[0]),
                        abs(geometry.bbox[3] - geometry.bbox[1]),
                    )
                )
                if spans[1] > 0:
                    measurements["horizontal_run_m"] = spans[1]

        if rule.element_type in {"slab", "raft", "foundation", "stair"} and (
            "area_m2" not in measurements or measurements["area_m2"] <= 0
        ):
            return None

        if rule.element_type == "rebar" and not {
            "count",
            "diameter_mm",
        }.issubset(measurements):
            # A line on a rebar-like layer is usually a detail, leader or hatch.
            # Without an explicit count and diameter it is not a quantity candidate.
            return None
        if rule.element_type == "shear_wall" and not {
            "length_m",
            "thickness_m",
        }.issubset(measurements):
            # A single/open line does not prove a physical wall thickness.
            return None

        missing = [
            key for key in rule.required_inputs if key not in measurements or measurements[key] <= 0
        ]
        issues.extend(f"missing:{key}" for key in missing)
        if scale is None or missing:
            status = ReviewStatus.NEEDS_REVIEW
        else:
            status = ReviewStatus.PENDING

        confidence = 0.92 if not missing and scale is not None else 0.68
        if entity.dxftype() == "INSERT" and rule.quantity_kind != "count":
            confidence = min(confidence, 0.6)
        identity = "|".join(
            (
                source.sha256,
                source.floor,
                rule.element_type,
                str(getattr(entity.dxf, "handle", "")),
                entity.dxf.layer,
            )
        )
        element_id = "elm_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        properties: dict[str, object] = {"quantity_kind": rule.quantity_kind}
        void_count = int(measurements.get("void_count", 0))
        if void_count:
            properties["opening_evidence"] = {
                "void_count": void_count,
                "gross_area_m2": measurements.get("gross_area_m2", 0.0),
                "void_area_m2": measurements.get("void_area_m2", 0.0),
                "method": "nested_hatch_boundaries",
            }
        if rule.element_type == "stair":
            properties["calculation_policy"] = (
                "inclined_waist_slab_requires_explicit_section_rise_and_thickness"
            )
        return DetectedElement(
            id=element_id,
            source_id=source.id,
            discipline=source.discipline,
            element_type=rule.element_type,
            floor=source.floor,
            layer=entity.dxf.layer,
            block_name=str(getattr(entity.dxf, "name", "")),
            source_handle=str(getattr(entity.dxf, "handle", "")),
            geometry=geometry,
            measurements=measurements,
            properties=properties,
            required_inputs=list(rule.required_inputs),
            confidence=confidence,
            review_status=status,
            issues=issues,
        )

    @staticmethod
    def _points(entity, scale: float | None) -> list[tuple[float, float]]:
        factor = scale or 1.0
        kind = entity.dxftype()
        if kind == "LINE":
            return [
                (float(entity.dxf.start.x) * factor, float(entity.dxf.start.y) * factor),
                (float(entity.dxf.end.x) * factor, float(entity.dxf.end.y) * factor),
            ]
        if kind == "LWPOLYLINE":
            try:
                tolerance = max(0.001 / factor, 1e-6)
                vertices = list(make_path(entity).flattening(distance=tolerance))
                return [(float(point.x) * factor, float(point.y) * factor) for point in vertices]
            except Exception:
                return [
                    (float(point[0]) * factor, float(point[1]) * factor)
                    for point in entity.get_points("xy")
                ]
        if kind == "INSERT":
            point = entity.dxf.insert
            return [(float(point.x) * factor, float(point.y) * factor)]
        if kind == "HATCH":
            points: list[tuple[float, float]] = []
            for path in from_hatch(entity):
                tolerance = max(0.001 / factor, 1e-6)
                points.extend(
                    (float(point.x) * factor, float(point.y) * factor)
                    for point in path.flattening(distance=tolerance)
                )
            return points
        return []

    @staticmethod
    def _bbox(entity, scale: float | None) -> tuple[float, float, float, float] | None:
        factor = scale or 1.0
        try:
            box = bbox.extents([entity], fast=True)
        except Exception:
            return None
        if not box.has_data:
            return None
        return (
            float(box.extmin.x) * factor,
            float(box.extmin.y) * factor,
            float(box.extmax.x) * factor,
            float(box.extmax.y) * factor,
        )

    @staticmethod
    def _measure(
        entity,
        points: list[tuple[float, float]],
        entity_bbox: tuple[float, float, float, float] | None,
        scale: float,
    ) -> dict[str, float]:
        measurements: dict[str, float] = {}
        kind = entity.dxftype()
        if kind == "LINE":
            start, end = points
            measurements["length_m"] = math.dist(start, end)
        elif kind == "LWPOLYLINE" and len(points) >= 2:
            length = sum(
                math.dist(first, second) for first, second in zip(points, points[1:], strict=False)
            )
            closed = bool(getattr(entity, "closed", False))
            if closed and points[0] != points[-1]:
                length += math.dist(points[-1], points[0])
            measurements["length_m"] = length
            if closed and len(points) >= 3:
                area = abs(
                    sum(
                        first[0] * second[1] - second[0] * first[1]
                        for first, second in zip(points, points[1:] + points[:1], strict=True)
                    )
                    / 2.0
                )
                measurements["area_m2"] = area
                measurements["perimeter_m"] = length
        elif kind == "HATCH":
            paths = list(from_hatch(entity))
            structure = make_polygon_structure(paths)

            def nested_metrics(items, level: int = 0) -> tuple[float, float, int]:
                gross = 0.0
                void = 0.0
                void_count = 0
                for item in items:
                    if isinstance(item, list):
                        child_gross, child_void, child_count = nested_metrics(item, level + 1)
                        gross += child_gross
                        void += child_void
                        void_count += child_count
                    else:
                        vertices = list(item.flattening(distance=max(0.001 / scale, 1e-6)))
                        value = abs(float(polygon_area(vertices)))
                        if level % 2:
                            gross += value
                        else:
                            void += value
                            void_count += 1
                return gross, void, void_count

            raw_gross, raw_void, void_count = nested_metrics(structure)
            raw_area = raw_gross - raw_void
            if raw_gross > 0:
                measurements["gross_area_m2"] = raw_gross * scale * scale
                measurements["void_area_m2"] = raw_void * scale * scale
                measurements["void_count"] = float(void_count)
            if raw_area > 0:
                measurements["area_m2"] = raw_area * scale * scale
            perimeter = 0.0
            for path in paths:
                vertices = list(path.flattening(distance=max(0.001 / scale, 1e-6)))
                perimeter += sum(
                    first.distance(second)
                    for first, second in zip(vertices, vertices[1:], strict=False)
                )
                if len(vertices) > 1 and vertices[0] != vertices[-1]:
                    perimeter += vertices[-1].distance(vertices[0])
            if perimeter > 0:
                measurements["perimeter_m"] = perimeter * scale
        elif kind == "INSERT":
            measurements["count"] = 1.0

        if entity_bbox is not None:
            x1, y1, x2, y2 = entity_bbox
            measurements["bbox_width_m"] = abs(x2 - x1)
            measurements["bbox_height_m"] = abs(y2 - y1)
        return measurements


def iter_layer_names(elements: Iterable[DetectedElement]) -> list[str]:
    return sorted({element.layer for element in elements})
