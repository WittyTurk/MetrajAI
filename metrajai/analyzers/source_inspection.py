from __future__ import annotations

import unicodedata
from pathlib import Path

import ezdxf

from ..contracts import Discipline, DrawingUnit, FloorKind, SheetKind, SourceFile, SourceFormat
from ..units import suggest_unit_from_area_ratio, unit_from_insunits
from .architectural_plan import extract_architectural_plan
from .structural_plan import inspect_structural_unit


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
        "MAHAL TABLOSU",
        "MAHAL LISTESI",
        "ZEMIN KAT PLANI",
        "VAZIYET PLANI",
        "CATI PLANI",
        "GORUNUSLER",
        "ASMA TAVAN PLANI",
    )
    structural_phrases = (
        "KALIP PLANI",
        "KOLON APLIKASYON",
        "DONATI PLANI",
        "KIRIS DONATI",
        "TEMEL KALIP",
        "RADYE TEMEL PLANI",
    )
    other_phrases = {
        Discipline.MECHANICAL: ("MEKANIK TESISAT", "SIHHI TESISAT", "HAVALANDIRMA PROJESI"),
        Discipline.ELECTRICAL: ("ELEKTRIK TESISAT", "AYDINLATMA PROJESI", "KUVVETLI AKIM PROJESI"),
        Discipline.LANDSCAPE: ("PEYZAJ PROJESI", "CEVRE DUZENLEME PROJESI", "BITKISEL PROJE"),
    }
    architectural = [
        phrase for phrase in architectural_phrases if any(phrase in text for text in texts)
    ]
    structural = [phrase for phrase in structural_phrases if any(phrase in text for text in texts)]
    other = {
        discipline: [phrase for phrase in phrases if any(phrase in text for text in texts)]
        for discipline, phrases in other_phrases.items()
    }
    found_other = [(discipline, evidence) for discipline, evidence in other.items() if evidence]
    if len(found_other) == 1 and not structural and len(architectural) < 2:
        return found_other[0]
    if found_other:
        return None, architectural + structural + [
            phrase for _, evidence in found_other for phrase in evidence
        ]
    if len(architectural) >= 2 and not structural:
        return Discipline.ARCHITECTURAL, architectural
    if structural and len(architectural) < 2:
        return Discipline.STRUCTURAL, structural
    return None, architectural + structural


def _sheet_evidence(document, discipline: Discipline | None) -> tuple[SheetKind | None, list[str]]:
    if discipline is None:
        return None, []
    texts = _drawing_texts(document)
    physical: list[tuple[SheetKind, str]] = []
    if discipline == Discipline.STRUCTURAL:
        for kind, phrase in (
            (SheetKind.COLUMN_APPLICATION, "KOLON APLIKASYON"),
            (SheetKind.REBAR_PLAN, "DONATI PLANI"),
            (SheetKind.FOUNDATION, "TEMEL KALIP"),
            (SheetKind.FOUNDATION, "RADYE TEMEL PLANI"),
        ):
            if any(phrase in text for text in texts):
                physical.append((kind, phrase))
        if any("KALIP PLANI" in text and "TEMEL KALIP" not in text for text in texts):
            physical.append((SheetKind.PLAN, "KALIP PLANI"))
    elif discipline == Discipline.ARCHITECTURAL:
        for phrase in (
            "ZEMIN KAT PLANI",
            "BODRUM KAT PLANI",
            "NORMAL KAT PLANI",
            "CATI PLANI",
            "ASMA TAVAN PLANI",
        ):
            if any(phrase in text for text in texts):
                physical.append((SheetKind.PLAN, phrase))
    # A drawing may contain plan, section and schedule regions together. In that case
    # its source role is the physical plan; region filtering remains the analyzer's job.
    kinds = {kind for kind, _ in physical}
    if len(kinds) == 1:
        return next(iter(kinds)), [phrase for _, phrase in physical]
    if kinds:
        return None, [phrase for _, phrase in physical]
    reference = [
        (SheetKind.SCHEDULE, "MAHAL TABLOSU"),
        (SheetKind.SCHEDULE, "MAHAL LISTESI"),
        (SheetKind.SECTION, "KESIT"),
        (SheetKind.ELEVATION, "GORUNUS"),
        (SheetKind.DETAIL, "DETAY"),
    ]
    found = [(kind, phrase) for kind, phrase in reference if any(phrase in text for text in texts)]
    return (
        found[0][0] if len({kind for kind, _ in found}) == 1 else None,
        [phrase for _, phrase in found],
    )


def _floor_evidence(document) -> tuple[str | None, FloorKind | None]:
    texts = _drawing_texts(document)
    candidates = [
        ("Bodrum Kat", FloorKind.BASEMENT, "BODRUM KAT PLANI"),
        ("Zemin Kat", FloorKind.GROUND, "ZEMIN KAT PLANI"),
        ("Normal Kat", FloorKind.TYPICAL, "NORMAL KAT PLANI"),
        ("Çatı", FloorKind.ROOF, "CATI PLANI"),
        ("Temel", FloorKind.FOUNDATION, "TEMEL KALIP"),
    ]
    matches = [
        (name, kind) for name, kind, phrase in candidates if any(phrase in text for text in texts)
    ]
    return matches[0] if len(matches) == 1 else (None, None)


def inspect_dxf_document(document, original_name: str, *, check_area: bool = False) -> dict:
    header_unit = unit_from_insunits(document.header.get("$INSUNITS", 0))
    suggested_discipline, discipline_evidence = _discipline_evidence(document)
    suggested_sheet_kind, sheet_evidence = _sheet_evidence(document, suggested_discipline)
    suggested_floor, suggested_floor_kind = (
        _floor_evidence(document) if suggested_sheet_kind else (None, None)
    )
    suggested_unit = header_unit
    unit_evidence_basis = "header"
    unit_evidence = [
        f"DXF başlığı: {header_unit.value}"
        if header_unit != DrawingUnit.UNKNOWN
        else "DXF başlığında kullanılabilir birim yok"
    ]
    area_ratio: float | None = None
    ambiguous_unit = False
    if check_area and suggested_discipline == Discipline.STRUCTURAL:
        structural_unit, structural_evidence, geometric_candidate = inspect_structural_unit(
            document
        )
        unit_evidence.extend(structural_evidence)
        if structural_unit is not None:
            suggested_unit = structural_unit
            unit_evidence_basis = "structural_sections"
        elif geometric_candidate is not None and geometric_candidate != header_unit:
            # The header contradicts physical geometry, but there is not enough
            # written evidence to recommend a replacement unit confidently.
            suggested_unit = DrawingUnit.UNKNOWN
            ambiguous_unit = True
            unit_evidence_basis = "geometry_only"
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
                area_candidate = suggest_unit_from_area_ratio(header_unit, area_ratio)
                if area_candidate is not None and area_candidate != header_unit:
                    suggested_unit = area_candidate
                    unit_evidence_basis = "architectural_area"
                unit_evidence.append(f"Yazılı mahal alanı / geometri alanı: {area_ratio:.1f} kat")
                if suggested_unit != header_unit:
                    unit_evidence.append(f"Alan kanıtı {suggested_unit.value} birimini öneriyor")

    conflict = suggested_unit != header_unit and suggested_unit != DrawingUnit.UNKNOWN
    return {
        "source_format": "dxf",
        "header_unit": header_unit.value,
        "suggested_unit": suggested_unit.value,
        "unit_conflict": conflict,
        "requires_unit_confirmation": header_unit == DrawingUnit.UNKNOWN
        or conflict
        or ambiguous_unit,
        "unit_evidence": unit_evidence,
        "unit_evidence_basis": unit_evidence_basis,
        "area_ratio": area_ratio,
        "suggested_discipline": suggested_discipline.value if suggested_discipline else None,
        "discipline_evidence": discipline_evidence,
        "suggested_sheet_kind": suggested_sheet_kind.value if suggested_sheet_kind else None,
        "sheet_evidence": sheet_evidence,
        "suggested_floor": suggested_floor,
        "suggested_floor_kind": suggested_floor_kind.value if suggested_floor_kind else None,
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
            "unit_evidence_basis": "not_applicable",
            "area_ratio": None,
            "suggested_discipline": None,
            "discipline_evidence": [],
            "suggested_sheet_kind": None,
            "sheet_evidence": [],
            "suggested_floor": None,
            "suggested_floor_kind": None,
        }
    document = ezdxf.readfile(source_path)
    return inspect_dxf_document(document, source_path.name, check_area=check_area)
