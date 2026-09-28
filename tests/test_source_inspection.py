from __future__ import annotations

import os
from pathlib import Path

import ezdxf
import pytest
from fastapi.testclient import TestClient

from metrajai.analyzers import DxfAnalyzer
from metrajai.analyzers.source_inspection import inspect_source_file
from metrajai.api import create_app
from metrajai.contracts import (
    DetectedElement,
    Discipline,
    DrawingUnit,
    Geometry,
    ReviewStatus,
    SheetKind,
    SourceFile,
)
from metrajai.workspace import ProjectWorkspace


def _source(path: Path) -> SourceFile:
    return SourceFile(
        project_id="diagnostic",
        original_name=path.name,
        stored_path=str(path),
        sha256="synthetic",
        size_bytes=path.stat().st_size,
        discipline=Discipline.STRUCTURAL,
        role="kalip",
        sheet_kind=SheetKind.PLAN,
        drawing_unit=DrawingUnit.CM,
        unit_confirmed=True,
    )


def test_architectural_titles_stop_structural_detection_and_api_offers_preflight(
    tmp_path: Path,
) -> None:
    path = tmp_path / "mixed_architecture.dxf"
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = 4
    model = document.modelspace()
    model.add_text("ZEMİN KAT PLANI")
    model.add_text("VAZİYET PLANI")
    marker = document.blocks.new("0.00")
    marker.add_text("%%P0.00", dxfattribs={"height": 50})
    model.add_blockref("0.00", (0, 0), dxfattribs={"layer": "KOLON"})
    document.saveas(path)

    client = TestClient(create_app("local-token"))
    response = client.post(
        "/system/inspect-source",
        json={"path": str(path)},
        headers={"x-metrajai-token": "local-token"},
    )
    assert response.status_code == 200
    assert response.json()["header_unit"] == "mm"
    assert response.json()["suggested_discipline"] == "architectural"
    assert response.json()["suggested_sheet_kind"] == "plan"
    assert response.json()["suggested_floor"] == "Zemin Kat"

    elements, warnings, _ = DxfAnalyzer().analyze(_source(path), path)
    assert elements == []
    assert any(item.code == "SOURCE_DISCIPLINE_CONFLICT" for item in warnings)


def test_preflight_leaves_mixed_physical_sheet_roles_unselected(tmp_path: Path) -> None:
    path = tmp_path / "mixed_structural.dxf"
    document = ezdxf.new("R2018")
    model = document.modelspace()
    model.add_text("KOLON APLIKASYON PLANI")
    model.add_text("TEMEL KALIP PLANI")
    document.saveas(path)

    inspection = inspect_source_file(path, check_area=False)
    assert inspection["suggested_discipline"] == "structural"
    assert inspection["suggested_sheet_kind"] is None
    assert inspection["suggested_floor"] is None
    assert set(inspection["sheet_evidence"]) == {"KOLON APLIKASYON", "TEMEL KALIP"}


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("SIHHI TESISAT PROJESI", "mechanical"),
        ("ELEKTRIK TESISAT PROJESI", "electrical"),
        ("CEVRE DUZENLEME PROJESI", "landscape"),
    ],
)
def test_preflight_suggests_other_disciplines_from_strong_titles(
    title: str, expected: str, tmp_path: Path
) -> None:
    path = tmp_path / "drawing.dxf"
    document = ezdxf.new("R2018")
    document.modelspace().add_text(title)
    document.saveas(path)
    inspection = inspect_source_file(path, check_area=False)
    assert inspection["suggested_discipline"] == expected


def _structural_unit_drawing(
    path: Path, *, header_unit: int, labels: int = 3, section_width: int = 40
) -> None:
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = header_unit
    model = document.modelspace()
    model.add_text("DONATISIZ KALIP PLANI", dxfattribs={"insert": (0, -150)})
    for index in range(9):
        block_name = f"COLUMN_{index}"
        block = document.blocks.new(block_name)
        x, y = 100 + (index % 3) * 300, 100 + (index // 3) * 250
        block.add_lwpolyline(
            [(x, y), (x + 40, y), (x + 40, y + 60), (x, y + 60)],
            close=True,
        )
        model.add_blockref(block_name, (0, 0), dxfattribs={"layer": "KOLON"})
    for index in range(3):
        y = 100 + index * 250
        for edge in range(2):
            block_name = f"BEAM_{index}_{edge}"
            block = document.blocks.new(block_name)
            block.add_line((140, y + edge * 40), (440, y + edge * 40))
            model.add_blockref(block_name, (0, 0), dxfattribs={"layer": "KIRIS"})
        if index < labels:
            block_name = f"BEAM_LABEL_{index}"
            block = document.blocks.new(block_name)
            block.add_text(
                f"KZ{index + 1:02d} {section_width}/60",
                dxfattribs={"insert": (250, y + 10), "height": 10},
            )
            model.add_blockref(block_name, (0, 0), dxfattribs={"layer": "KIRIS"})
    document.saveas(path)


@pytest.mark.parametrize(
    ("header_unit", "labels", "expected_unit", "conflict", "confirmation"),
    [
        (6, 3, "cm", True, True),
        (5, 3, "cm", False, False),
        (6, 1, "unknown", False, True),
    ],
)
def test_structural_preflight_checks_sections_against_geometry(
    tmp_path: Path,
    header_unit: int,
    labels: int,
    expected_unit: str,
    conflict: bool,
    confirmation: bool,
) -> None:
    path = tmp_path / "structural.dxf"
    _structural_unit_drawing(path, header_unit=header_unit, labels=labels)
    inspection = inspect_source_file(path)
    assert inspection["suggested_discipline"] == "structural"
    assert inspection["suggested_unit"] == expected_unit
    assert inspection["unit_conflict"] is conflict
    assert inspection["requires_unit_confirmation"] is confirmation
    assert inspection["unit_evidence_basis"] == (
        "structural_sections" if expected_unit == "cm" else "geometry_only"
    )
    assert any("kiriş kesit" in item for item in inspection["unit_evidence"])


def test_written_structural_sections_block_wrong_selected_unit(tmp_path: Path) -> None:
    path = tmp_path / "sections.dxf"
    _structural_unit_drawing(path, header_unit=6)
    analyzer = DxfAnalyzer()

    wrong = _source(path).model_copy(update={"drawing_unit": DrawingUnit.M})
    wrong_elements, wrong_warnings, _ = analyzer.analyze(wrong, path)
    assert wrong_elements
    assert any(item.code == "UNIT_EVIDENCE_CONFLICT" and item.severity == "error"
               for item in wrong_warnings)
    assert all("blocking:drawing_unit_evidence_mismatch" in item.issues
               for item in wrong_elements)

    correct = _source(path)
    correct_elements, correct_warnings, _ = analyzer.analyze(correct, path)
    assert correct_elements
    assert any(item.code == "UNIT_EVIDENCE_VERIFIED" for item in correct_warnings)
    assert all("blocking:drawing_unit_evidence_mismatch" not in item.issues
               for item in correct_elements)


def test_imported_source_can_be_reinspected_without_changing_selected_unit(tmp_path: Path) -> None:
    drawing = tmp_path / "structural.dxf"
    _structural_unit_drawing(drawing, header_unit=6)
    workspace = ProjectWorkspace.create(tmp_path / "project", "Statik")
    source = workspace.add_source(
        drawing, discipline=Discipline.STRUCTURAL, role="kalip",
        drawing_unit=DrawingUnit.CM,
    )
    client = TestClient(create_app("local-token"))
    response = client.post(
        "/projects/open",
        json={"path": str(workspace.root)},
        headers={"x-metrajai-token": "local-token"},
    )
    assert response.status_code == 200
    response = client.get(
        f"/projects/{source.project_id}/sources/{source.id}/inspection",
        headers={"x-metrajai-token": "local-token"},
    )
    assert response.status_code == 200
    assert response.json()["suggested_unit"] == "cm"
    assert ProjectWorkspace(workspace.root).get_source(source.id).drawing_unit == DrawingUnit.CM


def test_structural_preflight_does_not_trust_conflicting_section_labels(tmp_path: Path) -> None:
    drawing = tmp_path / "wrong_sections.dxf"
    _structural_unit_drawing(drawing, header_unit=6, section_width=50)
    inspection = inspect_source_file(drawing)
    assert inspection["suggested_unit"] == "unknown"
    assert inspection["requires_unit_confirmation"] is True
    assert any("0/3" in item for item in inspection["unit_evidence"])


def test_elevation_insert_on_column_layer_is_not_a_column(tmp_path: Path) -> None:
    path = tmp_path / "column_and_level.dxf"
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = 5
    marker = document.blocks.new("0.00")
    marker.add_text("%%P0.00", dxfattribs={"height": 50})
    column = document.blocks.new("C40X60")
    column.add_lwpolyline([(0, 0), (40, 0), (40, 60), (0, 60)], close=True)
    model = document.modelspace()
    model.add_blockref("0.00", (0, 0), dxfattribs={"layer": "KOLON"})
    model.add_blockref("C40X60", (100, 0), dxfattribs={"layer": "KOLON"})
    document.saveas(path)

    elements, _, _ = DxfAnalyzer().analyze(_source(path), path)
    columns = [item for item in elements if item.element_type == "column"]
    assert len(columns) == 1
    assert columns[0].block_name == "C40X60"
    assert columns[0].measurements["width_m"] == pytest.approx(0.4)


def test_old_misclassified_results_are_backed_up_and_quarantined(tmp_path: Path) -> None:
    path = tmp_path / "old_architecture.dxf"
    document = ezdxf.new("R2018")
    model = document.modelspace()
    model.add_text("ZEMİN KAT PLANI")
    model.add_text("VAZİYET PLANI")
    document.saveas(path)
    project_path = tmp_path / "project"
    workspace = ProjectWorkspace.create(project_path, "Test")
    source = workspace.add_source(
        path,
        discipline=Discipline.STRUCTURAL,
        role="kalip",
        drawing_unit=DrawingUnit.CM,
    )
    workspace.replace_source_elements(
        source.id,
        [DetectedElement(
            source_id=source.id,
            discipline=Discipline.STRUCTURAL,
            element_type="column",
            geometry=Geometry(kind="rectangle", bbox=(0, 0, 1, 1)),
            measurements={"width_m": 1, "depth_m": 1, "height_m": 3},
            review_status=ReviewStatus.ACCEPTED,
        )],
    )

    reopened = ProjectWorkspace(project_path)
    assert reopened.list_elements(source_id=source.id) == []
    assert reopened.get_source(source.id).discipline == Discipline.STRUCTURAL
    assert reopened.list_backups()
    assert any("mimari pafta" in notice for notice in reopened.summary()["source_safety_notices"])

    reopened.update_source_discipline(source.id, Discipline.ARCHITECTURAL)
    assert reopened.summary()["source_safety_notices"] == []


@pytest.mark.skipif(not os.getenv("METRAJAI_PRIVATE_DXF"), reason="özel DXF sağlanmadı")
def test_private_taziye_unit_and_discipline_regression() -> None:
    path = Path(os.environ["METRAJAI_PRIVATE_DXF"])
    inspection = inspect_source_file(path)
    assert inspection["header_unit"] == "mm"
    assert inspection["suggested_unit"] == "cm"
    assert inspection["unit_conflict"] is True
    assert inspection["suggested_discipline"] == "architectural"

    elements, warnings, _ = DxfAnalyzer().analyze(_source(path), path)
    assert elements == []
    assert any(item.code == "SOURCE_DISCIPLINE_CONFLICT" for item in warnings)
