from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import ezdxf

from ..contracts import (
    AnalysisWarning,
    DetectedElement,
    Discipline,
    ReviewStatus,
    SourceFile,
)

LEVEL_TEXT = re.compile(r"^(?P<marker>%%P|[+\-±])?\s*(?P<value>\d+(?:[.,]\d+)?)\s*$")
FLOOR_TOKENS = (
    "BODRUM KAT",
    "ZEMIN KAT",
    "GIRIS KATI",
    "ASMA KAT",
    "NORMAL KAT",
    "1. KAT",
    "2. KAT",
    "3. KAT",
    "4. KAT",
    "5. KAT",
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    ).upper()


def _text(entity) -> str:
    if entity.dxftype() == "TEXT":
        return str(entity.dxf.text).strip()
    if entity.dxftype() == "MTEXT":
        return str(entity.plain_text()).strip()
    return ""


def _level(value: str) -> tuple[float, bool] | None:
    match = LEVEL_TEXT.fullmatch(value.strip())
    if match is None:
        return None
    number = float(match.group("value").replace(",", "."))
    marker = match.group("marker") or ""
    if marker == "-":
        number *= -1
    return number, bool(marker) or number == 0


def _floor_label(texts: list[str]) -> str:
    normalized = [_normalize(value) for value in texts]
    for token in FLOOR_TOKENS:
        if any(token in value for value in normalized):
            return token.title()
    return ""


@dataclass(frozen=True)
class ArchitecturalHeightEvidence:
    source_id: str
    source_name: str
    floor_label: str
    lower_level_m: float
    upper_level_m: float
    height_m: float
    block_name: str
    source_handles: tuple[str, ...]
    confidence: float = 0.98

    def trace(self) -> dict[str, str | float | list[str]]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "floor_label": self.floor_label,
            "lower_level_m": self.lower_level_m,
            "upper_level_m": self.upper_level_m,
            "height_m": self.height_m,
            "block_name": self.block_name,
            "source_handles": list(self.source_handles),
            "method": "architectural_section_level_difference",
        }


def extract_architectural_height_evidence(
    document,
    source: SourceFile,
) -> list[ArchitecturalHeightEvidence]:
    """Read explicit storey levels from referenced architectural section blocks."""
    references: dict[str, list[str]] = {}
    for entity in document.modelspace():
        if entity.dxftype() != "INSERT":
            continue
        references.setdefault(str(entity.dxf.name), []).append(str(entity.dxf.handle))

    evidence: list[ArchitecturalHeightEvidence] = []
    for block_name, handles in references.items():
        try:
            block = document.blocks.get(block_name)
        except Exception:
            continue
        texts = [value for entity in block if (value := _text(entity))]
        floor_label = _floor_label(texts)
        if not floor_label:
            continue
        parsed_levels = [parsed for value in texts if (parsed := _level(value)) is not None]
        levels = sorted({round(value, 4) for value, explicit in parsed_levels if explicit})
        if len(levels) != 2:
            continue
        lower, upper = levels
        height = round(upper - lower, 4)
        if not 2.0 <= height <= 8.0:
            continue
        evidence.append(
            ArchitecturalHeightEvidence(
                source_id=source.id,
                source_name=source.original_name,
                floor_label=floor_label,
                lower_level_m=lower,
                upper_level_m=upper,
                height_m=height,
                block_name=block_name,
                source_handles=tuple(sorted(handles)),
            )
        )
    return evidence


def extract_architectural_height_evidence_from_path(
    source: SourceFile,
    path: str | Path,
) -> list[ArchitecturalHeightEvidence]:
    if Path(path).suffix.lower() != ".dxf":
        return []
    return extract_architectural_height_evidence(ezdxf.readfile(path), source)


def evidence_warnings(
    source: SourceFile,
    evidence: list[ArchitecturalHeightEvidence],
) -> list[AnalysisWarning]:
    if not evidence:
        return [
            AnalysisWarning(
                code="ARCHITECTURAL_HEIGHT_NOT_FOUND",
                message=(
                    f"{source.original_name}: mimari kesitte aynı katı tanımlayan iki açık "
                    "kot bulunamadı. Yükseklik otomatik doldurulmadı."
                ),
                source_id=source.id,
            )
        ]
    return [
        AnalysisWarning(
            code="ARCHITECTURAL_HEIGHT_EVIDENCE",
            message=(
                f"Mimari kesitte {item.floor_label} için {item.lower_level_m:+g} ile "
                f"{item.upper_level_m:+g} kotları okundu: yükseklik {item.height_m:g} m."
            ),
            source_id=item.source_id,
            severity="info",
        )
        for item in evidence
    ]


def _floor_matches(element: DetectedElement, item: ArchitecturalHeightEvidence) -> bool:
    element_floor = _normalize(element.floor)
    evidence_floor = _normalize(item.floor_label)
    return (
        element_floor == "GENEL"
        or element_floor in evidence_floor
        or evidence_floor in element_floor
    )


def apply_architectural_heights(
    elements: list[DetectedElement],
    evidence: list[ArchitecturalHeightEvidence],
) -> tuple[list[DetectedElement], int]:
    unique_heights = {round(item.height_m, 4) for item in evidence}
    if len(unique_heights) != 1:
        return elements, 0

    applied = 0
    for element in elements:
        if element.discipline != Discipline.STRUCTURAL:
            continue
        if element.element_type not in {"column", "shear_wall"}:
            continue
        matching = [item for item in evidence if _floor_matches(element, item)]
        if not matching:
            continue
        item = matching[0]
        current = element.measurements.get("height_m")
        if current is not None and current > 0:
            continue
        element.measurements["height_m"] = item.height_m
        element.properties["height_evidence"] = item.trace()
        element.issues = [issue for issue in element.issues if issue != "missing:height_m"]
        element.issues.append("review:architectural_height_evidence")
        if element.review_status not in {ReviewStatus.ACCEPTED, ReviewStatus.REJECTED}:
            element.review_status = ReviewStatus.NEEDS_REVIEW
        element.confidence = max(element.confidence, 0.88)
        applied += 1
    return elements, applied
