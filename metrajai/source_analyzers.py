from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

from .commercial import CatalogImportError, read_spreadsheet_rows
from .contracts import (
    AnalysisWarning,
    CalibrationStatus,
    DetectedElement,
    Discipline,
    DrawingUnit,
    Geometry,
    ReviewStatus,
    SourceFile,
    SourceFormat,
)


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.replace("ı", "i")
    return " ".join(text.casefold().replace("_", " ").split())


def _stable_element_id(source_id: str, identity: str) -> str:
    return "elm_" + hashlib.sha256(f"{source_id}|{identity}".encode()).hexdigest()[:32]


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _find_columns(rows: list[list[Any]]) -> tuple[int, dict[str, int]]:
    aliases = {
        "code": {"poz", "poz no", "kod", "code"},
        "description": {"aciklama", "poz aciklamasi", "imalat", "tanim", "description"},
        "unit": {"birim", "unit"},
        "quantity": {"miktar", "quantity", "adet"},
        "room": {"mahal", "mahal adi", "oda", "oda adi", "room"},
        "area": {"alan", "net alan", "m2", "area"},
    }
    best: tuple[int, dict[str, int]] = (0, {})
    for row_index, row in enumerate(rows[:40]):
        mapping: dict[str, int] = {}
        for column, value in enumerate(row):
            normalized = _normalize(value)
            for key, names in aliases.items():
                if normalized in names:
                    mapping.setdefault(key, column)
        if len(mapping) > len(best[1]) or (
            len(mapping) == len(best[1])
            and any(key in mapping for key in ("room", "area", "code", "unit"))
            and not any(key in best[1] for key in ("room", "area", "code", "unit"))
        ):
            best = row_index, mapping
    return best


def _element_type(discipline: Discipline, description: str, unit: str) -> str:
    text = _normalize(description)
    normalized_unit = _normalize(unit)
    is_count = normalized_unit in {"adet", "ad", "pcs", "piece"}
    is_length = normalized_unit in {"m", "metre", "meter"}
    is_area = normalized_unit in {"m2", "m²"}
    if discipline == Discipline.LANDSCAPE:
        if is_count:
            return "landscape_item"
        return "landscape_linear" if is_length else "landscape_area"
    if discipline == Discipline.MECHANICAL:
        if is_count:
            return "mechanical_equipment"
        if is_length and any(word in text for word in ("kanal", "duct")):
            return "duct"
        return "pipe" if is_length else "schedule_item"
    if discipline == Discipline.ELECTRICAL:
        if is_count and any(word in text for word in ("armatur", "aydinlatma", "led")):
            return "light"
        if is_count and "priz" in text:
            return "socket"
        if is_count and any(word in text for word in ("pano", "tablo")):
            return "panel"
        if is_length and any(word in text for word in ("tava", "tray")):
            return "cable_tray"
        return "cable" if is_length else "electrical_item" if is_count else "schedule_item"
    if discipline == Discipline.ARCHITECTURAL and is_area:
        return "finish_area"
    return "schedule_item"


def analyze_spreadsheet_source(
    source: SourceFile, path: Path
) -> tuple[list[DetectedElement], list[AnalysisWarning], DrawingUnit]:
    try:
        rows = read_spreadsheet_rows(path)
    except CatalogImportError as exc:
        return (
            [],
            [
                AnalysisWarning(
                    code="SPREADSHEET_IMPORT_FAILED",
                    message=str(exc),
                    source_id=source.id,
                    severity="error",
                )
            ],
            DrawingUnit.UNKNOWN,
        )
    header_row, columns = _find_columns(rows)
    elements: list[DetectedElement] = []
    warnings: list[AnalysisWarning] = []
    if (
        source.discipline == Discipline.ARCHITECTURAL
        and "room" in columns
        and "area" not in columns
    ):
        room_column = columns["room"]
        floor_column = max(0, room_column - 1)
        code_row = rows[header_row] if header_row < len(rows) else []
        description_row = rows[header_row - 1] if header_row > 0 else []
        section_row = rows[header_row - 2] if header_row > 1 else []
        sections: list[str] = []
        active_section = ""
        for column in range(max(len(code_row), len(description_row), len(section_row))):
            if column < len(section_row) and str(section_row[column] or "").strip():
                active_section = str(section_row[column]).strip()
            sections.append(active_section)
        current_floor = source.floor
        for row_number, row in enumerate(rows[header_row + 1 :], start=header_row + 2):
            if floor_column < len(row) and str(row[floor_column] or "").strip():
                candidate_floor = str(row[floor_column]).strip()
                normalized_floor = _normalize(candidate_floor)
                if any(token in normalized_floor for token in ("kat", "bodrum", "zemin", "normal")):
                    current_floor = candidate_floor
            room_name = str(row[room_column] or "").strip() if room_column < len(row) else ""
            match = re.match(
                r"^(?P<code>(?:[A-ZÇĞİÖŞÜ]+)?\d+)\s+(?P<name>.+)$",
                room_name,
                re.IGNORECASE,
            )
            if match is None:
                continue
            applications: list[dict[str, str]] = []
            for column in range(room_column + 1, len(row)):
                marker = _normalize(row[column])
                if marker not in {"o", "x", "1", "+"}:
                    continue
                code = str(code_row[column] or "").strip() if column < len(code_row) else ""
                description = (
                    str(description_row[column] or "").strip()
                    if column < len(description_row)
                    else ""
                )
                if not code and not description:
                    continue
                applications.append(
                    {
                        "section": sections[column] if column < len(sections) else "",
                        "position_code": code,
                        "material": description,
                    }
                )
            room_code = match.group("code").upper()
            elements.append(
                DetectedElement(
                    id=_stable_element_id(source.id, f"room-matrix:{room_code}"),
                    source_id=source.id,
                    discipline=source.discipline,
                    element_type="room",
                    floor=current_floor,
                    source_handle=f"sheet-row-{row_number}",
                    geometry=Geometry(kind="spreadsheet_schedule_row"),
                    properties={
                        "room_code": room_code,
                        "room_name": match.group("name").strip(),
                        "source_row": row_number,
                        "finish_applicability": applications,
                        "schedule_only": True,
                    },
                    required_inputs=["area_m2"],
                    confidence=0.9,
                    review_status=ReviewStatus.NEEDS_REVIEW,
                    issues=["blocking:room_boundary_assignment_required", "missing:area_m2"],
                )
            )
        warnings.append(
            AnalysisWarning(
                code="ARCHITECTURAL_FINISH_MATRIX_EXTRACTED",
                message=(
                    f"Excel mahal/imalat matrisinden {len(elements)} mahal ve "
                    "uygulanabilir kaplama pozları okundu; alanlar plan geometrisiyle "
                    "eşleşmeden kesin metraja alınmayacak."
                ),
                source_id=source.id,
                severity="info",
            )
        )
    elif "room" in columns and "area" in columns:
        for row_number, row in enumerate(rows[header_row + 1 :], start=header_row + 2):
            room_name = (
                str(row[columns["room"]] or "").strip() if columns["room"] < len(row) else ""
            )
            area = _number(row[columns["area"]]) if columns["area"] < len(row) else None
            if not room_name:
                continue
            measurements = {"area_m2": area} if area and area > 0 else {}
            elements.append(
                DetectedElement(
                    id=_stable_element_id(source.id, f"room:{row_number}:{room_name}"),
                    source_id=source.id,
                    discipline=source.discipline,
                    element_type="room",
                    floor=source.floor,
                    source_handle=f"sheet-row-{row_number}",
                    geometry=Geometry(kind="spreadsheet_row"),
                    measurements=measurements,
                    properties={"room_name": room_name, "source_row": row_number},
                    required_inputs=["area_m2"],
                    confidence=0.8 if measurements else 0.45,
                    review_status=ReviewStatus.NEEDS_REVIEW,
                    issues=[] if measurements else ["missing:area_m2"],
                )
            )
    elif {"code", "description", "unit"}.issubset(columns):
        quantity_column = columns.get("quantity")
        for row_number, row in enumerate(rows[header_row + 1 :], start=header_row + 2):

            def cell(key: str, current_row: list[Any] = row) -> Any:
                index = columns[key]
                return current_row[index] if index < len(current_row) else None

            code = str(cell("code") or "").strip()
            description = str(cell("description") or "").strip()
            unit = str(cell("unit") or "").strip()
            if not code or not description or not unit:
                continue
            quantity = (
                _number(row[quantity_column])
                if quantity_column is not None and quantity_column < len(row)
                else None
            )
            element_type = _element_type(source.discipline, description, unit)
            measurement_key = {
                "adet": "count",
                "ad": "count",
                "m": "length_m",
                "metre": "length_m",
                "m2": "area_m2",
                "m²": "area_m2",
            }.get(_normalize(unit), "")
            measurements = (
                {measurement_key: quantity}
                if measurement_key and quantity is not None and quantity > 0
                else {}
            )
            issues = [] if measurements else ["blocking:quantity_geometry_missing"]
            elements.append(
                DetectedElement(
                    id=_stable_element_id(source.id, f"schedule:{row_number}:{code}"),
                    source_id=source.id,
                    discipline=source.discipline,
                    element_type=element_type,
                    floor=source.floor,
                    source_handle=f"sheet-row-{row_number}",
                    geometry=Geometry(kind="spreadsheet_row"),
                    measurements=measurements,
                    properties={
                        "position_code": code,
                        "description": description,
                        "declared_unit": unit,
                        "source_row": row_number,
                        "schedule_only": not bool(measurements),
                    },
                    required_inputs=[measurement_key] if measurement_key else [],
                    confidence=0.75 if measurements else 0.4,
                    review_status=ReviewStatus.NEEDS_REVIEW,
                    issues=issues,
                )
            )
    else:
        warnings.append(
            AnalysisWarning(
                code="SPREADSHEET_SCHEMA_NEEDS_MAPPING",
                message="Excel sütunları mahal veya poz şemasıyla eşleştirilemedi.",
                source_id=source.id,
                severity="warning",
            )
        )
    if elements and all(item.properties.get("schedule_only") for item in elements):
        warnings.append(
            AnalysisWarning(
                code="SCHEDULE_IS_NOT_QUANTITY_SOURCE",
                message=(
                    f"{len(elements)} poz/uygulanabilirlik satırı okundu; gerçek miktar "
                    "geometrisi bulunmadığından kesin metraja alınmadı."
                ),
                source_id=source.id,
                severity="warning",
            )
        )
    return elements, warnings, DrawingUnit.UNKNOWN


def analyze_pdf_source(
    source: SourceFile, path: Path
) -> tuple[list[DetectedElement], list[AnalysisWarning], DrawingUnit]:
    try:
        import pdfplumber
    except ImportError:
        return (
            [],
            [
                AnalysisWarning(
                    code="PDF_RUNTIME_UNAVAILABLE",
                    message="PDF okuma bileşeni paketlenmemiş.",
                    source_id=source.id,
                    severity="error",
                )
            ],
            DrawingUnit.UNKNOWN,
        )
    elements: list[DetectedElement] = []
    warnings: list[AnalysisWarning] = []
    scanned_pages: dict[int, tuple[float, float]] = {}
    with pdfplumber.open(path) as document:
        for page_number, page in enumerate(document.pages, start=1):
            text = (page.extract_text() or "").strip()
            lines = page.lines or []
            if not text and not lines:
                scanned_pages[page_number] = (float(page.width), float(page.height))
                continue
            points: list[tuple[float, float]] = []
            for line in lines[:2000]:
                points.extend(
                    [
                        (float(line.get("x0", 0)), float(line.get("y0", 0))),
                        (float(line.get("x1", 0)), float(line.get("y1", 0))),
                    ]
                )
            issues = ["blocking:pdf_scale_confirmation_required"]
            if source.calibration_status == CalibrationStatus.CONFIRMED:
                issues = ["review:pdf_geometry_requires_engineer_classification"]
            elements.append(
                DetectedElement(
                    id=_stable_element_id(source.id, f"pdf-page:{page_number}"),
                    source_id=source.id,
                    discipline=source.discipline,
                    element_type="pdf_evidence",
                    floor=source.floor,
                    source_handle=f"page-{page_number}",
                    geometry=Geometry(
                        kind="pdf_page",
                        points=points,
                        bbox=(0.0, 0.0, float(page.width), float(page.height)),
                    ),
                    properties={
                        "page": page_number,
                        "text_excerpt": re.sub(r"\s+", " ", text)[:1000],
                        "vector_line_count": len(lines),
                        "calibration_scale": source.calibration_scale,
                    },
                    confidence=0.7 if text else 0.4,
                    review_status=ReviewStatus.NEEDS_REVIEW,
                    issues=issues,
                )
            )
    if scanned_pages:
        ocr_pages = _run_local_pdf_ocr(path)
        for page_number, dimensions in scanned_pages.items():
            ocr = ocr_pages.get(page_number)
            if ocr is None or not str(ocr.get("text", "")).strip():
                warnings.append(
                    AnalysisWarning(
                        code="SCANNED_PDF_OCR_REQUIRED",
                        message=(
                            f"PDF sayfa {page_number} taranmış görünüyor; yerel OCR "
                            "çalışma zamanı bulunamadı veya metin okuyamadı."
                        ),
                        source_id=source.id,
                        severity="warning",
                    )
                )
                continue
            issues = ["blocking:pdf_scale_confirmation_required"]
            if source.calibration_status == CalibrationStatus.CONFIRMED:
                issues = ["review:ocr_text_requires_engineer_classification"]
            text = str(ocr["text"])
            confidence = float(ocr.get("confidence", 0.0))
            elements.append(
                DetectedElement(
                    id=_stable_element_id(source.id, f"pdf-ocr-page:{page_number}"),
                    source_id=source.id,
                    discipline=source.discipline,
                    element_type="pdf_evidence",
                    floor=source.floor,
                    source_handle=f"page-{page_number}-ocr",
                    geometry=Geometry(
                        kind="pdf_ocr_page",
                        bbox=(0.0, 0.0, dimensions[0], dimensions[1]),
                    ),
                    properties={
                        "page": page_number,
                        "text_excerpt": re.sub(r"\s+", " ", text)[:1000],
                        "ocr_engine": "Apple Vision (on-device)",
                        "calibration_scale": source.calibration_scale,
                    },
                    confidence=max(0.0, min(confidence, 1.0)),
                    review_status=ReviewStatus.NEEDS_REVIEW,
                    issues=issues,
                )
            )
            warnings.append(
                AnalysisWarning(
                    code="SCANNED_PDF_OCR_EXTRACTED",
                    message=(
                        f"PDF sayfa {page_number} metni cihazdaki Apple Vision ile okundu; "
                        "ölçü ve eleman eşleştirmesi mühendis onayı bekliyor."
                    ),
                    source_id=source.id,
                    severity="info",
                )
            )
    return elements, warnings, DrawingUnit.UNKNOWN


def _run_local_pdf_ocr(path: Path) -> dict[int, dict[str, Any]]:
    configured = os.environ.get("METRAJAI_OCR_BINARY", "").strip()
    candidates = [Path(configured)] if configured else []
    candidates.extend(
        [
            Path(sys.executable).resolve().parent / "metrajai-ocr",
            Path(__file__).resolve().parents[1]
            / "desktop"
            / "src-tauri"
            / "resources"
            / "metrajai-ocr",
        ]
    )
    binary = next((candidate for candidate in candidates if candidate.is_file()), None)
    if binary is None:
        return {}
    try:
        completed = subprocess.run(
            [str(binary), str(path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        payload = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, list):
        return {}
    return {
        int(item["page"]): item
        for item in payload
        if isinstance(item, dict) and isinstance(item.get("page"), int)
    }


def analyze_non_dxf_source(
    source: SourceFile, path: Path
) -> tuple[list[DetectedElement], list[AnalysisWarning], DrawingUnit]:
    if source.source_format in (SourceFormat.XLS, SourceFormat.XLSX):
        return analyze_spreadsheet_source(source, path)
    if source.source_format == SourceFormat.PDF:
        return analyze_pdf_source(source, path)
    return (
        [],
        [
            AnalysisWarning(
                code="UNSUPPORTED_SOURCE_FORMAT",
                message=f"Kaynak biçimi analiz edilemiyor: {source.source_format.value}",
                source_id=source.id,
                severity="error",
            )
        ],
        DrawingUnit.UNKNOWN,
    )
