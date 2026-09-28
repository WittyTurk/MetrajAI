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

    elements, warnings, _ = DxfAnalyzer().analyze(_source(path), path)
    assert elements == []
    assert any(item.code == "SOURCE_DISCIPLINE_CONFLICT" for item in warnings)


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
