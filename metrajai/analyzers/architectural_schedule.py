from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from ..contracts import (
    AnalysisWarning,
    DetectedElement,
    Geometry,
    ReviewStatus,
    SourceFile,
)

AREA_TEXT = re.compile(r"^(?P<value>\d+(?:[.,]\d+)?)\s*M(?:2|²)$", re.IGNORECASE)
ROOM_CODE = re.compile(r"^[A-Z]{1,4}\d{1,3}$")


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(ascii_text.upper().replace("İ", "I").split())


def _text(entity) -> str:
    if entity.dxftype() == "TEXT":
        return str(entity.dxf.text).strip()
    if entity.dxftype() == "MTEXT":
        return str(entity.plain_text()).strip()
    return ""


def _area(value: str) -> float | None:
    match = AREA_TEXT.fullmatch(_normalize(value).replace(" ", ""))
    if match is None:
        return None
    return round(float(match.group("value").replace(",", ".")), 4)


def _identity(source: SourceFile, table_handle: str, room_code: str) -> str:
    value = f"{source.sha256}|architectural-room|{table_handle}|{room_code}"
    return "elm_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _floor_label(values: list[str], source: SourceFile) -> str:
    combined = " ".join(_normalize(value) for value in values[:8])
    if "ZEMIN KAT" in combined:
        return "Zemin Kat"
    if "BODRUM KAT" in combined:
        return "Bodrum Kat"
    if "CATI" in combined:
        return "Çatı"
    return source.floor


@dataclass(frozen=True)
class ArchitecturalScheduleResult:
    elements: list[DetectedElement]
    warnings: list[AnalysisWarning]
    room_area_m2: float | None = None
    reference_net_area_m2: float | None = None
    reference_gross_area_m2: float | None = None


def _table_values(document, geometry_name: str) -> list[str]:
    try:
        block = document.blocks.get(geometry_name)
    except Exception:
        return []
    return [value for entity in block if (value := _text(entity))]


def _room_rows(values: list[str]) -> list[tuple[str, str, float, list[str]]]:
    normalized = [_normalize(value) for value in values]
    if not {
        "MAHAL KODU",
        "MAHAL ADI",
        "NET ALAN",
    }.issubset(set(normalized)):
        return []

    rows: list[tuple[str, str, float, list[str]]] = []
    for index, value in enumerate(normalized):
        code = value.replace(" ", "")
        if ROOM_CODE.fullmatch(code) is None or index + 2 >= len(values):
            continue
        area_index = next(
            (
                candidate
                for candidate in range(index + 2, min(index + 5, len(values)))
                if _area(values[candidate]) is not None
            ),
            None,
        )
        if area_index is None:
            continue
        area = _area(values[area_index])
        if area is None or area <= 0:
            continue
        room_name = values[index + 1].strip()
        finishes = values[area_index + 1 : area_index + 4]
        rows.append((code, room_name, area, finishes))
    return rows


def extract_architectural_schedules(
    document,
    source: SourceFile,
) -> ArchitecturalScheduleResult:
    """Extract explicit room rows and reconcile them with architectural area tables."""
    rooms: dict[str, DetectedElement] = {}
    all_tables: list[tuple[str, str, list[str]]] = []
    for entity in document.modelspace():
        if entity.dxftype() == "ACAD_TABLE":
            geometry_name = str(getattr(entity.dxf, "geometry", ""))
        elif entity.dxftype() == "INSERT":
            geometry_name = str(getattr(entity.dxf, "name", ""))
        else:
            continue
        values = _table_values(document, geometry_name)
        if not values:
            continue
        table_handle = str(entity.dxf.handle)
        all_tables.append((table_handle, geometry_name, values))
        floor = _floor_label(values, source)
        for row_number, (code, room_name, area, finishes) in enumerate(
            _room_rows(values),
            start=1,
        ):
            properties: dict[str, object] = {
                "quantity_kind": "room",
                "element_label": code,
                "room_code": code,
                "room_name": room_name,
                "schedule_evidence": {
                    "method": "explicit_dxf_acad_table",
                    "table_handle": table_handle,
                    "table_block": geometry_name,
                    "row_number": row_number,
                    "declared_area_text": f"{area:g} m²",
                },
            }
            if finishes:
                properties["floor_finish"] = finishes[0]
            if len(finishes) > 1:
                properties["wall_finish"] = finishes[1]
            if len(finishes) > 2:
                properties["ceiling_finish"] = finishes[2]
            rooms[code] = DetectedElement(
                id=_identity(source, table_handle, code),
                source_id=source.id,
                discipline=source.discipline,
                element_type="room",
                floor=floor,
                layer="Mahal Çizelgesi",
                block_name=geometry_name,
                source_handle=f"{table_handle}:{code}",
                geometry=Geometry(kind="architectural_schedule_row"),
                measurements={"area_m2": area},
                properties=properties,
                required_inputs=["area_m2"],
                confidence=0.98,
                review_status=ReviewStatus.PENDING,
            )

    elements = sorted(rooms.values(), key=lambda item: str(item.properties["room_code"]))
    if not elements:
        return ArchitecturalScheduleResult([], [])

    room_area = round(sum(item.measurements["area_m2"] for item in elements), 4)
    reference_areas: list[float] = []
    for _, _, values in all_tables:
        normalized = {_normalize(value) for value in values}
        if "BB NET ALAN" not in normalized or "BB BRUT ALAN" not in normalized:
            continue
        reference_areas.extend(
            parsed for value in values if (parsed := _area(value)) is not None
        )
    candidates = sorted({value for value in reference_areas if value >= room_area * 0.9})
    reference_net = (
        min(candidates, key=lambda value: abs(value - room_area)) if candidates else None
    )
    reference_gross = max(candidates) if candidates else None

    warnings = [
        AnalysisWarning(
            code="ARCHITECTURAL_ROOM_SCHEDULE_EXTRACTED",
            message=(
                f"DXF mahal çizelgesinden {len(elements)} açık mahal satırı okundu; "
                f"satır alanları toplamı {room_area:g} m²."
            ),
            source_id=source.id,
            severity="info",
        )
    ]
    if reference_net is not None and abs(reference_net - room_area) > 0.02:
        warnings.append(
            AnalysisWarning(
                code="ARCHITECTURAL_NET_AREA_MISMATCH",
                message=(
                    f"Mahal satırları {room_area:g} m², bağımsız bölüm net alanı "
                    f"{reference_net:g} m²: {abs(reference_net - room_area):g} m² fark "
                    "mimar tarafından doğrulanmalıdır."
                ),
                source_id=source.id,
            )
        )
    if reference_gross is not None:
        warnings.append(
            AnalysisWarning(
                code="ARCHITECTURAL_GROSS_AREA_EVIDENCE",
                message=f"Bağımsız bölüm tablosunda brüt alan {reference_gross:g} m² okundu.",
                source_id=source.id,
                severity="info",
            )
        )
    return ArchitecturalScheduleResult(
        elements,
        warnings,
        room_area_m2=room_area,
        reference_net_area_m2=reference_net,
        reference_gross_area_m2=reference_gross,
    )
