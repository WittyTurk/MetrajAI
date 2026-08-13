from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook
from pypdf import PdfWriter

from metrajai.calculations import calculate_quantities
from metrajai.commercial import calculate_offer, import_price_catalog_file
from metrajai.contracts import (
    AdjustmentBase,
    AdjustmentKind,
    CalibrationStatus,
    DetectedElement,
    Discipline,
    FloorDefinition,
    FloorKind,
    Geometry,
    MappingStatus,
    OfferAdjustment,
    OfferScenario,
    PriceMapping,
    QuantityLine,
    RepeatAssignment,
    RepeatScope,
    ReviewDecision,
    ReviewStatus,
    SourceFile,
    SourceFormat,
    ValidationGate,
)
from metrajai.floor_management import expand_approved_repeat_assignments
from metrajai.source_analyzers import analyze_pdf_source, analyze_spreadsheet_source
from metrajai.workspace import CURRENT_SCHEMA_VERSION, ProjectWorkspace


def _element(source_id: str, label: str = "M1") -> DetectedElement:
    return DetectedElement(
        id=f"elm_{label.lower()}",
        source_id=source_id,
        discipline=Discipline.STRUCTURAL,
        element_type="stair",
        floor="1. KAT",
        geometry=Geometry(kind="polyline", bbox=(0, 0, 4, 1.2)),
        measurements={
            "plan_area_m2": 4.8,
            "horizontal_run_m": 4,
            "total_rise_m": 3,
            "waist_thickness_m": 0.15,
        },
        properties={"element_label": label},
        required_inputs=[
            "plan_area_m2",
            "horizontal_run_m",
            "total_rise_m",
            "waist_thickness_m",
        ],
        confidence=0.9,
        review_status=ReviewStatus.PENDING,
        issues=["blocking:stair_floor_repeat_required"],
    )


def test_schema_migration_creates_recovery_backup(tmp_path: Path) -> None:
    root = tmp_path / "pilot.metrajai"
    workspace = ProjectWorkspace.create(root, "Pilot")
    manifest = workspace.manifest.model_dump(mode="json")
    manifest["schema_version"] = 1
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    migrated = ProjectWorkspace(root)

    assert migrated.manifest.schema_version == CURRENT_SCHEMA_VERSION
    backups = migrated.list_backups()
    assert len(backups) == 1
    assert f"schema-v1-to-v{CURRENT_SCHEMA_VERSION}" in backups[0]["path"]
    assert (Path(backups[0]["path"]) / "project.metrajai.sqlite3").is_file()


def test_template_repeat_applies_only_approved_m1_to_selected_floor(tmp_path: Path) -> None:
    source_path = tmp_path / "plan.dxf"
    source_path.write_text("test", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "repeat.metrajai", "Repeat")
    source = workspace.add_source(
        source_path,
        discipline=Discipline.STRUCTURAL,
        role="kalip",
    )
    second = workspace.put_floor(
        FloorDefinition(
            project_id=workspace.manifest.project_id,
            name="2. KAT",
            kind=FloorKind.TYPICAL,
            order=2,
            elevation_m=3,
            height_m=3,
        )
    )
    assignment = workspace.put_repeat_assignment(
        RepeatAssignment(
            project_id=workspace.manifest.project_id,
            source_id=source.id,
            scope=RepeatScope.TEMPLATE,
            template_label="M1",
            target_floor_ids=[second.id],
            approved=True,
            reviewer="Engineer",
            reason="Kat listesi kontrol edildi",
        )
    )

    expanded, warnings = expand_approved_repeat_assignments(
        [_element(source.id, "M1"), _element(source.id, "M2")],
        source,
        [assignment],
        [second],
    )

    clones = [item for item in expanded if item.properties.get("repeat_assignment_id")]
    assert [(item.properties["element_label"], item.floor) for item in clones] == [
        ("M1", "2. KAT")
    ]
    assert "blocking:stair_floor_repeat_required" not in clones[0].issues
    assert warnings[0].code == "APPROVED_ELEMENT_REPETITION_APPLIED"


def test_manual_measurement_requires_reason_and_is_audited(tmp_path: Path) -> None:
    source_path = tmp_path / "plan.dxf"
    source_path.write_text("test", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "manual.metrajai", "Manual")
    source = workspace.add_source(
        source_path,
        discipline=Discipline.STRUCTURAL,
        role="kalip",
    )
    element = _element(source.id)
    element.id = "elm_manual"
    element.issues = []
    del element.measurements["total_rise_m"]
    workspace.replace_source_elements(source.id, [element])

    with pytest.raises(ValueError, match="gerekçe"):
        workspace.review_element(
            ReviewDecision(
                element_id=element.id,
                status=ReviewStatus.ACCEPTED,
                measurement_overrides={"total_rise_m": 3.2},
            )
        )

    workspace.review_element(
        ReviewDecision(
            element_id=element.id,
            status=ReviewStatus.ACCEPTED,
            reviewer="Engineer",
            reason="Kesit K-01 kontrol edildi",
            measurement_overrides={"total_rise_m": 3.2},
        )
    )
    override = workspace.list_manual_overrides(element.id)[0]
    assert override.new_values == {"total_rise_m": 3.2}
    assert override.reason == "Kesit K-01 kontrol edildi"


def test_price_catalog_import_and_full_offer_rounding(tmp_path: Path) -> None:
    path = tmp_path / "catalog.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Poz", "Açıklama", "Birim", "Birim Fiyat"])
    sheet.append(["15.001", "Kolon betonu", "m³", 2500.125])
    workbook.save(path)
    catalog, items = import_price_catalog_file(
        path,
        project_id="prj_test",
        name="2026",
        year=2026,
        version="1",
    )
    assert catalog.sha256
    assert items[0].unit_price == Decimal("2500.125")

    quantity = QuantityLine(
        id="qty_1",
        element_id="elm_1",
        source_id="src_1",
        discipline=Discipline.STRUCTURAL,
        floor="ZEMİN",
        category="Beton",
        description="Kolon betonu",
        unit="m³",
        quantity=1.234,
        formula="w*d*h",
        formula_key="column:0",
        variables={},
        review_status=ReviewStatus.ACCEPTED,
    )
    mapping = PriceMapping(
        project_id="prj_test",
        quantity_line_id=quantity.id,
        price_item_id=items[0].id,
        status=MappingStatus.APPROVED,
        reviewer="Engineer",
        reason="Poz kontrol edildi",
    )
    scenario = OfferScenario(
        project_id="prj_test",
        name="Ana teklif",
        approved=True,
        reviewer="Engineer",
        adjustments=[
            OfferAdjustment(
                label="Genel gider",
                kind=AdjustmentKind.PERCENT,
                base=AdjustmentBase.DIRECT_COST,
                value=Decimal("10"),
                order=10,
                applicable=True,
            ),
            OfferAdjustment(
                label="KDV",
                kind=AdjustmentKind.PERCENT,
                base=AdjustmentBase.RUNNING_TOTAL,
                value=Decimal("20"),
                order=20,
                applicable=True,
            ),
        ],
    )
    lines, totals = calculate_offer(scenario, [quantity], [mapping], items)
    assert lines[0].amount == Decimal("3085.15")
    assert totals["direct_cost"] == Decimal("3085.15")
    assert totals["grand_total"] == Decimal("4072.40")


def test_mechanical_quantities_stay_locked_until_reliability_gate(tmp_path: Path) -> None:
    element = DetectedElement(
        source_id="src_mech",
        discipline=Discipline.MECHANICAL,
        element_type="pipe",
        geometry=Geometry(kind="line"),
        measurements={"length_m": 10},
        required_inputs=["length_m"],
        confidence=1,
        review_status=ReviewStatus.ACCEPTED,
    )
    quantities, warnings = calculate_quantities(
        [element], blocked_disciplines={Discipline.MECHANICAL}
    )
    assert quantities == []
    assert warnings[0].code == "DISCIPLINE_RELIABILITY_GATE_LOCKED"
    workspace = ProjectWorkspace.create(tmp_path / "gates.metrajai", "Gates")
    with pytest.raises(ValueError, match="küçük ve karmaşık"):
        workspace.put_validation_gate(
            ValidationGate(
                project_id=workspace.manifest.project_id,
                discipline=Discipline.MECHANICAL,
                state="reliable",
            )
        )


def test_room_spreadsheet_can_produce_area_without_inventing_perimeter(tmp_path: Path) -> None:
    path = tmp_path / "mahaller.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Mahal Adı", "Net Alan"])
    sheet.append(["Toplantı Salonu", 42.5])
    workbook.save(path)
    source = SourceFile(
        project_id="prj_test",
        original_name=path.name,
        stored_path=path.name,
        sha256="a" * 64,
        size_bytes=path.stat().st_size,
        source_format=SourceFormat.XLSX,
        discipline=Discipline.ARCHITECTURAL,
        role="mahal_listesi",
    )

    elements, warnings, _ = analyze_spreadsheet_source(source, path)

    assert not warnings
    assert len(elements) == 1
    room = elements[0]
    assert room.measurements == {"area_m2": 42.5}
    assert room.required_inputs == ["area_m2"]
    room.review_status = ReviewStatus.ACCEPTED
    quantities, quantity_warnings = calculate_quantities([room])
    assert not quantity_warnings
    assert [line.description for line in quantities] == [
        "Net döşeme alanı",
        "Tavan alanı",
    ]


def test_scanned_pdf_uses_local_ocr_as_reviewable_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with path.open("wb") as output:
        writer.write(output)
    source = SourceFile(
        project_id="prj_test",
        original_name=path.name,
        stored_path=path.name,
        sha256="a" * 64,
        size_bytes=path.stat().st_size,
        source_format=SourceFormat.PDF,
        discipline=Discipline.ARCHITECTURAL,
        role="kesit",
        calibration_status=CalibrationStatus.CONFIRMED,
        calibration_scale=0.01,
    )
    monkeypatch.setattr(
        "metrajai.source_analyzers._run_local_pdf_ocr",
        lambda _path: {1: {"page": 1, "text": "+0.00 +3.20 ZEMİN KAT", "confidence": 0.91}},
    )

    elements, warnings, _ = analyze_pdf_source(source, path)

    assert len(elements) == 1
    assert elements[0].geometry.kind == "pdf_ocr_page"
    assert elements[0].properties["ocr_engine"] == "Apple Vision (on-device)"
    assert elements[0].confidence == pytest.approx(0.91)
    assert "review:ocr_text_requires_engineer_classification" in elements[0].issues
    assert warnings[0].code == "SCANNED_PDF_OCR_EXTRACTED"
