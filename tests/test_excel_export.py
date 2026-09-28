from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from metrajai.calculations import calculate_quantities
from metrajai.contracts import (
    DetectedElement,
    Discipline,
    Geometry,
    MappingStatus,
    OfferScenario,
    PriceCatalog,
    PriceItem,
    PriceMapping,
    ReviewStatus,
)
from metrajai.excel_export import export_traceable_excel
from metrajai.reporting import build_report_payload
from metrajai.workspace import ProjectWorkspace


def test_excel_export_uses_bundled_python_runtime_without_private_node(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = ProjectWorkspace.create(tmp_path / "project", "Test")
    monkeypatch.delenv("METRAJAI_NODE_BINARY", raising=False)
    monkeypatch.delenv("METRAJAI_ARTIFACT_NODE_MODULES", raising=False)
    output = export_traceable_excel(workspace)
    assert output.is_file()
    workbook = load_workbook(output, read_only=True, data_only=False)
    try:
        assert len(workbook.sheetnames) == 11
        assert "Mimari Kırılım" in workbook.sheetnames
    finally:
        workbook.close()


def test_excel_keeps_schedule_net_and_gross_plan_area_separate(tmp_path: Path) -> None:
    workspace = ProjectWorkspace.create(tmp_path / "project", "Alan dayanağı")
    drawing = tmp_path / "plan.dxf"
    drawing.write_text("synthetic", encoding="utf-8")
    source = workspace.add_source(drawing, discipline=Discipline.ARCHITECTURAL, role="mimari")
    room = DetectedElement(
        id="ZK01", source_id=source.id, discipline=Discipline.ARCHITECTURAL,
        element_type="room", geometry=Geometry(kind="room_boundary"),
        measurements={"area_m2": 9.33, "geometric_area_m2": 10.719,
                      "gross_region_area_m2": 10.719},
        properties={"room_code": "ZK01", "room_area_basis": "schedule_net_gross_plan"},
        required_inputs=["area_m2"], review_status=ReviewStatus.ACCEPTED,
    )
    workspace.replace_source_elements(source.id, [room])
    workbook = load_workbook(export_traceable_excel(workspace), data_only=False)
    try:
        sheet = workbook["Mimari Kırılım"]
        assert sheet["H5"].value == pytest.approx(9.33)
        assert sheet["J5"].value == "=MAX(0,H5-I5)"
        assert sheet["S5"].value == pytest.approx(10.719)
        assert sheet["T5"].value == "schedule_net_gross_plan"
    finally:
        workbook.close()


def test_structural_report_marks_partial_scope_until_raft_and_rebar_are_resolved(
    tmp_path: Path,
) -> None:
    workspace = ProjectWorkspace.create(tmp_path / "project", "Statik")
    drawing = tmp_path / "plan.dxf"
    drawing.write_text("synthetic", encoding="utf-8")
    source = workspace.add_source(drawing, discipline=Discipline.STRUCTURAL, role="kalip")
    column = DetectedElement(
        id="column", source_id=source.id, discipline=Discipline.STRUCTURAL,
        element_type="column", geometry=Geometry(kind="rectangle", bbox=(0, 0, 0.4, 0.6)),
        measurements={"width_m": 0.4, "depth_m": 0.6, "height_m": 3},
        required_inputs=["width_m", "depth_m", "height_m"],
        review_status=ReviewStatus.ACCEPTED,
    )
    raft = DetectedElement(
        id="raft", source_id=source.id, discipline=Discipline.STRUCTURAL,
        element_type="raft", geometry=Geometry(kind="closed_outline", bbox=(0, 0, 10, 10)),
        measurements={"area_m2": 100}, required_inputs=["area_m2", "thickness_m"],
    )
    rebar = DetectedElement(
        id="rebar", source_id=source.id, discipline=Discipline.STRUCTURAL,
        element_type="rebar", geometry=Geometry(kind="schedule_row"),
        properties={"revision_candidates": [{"label": "A"}, {"label": "B"}]},
    )
    workspace.replace_source_elements(source.id, [column, raft, rebar])
    lines, _ = calculate_quantities([column, raft, rebar])
    workspace.replace_quantities(lines)

    payload = build_report_payload(workspace)
    assert payload["completion"]["structural_complete"] is False
    assert {item["code"] for item in payload["completion"]["blockers"]} == {
        "RAFT_THICKNESS_REQUIRED", "REBAR_REVISION_REQUIRED",
    }
    assert all(item["status"] == "partial" for item in payload["summary"])

    workbook = load_workbook(export_traceable_excel(workspace), read_only=False)
    try:
        assert workbook["Özet"]["F5"].value == "Kısmi · statik kapsam eksik"
        warning_codes = {
            workbook["Uyarılar"].cell(row, 2).value
            for row in range(5, workbook["Uyarılar"].max_row + 1)
        }
        assert {"RAFT_THICKNESS_REQUIRED", "REBAR_REVISION_REQUIRED"} <= warning_codes
    finally:
        workbook.close()


def test_excel_export_contains_traceable_offer_and_correct_stair_formulas(
    tmp_path: Path,
) -> None:
    if not os.environ.get("METRAJAI_NODE_BINARY") or not os.environ.get(
        "METRAJAI_ARTIFACT_NODE_MODULES"
    ):
        pytest.skip("artifact-tool runtime is not available in this environment")
    workspace = ProjectWorkspace.create(tmp_path / "project", "Teklif Testi")
    source_path = tmp_path / "stair.dxf"
    source_path.write_text("synthetic", encoding="utf-8")
    source = workspace.add_source(
        source_path,
        discipline=Discipline.STRUCTURAL,
        role="merdiven",
    )
    stair = DetectedElement(
        id="elm_stair_report",
        source_id=source.id,
        discipline=Discipline.STRUCTURAL,
        element_type="stair",
        floor="ZEMİN",
        source_handle="A1",
        geometry=Geometry(kind="closed_outline", bbox=(0, 0, 4, 1.2)),
        measurements={
            "plan_area_m2": 4.8,
            "horizontal_run_m": 4,
            "total_rise_m": 3,
            "waist_thickness_m": 0.15,
            "step_volume_m3": 0.5,
            "side_formwork_m2": 1.5,
            "riser_formwork_m2": 3.6,
        },
        required_inputs=[
            "plan_area_m2",
            "horizontal_run_m",
            "total_rise_m",
            "waist_thickness_m",
        ],
        confidence=1,
        review_status=ReviewStatus.ACCEPTED,
    )
    workspace.replace_source_elements(source.id, [stair])
    quantities, warnings = calculate_quantities([stair])
    assert not warnings
    workspace.replace_quantities(quantities)
    catalog = PriceCatalog(
        project_id=workspace.manifest.project_id,
        name="Pilot",
        year=2026,
        version="1",
        source_name="pilot.xlsx",
        sha256="b" * 64,
    )
    price = PriceItem(
        catalog_id=catalog.id,
        code="15.001",
        description="Merdiven betonu",
        unit=quantities[0].unit,
        unit_price=Decimal("2500"),
    )
    workspace.put_price_catalog(catalog, [price])
    workspace.put_price_mapping(
        PriceMapping(
            project_id=workspace.manifest.project_id,
            quantity_line_id=quantities[0].id,
            price_item_id=price.id,
            status=MappingStatus.APPROVED,
            reviewer="Mühendis",
            reason="Poz ve birim kontrol edildi",
        )
    )
    workspace.put_offer_scenario(
        OfferScenario(
            project_id=workspace.manifest.project_id,
            name="Ana teklif",
            approved=True,
            reviewer="Mühendis",
        )
    )

    output = export_traceable_excel(workspace, tmp_path / "report.xlsx")
    workbook = load_workbook(output, read_only=True, data_only=False)
    try:
        assert workbook.sheetnames == [
            "Özet",
            "Kaynaklar",
            "Elemanlar",
            "Metraj",
            "Varsayımlar",
            "Uyarılar",
            "Poz Eşleştirme",
            "Birim Fiyatlar",
            "Teklif Senaryosu",
            "Teklif Özeti",
            "Mimari Kırılım",
        ]
        metraj = workbook["Metraj"]
        formula_by_key = {
            line.formula_key: metraj.cell(row=index + 5, column=20).value
            for index, line in enumerate(quantities)
        }
        assert "SQRT" in formula_by_key["stair:0"]
        assert formula_by_key["stair:1"] == "=0.5"
        assert "SQRT" in formula_by_key["stair:6"]
        assert workbook["Teklif Özeti"]["E5"].value.startswith("=SUM(")
    finally:
        workbook.close()
