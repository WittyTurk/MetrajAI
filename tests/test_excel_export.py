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
        assert len(workbook.sheetnames) == 10
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
