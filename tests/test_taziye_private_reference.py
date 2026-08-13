from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from metrajai.analyzers import DxfAnalyzer
from metrajai.contracts import Discipline, DrawingUnit, SourceFile, SourceFormat

EXPECTED_SHA256 = "73ba0b231e49766564dadb46aa7dcdbc6d1d89fa4824d6e2d2672d02e1e1700e"


def _private_drawing() -> Path:
    roots = (
        Path(__file__).resolve().parents[1] / "INPUT",
        Path.home() / "Downloads" / "Taziye Evi" / "sources",
    )
    for root in roots:
        for path in root.glob("*.dxf"):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest == EXPECTED_SHA256:
                return path
    pytest.skip("özel Taziye mimari paftası yerel test alanında yok")


def _source(path: Path, unit: DrawingUnit) -> SourceFile:
    return SourceFile(
        id="src_taziye_private",
        project_id="prj_taziye_private",
        original_name=path.name,
        stored_path=str(path),
        sha256=EXPECTED_SHA256,
        size_bytes=path.stat().st_size,
        source_format=SourceFormat.DXF,
        discipline=Discipline.ARCHITECTURAL,
        role="mimari plan",
        drawing_unit=unit,
        detected_unit=DrawingUnit.MM,
        unit_confirmed=True,
    )


def test_taziye_unit_evidence_and_plan_region_are_conservative() -> None:
    path = _private_drawing()

    millimetre_elements, millimetre_warnings, _ = DxfAnalyzer().analyze(
        _source(path, DrawingUnit.MM), path
    )
    mismatch = next(
        warning
        for warning in millimetre_warnings
        if warning.code == "ARCHITECTURAL_UNIT_EVIDENCE_MISMATCH"
    )
    assert "cm olarak doğrulanması" in mismatch.message
    physical_elements = [
        element
        for element in millimetre_elements
        if element.geometry.kind != "architectural_schedule_row"
    ]
    assert physical_elements
    assert all(
        "blocking:drawing_unit_evidence_mismatch" in element.issues
        for element in physical_elements
    )

    elements, warnings, _ = DxfAnalyzer().analyze(_source(path, DrawingUnit.CM), path)
    rooms = [element for element in elements if element.element_type == "room"]
    openings = [element for element in elements if element.element_type in {"door", "window"}]

    assert {str(room.properties.get("room_code")) for room in rooms} == {
        f"ZK{index:02d}" for index in range(1, 11)
    }
    assert sum(room.measurements["area_m2"] for room in rooms) == pytest.approx(166.94)
    assert all(room.geometry.kind == "room_boundary" for room in rooms)
    assert all("blocking:room_schedule_geometry_mismatch" in room.issues for room in rooms)
    assert len(openings) == 27
    assert all(opening.source_handle.startswith("2DB1/") for opening in openings)
    assert not any(
        warning.code == "ARCHITECTURAL_UNIT_EVIDENCE_MISMATCH" for warning in warnings
    )
