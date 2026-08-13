from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from statistics import median
from typing import Any

from ezdxf import bbox
from ezdxf.math import area as polygon_area
from ezdxf.path import from_hatch, make_path
from ezdxf.path.nesting import make_polygon_structure

from ..contracts import (
    AnalysisWarning,
    ArchitecturalAssignment,
    DetectedElement,
    Geometry,
    ReviewStatus,
    SourceFile,
)
from ..units import unit_scale
from .architectural_schedule import _normalize, extract_opening_schedule

PLAN_TOKENS = ("KAT PLANI", "ZEMIN KAT", "BODRUM KAT", "NORMAL KAT")
EXCLUDED_TOKENS = ("KESIT", "GORUNUS", "DETAY", "VAZIYET", "CIZELGE", "ACILIM")
ROOM_TOKENS = ("MAHAL", "ODA", "ROOM", "ALAN")
WALL_TOKENS = ("DUVAR", "WALL", "SIVA")
DOOR_TOKENS = ("KAPI", "DOOR")
WINDOW_TOKENS = ("PENCERE", "WINDOW", "PEN")
ROOM_CODE = re.compile(r"\b([A-Z]{1,4}\s*\d{1,3})\b")
OPENING_LABEL = re.compile(
    r"\b([A-Z]{1,5}(?:-\d+)?)\s*(?:[-:]\s*)?(\d{2,4})?\s*[/X]?\s*(\d{2,4})?\b"
)
HEIGHT_BAND = re.compile(r"H\s*[:=]\s*(\d+(?:[.,]\d+)?)\s*CM", re.IGNORECASE)
AREA_LABEL = re.compile(r"(?P<area>\d+(?:[.,]\d+)?)\s*M(?:2|²)", re.IGNORECASE)


@dataclass(frozen=True)
class _FlatEntity:
    entity: Any
    path: str
    inherited_layer: str
    block_name: str = ""

    @property
    def layer(self) -> str:
        layer = str(getattr(self.entity.dxf, "layer", "") or "")
        return self.inherited_layer if layer == "0" else layer


def _walk(entities, *, path: str = "", inherited_layer: str = "", depth: int = 0):
    if depth > 8:
        return
    for index, entity in enumerate(entities):
        handle = str(getattr(entity.dxf, "handle", "") or f"v{index}")
        current_path = f"{path}/{handle}" if path else handle
        layer = str(getattr(entity.dxf, "layer", "") or inherited_layer)
        name = str(getattr(entity.dxf, "name", "") or "")
        yield _FlatEntity(entity, current_path, inherited_layer, name)
        if entity.dxftype() != "INSERT":
            continue
        try:
            virtual = list(entity.virtual_entities())
        except Exception:
            continue
        yield from _walk(
            virtual,
            path=current_path,
            inherited_layer=layer if layer != "0" else inherited_layer,
            depth=depth + 1,
        )


def _entity_bbox(item: _FlatEntity, scale: float) -> tuple[float, float, float, float] | None:
    try:
        box = bbox.extents([item.entity], fast=True)
    except Exception:
        return None
    if not box.has_data:
        return None
    values = (
        float(box.extmin.x) * scale,
        float(box.extmin.y) * scale,
        float(box.extmax.x) * scale,
        float(box.extmax.y) * scale,
    )
    if not all(math.isfinite(value) for value in values):
        return None
    x1, y1, x2, y2 = values
    if max(abs(x2 - x1), abs(y2 - y1)) > 1000:
        return None
    return x1, y1, x2, y2


def _text(item: _FlatEntity) -> str:
    entity = item.entity
    if entity.dxftype() == "TEXT":
        return str(entity.dxf.text).strip()
    if entity.dxftype() == "MTEXT":
        return str(entity.plain_text()).strip()
    return ""


def _points(item: _FlatEntity, scale: float) -> list[tuple[float, float]]:
    entity = item.entity
    try:
        if entity.dxftype() == "LINE":
            return [
                (float(entity.dxf.start.x) * scale, float(entity.dxf.start.y) * scale),
                (float(entity.dxf.end.x) * scale, float(entity.dxf.end.y) * scale),
            ]
        if entity.dxftype() == "LWPOLYLINE":
            values = list(make_path(entity).flattening(distance=max(0.001 / scale, 1e-6)))
            return [(float(point.x) * scale, float(point.y) * scale) for point in values]
        if entity.dxftype() == "HATCH":
            return [
                (float(point.x) * scale, float(point.y) * scale)
                for path in from_hatch(entity)
                for point in path.flattening(distance=max(0.001 / scale, 1e-6))
            ]
        if entity.dxftype() == "INSERT":
            point = entity.dxf.insert
            return [(float(point.x) * scale, float(point.y) * scale)]
    except Exception:
        return []
    return []


def _poly_metrics(
    item: _FlatEntity, scale: float
) -> tuple[float, float, list[tuple[float, float]]]:
    points = _points(item, scale)
    if len(points) < 3:
        return 0.0, 0.0, points
    entity = item.entity
    if entity.dxftype() == "HATCH":
        try:
            structure = make_polygon_structure(list(from_hatch(entity)))

            def area_of(items, level: int = 0) -> float:
                result = 0.0
                for value in items:
                    if isinstance(value, list):
                        result += area_of(value, level + 1)
                    else:
                        vertices = list(value.flattening(distance=max(0.001 / scale, 1e-6)))
                        result += (1 if level % 2 else -1) * abs(float(polygon_area(vertices)))
                return result

            area = abs(area_of(structure)) * scale * scale
        except Exception:
            area = 0.0
    else:
        area = abs(
            sum(
                first[0] * second[1] - second[0] * first[1]
                for first, second in zip(points, points[1:] + points[:1], strict=True)
            )
            / 2
        )
    perimeter = sum(
        math.dist(first, second) for first, second in zip(points, points[1:], strict=False)
    )
    if points[0] != points[-1]:
        perimeter += math.dist(points[-1], points[0])
    return area, perimeter, points


def _stable_id(source: SourceFile, kind: str, identity: str) -> str:
    raw = f"{source.sha256}|architecture-v1.1|{kind}|{identity}"
    return "elm_" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _room_code_near(
    box: tuple[float, float, float, float],
    texts: list[tuple[str, tuple[float, float, float, float]]],
) -> str:
    candidates: list[tuple[float, str]] = []
    center = _center(box)
    for raw, text_box in texts:
        match = ROOM_CODE.search(_normalize(raw))
        if match is None:
            continue
        point = _center(text_box)
        if box[0] - 0.5 <= point[0] <= box[2] + 0.5 and box[1] - 0.5 <= point[1] <= box[3] + 0.5:
            candidates.append((math.dist(center, point), match.group(1).replace(" ", "")))
    return min(candidates)[1] if candidates else ""


def _nearest_wall(
    point: tuple[float, float], walls: list[DetectedElement], maximum: float
) -> DetectedElement | None:
    candidates: list[tuple[float, DetectedElement]] = []
    for wall in walls:
        if len(wall.geometry.points) < 2:
            continue
        first, second = wall.geometry.points[:2]
        dx, dy = second[0] - first[0], second[1] - first[1]
        length2 = dx * dx + dy * dy
        if not length2:
            continue
        ratio = max(
            0.0, min(1.0, ((point[0] - first[0]) * dx + (point[1] - first[1]) * dy) / length2)
        )
        projection = first[0] + ratio * dx, first[1] + ratio * dy
        candidates.append((math.dist(point, projection), wall))
    if not candidates or min(candidates)[0] > maximum:
        return None
    return min(candidates, key=lambda value: value[0])[1]


def _finish(
    source: SourceFile,
    room: DetectedElement,
    surface: str,
    material: str,
    *,
    gross: float,
    opening: float = 0.0,
    band_height: float | None = None,
    policy: str,
) -> DetectedElement:
    net = max(0.0, gross - opening)
    room_code = str(room.properties.get("room_code", room.id))
    identity = f"{room.id}|{surface}|{material}|{band_height or 0:g}"
    blocking = [issue for issue in room.issues if issue.startswith("blocking:")]
    return DetectedElement(
        id=_stable_id(source, "finish", identity),
        source_id=source.id,
        discipline=source.discipline,
        element_type="finish_area",
        floor=room.floor,
        layer="Mimari Kaplama",
        source_handle=f"{room.source_handle}:{surface}:{material}",
        geometry=room.geometry.model_copy(deep=True),
        measurements={
            "gross_area_m2": round(gross, 6),
            "opening_area_m2": round(opening, 6),
            "net_area_m2": round(net, 6),
            "area_m2": round(net, 6),
        },
        properties={
            "quantity_kind": "finish_area",
            "room_id": room.id,
            "room_code": room_code,
            "room_name": room.properties.get("room_name", ""),
            "surface_type": surface,
            "material": material.strip(),
            "band_height_m": band_height,
            "calculation_policy": policy,
            "derived_by": "architectural_v1.1",
        },
        required_inputs=["area_m2"],
        confidence=room.confidence,
        review_status=(
            ReviewStatus.PENDING if net > 0 and not blocking else ReviewStatus.NEEDS_REVIEW
        ),
        issues=(blocking if net > 0 else [*blocking, "blocking:finish_area_missing"]),
    )


def reconcile_architectural_elements(
    source: SourceFile, elements: list[DetectedElement]
) -> tuple[list[DetectedElement], list[AnalysisWarning]]:
    """Merge room schedule and plan evidence, then derive traceable finish rows."""
    schedule_rooms = {
        str(item.properties.get("room_code", "")): item
        for item in elements
        if item.source_id == source.id
        and item.element_type == "room"
        and item.geometry.kind
        in {"architectural_schedule_row", "spreadsheet_schedule_row", "spreadsheet_row"}
    }
    plan_rooms = [
        item
        for item in elements
        if item.element_type == "room"
        and item.geometry.kind
        not in {"architectural_schedule_row", "spreadsheet_schedule_row", "spreadsheet_row"}
    ]
    consumed: set[str] = set()
    room_id_map: dict[str, str] = {}
    warnings: list[AnalysisWarning] = []
    for code, room in schedule_rooms.items():
        candidates = [item for item in plan_rooms if item.properties.get("room_code") == code]
        if len(candidates) != 1:
            room.issues.append("blocking:room_boundary_assignment_required")
            room.review_status = ReviewStatus.NEEDS_REVIEW
            continue
        boundary = candidates[0]
        consumed.add(boundary.id)
        room_id_map[boundary.id] = room.id
        geometric = boundary.measurements.get("area_m2", 0.0)
        scheduled = room.measurements.get("area_m2", 0.0)
        room.geometry = boundary.geometry.model_copy(deep=True)
        room.measurements["perimeter_m"] = boundary.measurements["perimeter_m"]
        room.measurements["geometric_area_m2"] = geometric
        room.properties["boundary_element_id"] = boundary.id
        room.properties["boundary_source_handle"] = boundary.source_handle
        difference_ratio = abs(geometric - scheduled) / scheduled if scheduled else 1.0
        room.properties["area_difference_ratio"] = difference_ratio
        if difference_ratio > 0.01:
            room.issues.append("blocking:room_schedule_geometry_mismatch")
            room.review_status = ReviewStatus.NEEDS_REVIEW
        else:
            room.confidence = min(room.confidence, boundary.confidence)

    base = [
        item for item in elements if item.id not in consumed and item.element_type != "finish_area"
    ]
    openings = [item for item in base if item.element_type in {"door", "window"}]
    for opening in openings:
        adjacent = [
            room_id_map.get(str(room_id), str(room_id))
            for room_id in opening.properties.get("adjacent_room_ids", [])
        ]
        opening.properties["adjacent_room_ids"] = list(dict.fromkeys(adjacent))
    walls = [item for item in base if item.element_type == "wall"]
    for wall in walls:
        wall.measurements["opening_area_m2"] = round(
            sum(
                opening.measurements.get("opening_area_m2", 0.0)
                for opening in openings
                if opening.properties.get("host_wall_id") == wall.id
            ),
            6,
        )
    derived: list[DetectedElement] = []
    for room in [
        item for item in base if item.source_id == source.id and item.element_type == "room"
    ]:
        area = room.measurements.get("area_m2", 0.0)
        floor_material = str(room.properties.get("floor_finish", "")).strip()
        ceiling_material = str(room.properties.get("ceiling_finish", "")).strip()
        perimeter = room.measurements.get("perimeter_m", 0.0)
        height = room.measurements.get("height_m", 0.0)
        opening_area = sum(
            item.measurements.get("opening_area_m2", 0.0)
            for item in openings
            if room.id in item.properties.get("adjacent_room_ids", [])
        )
        if floor_material and area > 0:
            derived.append(
                _finish(source, room, "floor", floor_material, gross=area, policy="net_room_area")
            )
        if ceiling_material and area > 0:
            derived.append(
                _finish(
                    source, room, "ceiling", ceiling_material, gross=area, policy="net_room_area"
                )
            )

        applications = room.properties.get("finish_applicability", [])
        if isinstance(applications, list):
            for application in applications:
                if not isinstance(application, dict):
                    continue
                section = _normalize(str(application.get("section", "")))
                material = " · ".join(
                    value
                    for value in (
                        str(application.get("position_code", "")).strip(),
                        str(application.get("material", "")).strip(),
                    )
                    if value
                )
                if not material:
                    continue
                if "DOSEME" in section and area > 0:
                    derived.append(
                        _finish(
                            source,
                            room,
                            "floor",
                            material,
                            gross=area,
                            policy="finish_matrix_net_room_area",
                        )
                    )
                elif "TAVAN" in section and area > 0:
                    derived.append(
                        _finish(
                            source,
                            room,
                            "ceiling",
                            material,
                            gross=area,
                            policy="finish_matrix_net_room_area",
                        )
                    )
                elif "DUVAR" in section and perimeter > 0 and height > 0:
                    derived.append(
                        _finish(
                            source,
                            room,
                            "wall",
                            material,
                            gross=perimeter * height,
                            opening=opening_area,
                            band_height=height,
                            policy="finish_matrix_full_room_height",
                        )
                    )

        wall_material = str(room.properties.get("wall_finish", "")).strip()
        if not wall_material or perimeter <= 0 or height <= 0:
            continue
        band = HEIGHT_BAND.search(_normalize(wall_material))
        if band and "+" in wall_material:
            lower_height = min(height, float(band.group(1).replace(",", ".")) / 100)
            materials = [part.strip() for part in wall_material.split("+", 1)]
            materials[0] = HEIGHT_BAND.sub("", materials[0]).strip(" :-")
            lower_opening = opening_area * lower_height / height
            derived.append(
                _finish(
                    source,
                    room,
                    "wall",
                    materials[0],
                    gross=perimeter * lower_height,
                    opening=lower_opening,
                    band_height=lower_height,
                    policy="explicit_lower_height_band",
                )
            )
            upper_height = height - lower_height
            if upper_height > 0:
                derived.append(
                    _finish(
                        source,
                        room,
                        "wall",
                        materials[1],
                        gross=perimeter * upper_height,
                        opening=opening_area - lower_opening,
                        band_height=upper_height,
                        policy="remaining_upper_height_band",
                    )
                )
        else:
            derived.append(
                _finish(
                    source,
                    room,
                    "wall",
                    wall_material,
                    gross=perimeter * height,
                    opening=opening_area,
                    band_height=height,
                    policy="single_material_full_room_height",
                )
            )
    return base + derived, warnings


def apply_architectural_assignments(
    elements: list[DetectedElement], assignments: list[ArchitecturalAssignment]
) -> list[DetectedElement]:
    by_id = {item.id: item for item in elements}
    for assignment in assignments:
        if not assignment.approved:
            continue
        subject = by_id.get(assignment.subject_element_id)
        targets = [
            by_id[target_id] for target_id in assignment.target_element_ids if target_id in by_id
        ]
        if subject is None:
            continue
        kind = assignment.kind.value
        if kind == "room_boundary" and subject.element_type == "room" and len(targets) == 1:
            boundary = targets[0]
            subject.properties["room_code"] = subject.properties.get(
                "room_code", boundary.properties.get("room_code", "")
            )
            boundary.properties["room_code"] = subject.properties.get("room_code", "")
        elif (
            kind == "opening_host"
            and subject.element_type in {"door", "window"}
            and len(targets) == 1
        ):
            subject.properties["host_wall_id"] = targets[0].id
            subject.issues = [
                issue for issue in subject.issues if issue != "blocking:opening_host_wall_required"
            ]
        elif kind == "opening_rooms" and subject.element_type in {"door", "window"} and targets:
            subject.properties["adjacent_room_ids"] = [item.id for item in targets[:2]]
            subject.properties["opening_context"] = "interior" if len(targets) >= 2 else "exterior"
            subject.issues = [
                issue
                for issue in subject.issues
                if issue != "blocking:opening_room_assignment_required"
            ]
        elif kind == "finish_policy" and subject.element_type == "finish_area":
            subject.properties.update(assignment.values)
        subject.properties.setdefault("architectural_assignment_ids", []).append(assignment.id)
    return elements


def extract_architectural_plan(
    document, source: SourceFile, drawing_unit
) -> tuple[list[DetectedElement], list[AnalysisWarning]]:
    if str(drawing_unit) == "unknown":
        return [], []
    scale = unit_scale(drawing_unit)
    flat = list(_walk(document.modelspace()))
    grouped_by_root: dict[str, list[_FlatEntity]] = {}
    for item in flat:
        grouped_by_root.setdefault(item.path.split("/", 1)[0], []).append(item)
    duplicate_roots: set[str] = set()
    seen_plan_blocks: set[tuple[str, float, float, float]] = set()
    for root, group in grouped_by_root.items():
        root_item = group[0]
        if root_item.entity.dxftype() != "INSERT":
            continue
        has_room_boundary = any(
            candidate.entity.dxftype() in {"LWPOLYLINE", "HATCH"}
            and any(token in _normalize(candidate.layer) for token in ROOM_TOKENS)
            for candidate in group[1:]
        )
        if not has_room_boundary:
            continue
        entity = root_item.entity
        signature = (
            root_item.block_name,
            round(float(getattr(entity.dxf, "rotation", 0.0)), 4),
            round(abs(float(getattr(entity.dxf, "xscale", 1.0))), 4),
            round(abs(float(getattr(entity.dxf, "yscale", 1.0))), 4),
        )
        if signature in seen_plan_blocks:
            duplicate_roots.add(root)
        else:
            seen_plan_blocks.add(signature)
    if duplicate_roots:
        flat = [item for item in flat if item.path.split("/", 1)[0] not in duplicate_roots]
    boxes = [(item, box) for item in flat if (box := _entity_bbox(item, scale)) is not None]
    if not boxes:
        return [], []
    centers = [_center(box) for _, box in boxes]
    median_center = median(value[0] for value in centers), median(value[1] for value in centers)
    usable = [(item, box) for item, box in boxes if math.dist(_center(box), median_center) <= 2000]
    outlier_count = len(boxes) - len(usable)
    texts = [(_text(item), box) for item, box in usable if _text(item)]
    opening_schedule = extract_opening_schedule(document)
    titles = [
        (_normalize(value), box)
        for value, box in texts
        if any(token in _normalize(value) for token in PLAN_TOKENS + EXCLUDED_TOKENS)
    ]

    def excluded(box):
        if not titles:
            return False
        value, _ = min(titles, key=lambda title: math.dist(_center(box), _center(title[1])))
        return any(token in value for token in EXCLUDED_TOKENS) and not any(
            token in value for token in PLAN_TOKENS
        )

    elements: list[DetectedElement] = []
    wall_candidates: list[DetectedElement] = []
    seen: set[tuple] = set()
    for item, box in usable:
        if excluded(box):
            continue
        entity = item.entity
        layer = _normalize(item.layer)
        kind = entity.dxftype()
        identity = item.path
        if any(token in layer for token in ROOM_TOKENS) and kind in {"LWPOLYLINE", "HATCH"}:
            if kind == "LWPOLYLINE" and not bool(getattr(entity, "closed", False)):
                continue
            area, perimeter, points = _poly_metrics(item, scale)
            if area < 0.5:
                continue
            fingerprint = ("room", tuple(round(value, 4) for value in box))
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            code = _room_code_near(box, texts)
            wall_candidates.append(
                DetectedElement(
                    id=_stable_id(source, "room-boundary", identity),
                    source_id=source.id,
                    discipline=source.discipline,
                    element_type="room",
                    floor=source.floor,
                    layer=item.layer,
                    source_handle=identity,
                    geometry=Geometry(kind="room_boundary", points=points, bbox=box),
                    measurements={"area_m2": area, "perimeter_m": perimeter},
                    properties={"room_code": code, "boundary_method": kind.lower()},
                    required_inputs=["area_m2", "perimeter_m"],
                    confidence=0.9 if code else 0.72,
                    review_status=ReviewStatus.PENDING if code else ReviewStatus.NEEDS_REVIEW,
                    issues=[] if code else ["blocking:room_code_assignment_required"],
                )
            )
            continue
        if (
            any(token in layer for token in WALL_TOKENS)
            and kind == "LWPOLYLINE"
            and bool(getattr(entity, "closed", False))
        ):
            small, large = sorted((abs(box[2] - box[0]), abs(box[3] - box[1])))
            if not (0.05 <= small <= 1.0 and 0.5 <= large <= 100):
                continue
            horizontal = abs(box[2] - box[0]) >= abs(box[3] - box[1])
            center = _center(box)
            points = (
                [(box[0], center[1]), (box[2], center[1])]
                if horizontal
                else [(center[0], box[1]), (center[0], box[3])]
            )
            wall_candidates.append(
                DetectedElement(
                    id=_stable_id(source, "wall", identity),
                    source_id=source.id,
                    discipline=source.discipline,
                    element_type="wall",
                    floor=source.floor,
                    layer=item.layer,
                    source_handle=identity,
                    geometry=Geometry(kind="paired_wall_boundary", points=points, bbox=box),
                    measurements={"length_m": large, "thickness_m": small},
                    properties={"wall_detection_method": "closed_double_boundary"},
                    required_inputs=["length_m", "height_m"],
                    confidence=0.88,
                    review_status=ReviewStatus.NEEDS_REVIEW,
                    issues=["missing:height_m"],
                )
            )

    elements.extend(wall_candidates)
    walls = [item for item in elements if item.element_type == "wall"]
    rooms = [item for item in elements if item.element_type == "room"]
    for item, box in usable:
        if excluded(box) or item.entity.dxftype() not in {"INSERT", "ARC"}:
            continue
        opening_signature = _normalize(f"{item.layer} {item.block_name}")
        if any(token in opening_signature for token in EXCLUDED_TOKENS):
            continue
        element_type = ""
        if any(token in opening_signature for token in DOOR_TOKENS):
            element_type = "door"
        elif any(token in opening_signature for token in WINDOW_TOKENS):
            element_type = "window"
        if not element_type:
            continue
        width = abs(box[2] - box[0])
        height = abs(box[3] - box[1])
        if item.entity.dxftype() == "ARC":
            width = float(item.entity.dxf.radius) * scale
        if not 0.25 <= max(width, height) <= 10:
            continue
        opening_width = max(width, height)
        if opening_width < 0.25:
            continue
        center = _center(box)
        nearby_labels: list[tuple[float, str]] = []
        for raw_text, text_box in texts:
            match = OPENING_LABEL.search(_normalize(raw_text))
            if match is None:
                continue
            code = match.group(1).replace(" ", "")
            if code not in opening_schedule:
                continue
            distance = math.dist(center, _center(text_box))
            if distance <= 5:
                nearby_labels.append((distance, code))
        type_code = min(nearby_labels)[1] if nearby_labels else ""
        schedule_item = opening_schedule.get(type_code)
        if schedule_item:
            opening_width = float(schedule_item["width_m"])
        host = _nearest_wall(center, walls, max(0.75, opening_width))
        adjacent = [
            room.id
            for room in rooms
            if room.geometry.bbox
            and room.geometry.bbox[0] - 0.5 <= center[0] <= room.geometry.bbox[2] + 0.5
            and room.geometry.bbox[1] - 0.5 <= center[1] <= room.geometry.bbox[3] + 0.5
        ][:2]
        issues = []
        if host is None:
            issues.append("blocking:opening_host_wall_required")
        if not adjacent:
            issues.append("blocking:opening_room_assignment_required")
        measurements = {"count": 1.0, "width_m": opening_width}
        if schedule_item:
            measurements["height_m"] = float(schedule_item["height_m"])
            measurements["opening_area_m2"] = round(
                measurements["width_m"] * measurements["height_m"], 6
            )
        else:
            issues.append("blocking:opening_schedule_match_required")
            issues.append("missing:height_m")
        properties = {
            "opening_type": type_code or item.block_name or element_type,
            "opening_material": schedule_item.get("material", "") if schedule_item else "",
            "opening_schedule_block": schedule_item.get("schedule_block", "")
            if schedule_item
            else "",
            "host_wall_id": host.id if host else "",
            "adjacent_room_ids": adjacent,
            "opening_context": "interior" if len(adjacent) == 2 else "exterior",
        }
        elements.append(
            DetectedElement(
                id=_stable_id(source, element_type, item.path),
                source_id=source.id,
                discipline=source.discipline,
                element_type=element_type,
                floor=source.floor,
                layer=item.layer,
                block_name=item.block_name,
                source_handle=item.path,
                geometry=Geometry(
                    kind=f"{element_type}_opening", points=_points(item, scale), bbox=box
                ),
                measurements=measurements,
                properties=properties,
                required_inputs=["count", "width_m", "height_m"],
                confidence=0.9 if schedule_item and host and adjacent else 0.68,
                review_status=ReviewStatus.PENDING if not issues else ReviewStatus.NEEDS_REVIEW,
                issues=issues,
            )
        )

    warnings: list[AnalysisWarning] = []
    if duplicate_roots:
        warnings.append(
            AnalysisWarning(
                code="DUPLICATE_ARCHITECTURAL_PLAN_BLOCKS_EXCLUDED",
                message=(
                    f"Aynı blok tanımı ve dönüşümü taşıyan {len(duplicate_roots)} kopya "
                    "plan bölgesi metraja yeniden eklenmedi. Kat tekrarı kullanıcı "
                    "kararıyla tanımlanmalıdır."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    declared_areas = [
        (float(match.group("area").replace(",", ".")), box)
        for value, box in texts
        if (match := AREA_LABEL.search(value)) is not None
    ]
    area_boundaries: list[tuple[float, tuple[float, float, float, float]]] = []
    for item, box in usable:
        if item.entity.dxftype() != "LWPOLYLINE" or not bool(getattr(item.entity, "closed", False)):
            continue
        if not any(token in _normalize(item.layer) for token in ("METREKARE", "ALAN")):
            continue
        area, _, _ = _poly_metrics(item, scale)
        if area > 0:
            area_boundaries.append((area, box))
    ratios: list[float] = []
    for declared, label_box in declared_areas:
        label_center = _center(label_box)
        nearby = sorted(
            (
                (math.dist(label_center, _center(boundary_box)), area)
                for area, boundary_box in area_boundaries
                if boundary_box[0] - 0.1 <= label_center[0] <= boundary_box[2] + 0.1
                and boundary_box[1] - 0.1 <= label_center[1] <= boundary_box[3] + 0.1
            ),
            key=lambda value: value[0],
        )
        if nearby and nearby[0][0] <= 10:
            ratios.append(declared / nearby[0][1])
    unit_mismatch = bool(ratios) and not 0.8 <= median(ratios) <= 1.2
    if unit_mismatch:
        for element in elements:
            element.issues.append("blocking:drawing_unit_evidence_mismatch")
            element.review_status = ReviewStatus.NEEDS_REVIEW
        ratio = median(ratios)
        suggested = "cm" if 80 <= ratio <= 120 else "çizim birimi"
        warnings.append(
            AnalysisWarning(
                code="ARCHITECTURAL_UNIT_EVIDENCE_MISMATCH",
                message=(
                    "Yazılı mahal alanları ile geometrik alanlar seçili birimde "
                    f"{ratio:g} kat uyuşmuyor. Kaynağın {suggested} olarak "
                    "doğrulanması gerekir; mimari geometri kesin metraja kapatıldı."
                ),
                source_id=source.id,
                severity="error",
            )
        )
    if outlier_count:
        warnings.append(
            AnalysisWarning(
                code="ARCHITECTURAL_OUTLIERS_EXCLUDED",
                message=(
                    "Önizleme ve mimari hesap bağlamından "
                    f"{outlier_count} uzak/bozuk geometri çıkarıldı."
                ),
                source_id=source.id,
            )
        )
    if elements:
        warnings.append(
            AnalysisWarning(
                code="ARCHITECTURAL_PLAN_CONTEXT_EXTRACTED",
                message=(
                    "Plan bağlamından "
                    f"{sum(item.element_type == 'room' for item in elements)} mahal sınırı, "
                    f"{sum(item.element_type == 'wall' for item in elements)} duvar ve "
                    f"{sum(item.element_type in {'door', 'window'} for item in elements)} "
                    "açıklık adayı çıkarıldı."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    return elements, warnings
