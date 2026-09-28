from __future__ import annotations

import unicodedata
from pathlib import Path

import ezdxf

from ..contracts import Discipline, DrawingUnit, SheetKind, SourceFile, SourceFormat
from ..units import unit_from_insunits
from .architectural_plan import extract_architectural_plan


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    return " ".join(
        "".join(character for character in value if not unicodedata.combining(character))
        .upper()
        .split()
    )


def _drawing_texts(document) -> list[str]:
    values: list[str] = []
    for entity in document.modelspace():
        if entity.dxftype() == "TEXT":
            values.append(_normalize(str(entity.dxf.text)))
        elif entity.dxftype() == "MTEXT":
            values.append(_normalize(str(entity.plain_text())))
    return values


def _discipline_evidence(document) -> tuple[Discipline | None, list[str]]:
    texts = _drawing_texts(document)
    architectural_phrases = (
        "MAHAL TABLOSU", "MAHAL LISTESI", "ZEMIN KAT PLANI", "VAZIYET PLANI",
        "CATI PLANI", "GORUNUSLER", "ASMA TAVAN PLANI",
    )
    structural_phrases = (
        "KALIP PLANI", "KOLON APLIKASYON", "DONATI PLANI", "KIRIS DONATI",
        "TEMEL KALIP", "RADYE TEMEL PLANI",
    )
    architectural = [
        phrase for phrase in architectural_phrases if any(phrase in text for text in texts)
    ]
    structural = [phrase for phrase in structural_phrases if any(phrase in text for text in texts)]
    if len(architectural) >= 2 and not structural:
        return Discipline.ARCHITECTURAL, architectural
    if structural and len(architectural) < 2:
        return Discipline.STRUCTURAL, structural
    return None, architectural + structural


def inspect_dxf_document(document, original_name: str, *, check_area: bool = False) -> dict:
    header_unit = unit_from_insunits(document.header.get("$INSUNITS", 0))
    suggested_discipline, discipline_evidence = _discipline_evidence(document)
    suggested_unit = header_unit
    unit_evidence = [
        f"DXF başlığı: {header_unit.value}" if header_unit != DrawingUnit.UNKNOWN
        else "DXF başlığında kullanılabilir birim yok"
    ]
    area_ratio: float | None = None
    if (
        check_area
        and suggested_discipline == Discipline.ARCHITECTURAL
        and header_unit != DrawingUnit.UNKNOWN
    ):
        source = SourceFile(
            project_id="inspection",
            original_name=original_name,
            stored_path="inspection",
            sha256="inspection",
            size_bytes=0,
            source_format=SourceFormat.DXF,
            discipline=Discipline.ARCHITECTURAL,
            role="mimari",
            sheet_kind=SheetKind.PLAN,
        )
        _, warnings = extract_architectural_plan(document, source, header_unit)
        mismatch = next(
            (item for item in warnings if item.code == "ARCHITECTURAL_UNIT_EVIDENCE_MISMATCH"),
            None,
        )
        if mismatch is not None:
            raw_ratio = mismatch.evidence.get("area_ratio")
            if isinstance(raw_ratio, (float, int)):
                area_ratio = float(raw_ratio)
                if header_unit == DrawingUnit.MM and 80 <= area_ratio <= 120:
                    suggested_unit = DrawingUnit.CM
                elif header_unit == DrawingUnit.CM and 0.008 <= area_ratio <= 0.012:
                    suggested_unit = DrawingUnit.MM
                unit_evidence.append(
                    f"Yazılı mahal alanı / geometri alanı: {area_ratio:.1f} kat"
                )
                if suggested_unit != header_unit:
                    unit_evidence.append(f"Alan kanıtı {suggested_unit.value} birimini öneriyor")

    conflict = suggested_unit != header_unit and suggested_unit != DrawingUnit.UNKNOWN
    return {
        "source_format": "dxf",
        "header_unit": header_unit.value,
        "suggested_unit": suggested_unit.value,
        "unit_conflict": conflict,
        "requires_unit_confirmation": header_unit == DrawingUnit.UNKNOWN or conflict,
        "unit_evidence": unit_evidence,
        "area_ratio": area_ratio,
        "suggested_discipline": suggested_discipline.value if suggested_discipline else None,
        "discipline_evidence": discipline_evidence,
    }


def inspect_source_file(path: str | Path, *, check_area: bool = True) -> dict:
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if source_path.suffix.lower() != ".dxf":
        if source_path.suffix.lower() not in {".xlsx", ".xls", ".pdf"}:
            raise ValueError("Desteklenen kaynak biçimleri: DXF, XLSX, XLS ve PDF")
        return {
            "source_format": source_path.suffix.lower().lstrip("."),
            "header_unit": "unknown",
            "suggested_unit": "unknown",
            "unit_conflict": False,
            "requires_unit_confirmation": False,
            "unit_evidence": [],
            "area_ratio": None,
            "suggested_discipline": None,
            "discipline_evidence": [],
        }
    document = ezdxf.readfile(source_path)
    return inspect_dxf_document(document, source_path.name, check_area=check_area)
