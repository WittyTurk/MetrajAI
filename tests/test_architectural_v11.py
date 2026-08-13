from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest

from metrajai.analyzers import DxfAnalyzer
from metrajai.analyzers.architectural_plan import reconcile_architectural_elements
from metrajai.contracts import (
    ArchitecturalAssignment,
    ArchitecturalAssignmentKind,
    DetectedElement,
    Discipline,
    DrawingUnit,
    Geometry,
    ReviewStatus,
    SourceFile,
)
from metrajai.workspace import CURRENT_SCHEMA_VERSION, ProjectWorkspace


def source(path: Path) -> SourceFile:
    return SourceFile(
        project_id="prj_architecture",
        original_name=path.name,
        stored_path=path.name,
        sha256="b" * 64,
        size_bytes=path.stat().st_size,
        discipline=Discipline.ARCHITECTURAL,
        role="mimari uygulama",
        drawing_unit=DrawingUnit.MM,
        unit_confirmed=True,
    )


def test_nested_rotated_plan_room_and_opening_schedule_are_traceable(tmp_path: Path) -> None:
    path = tmp_path / "architecture.dxf"
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = 4
    room_table = document.blocks.new("ROOM_TABLE")
    for value in (
        "ZEMİN KAT MAHAL TABLOSU",
        "MAHAL KODU",
        "MAHAL ADI",
        "NET ALAN",
        "ZK01",
        "SALON",
        "20.00 M2",
        "SERAMİK",
        "H:120cm SERAMİK + BOYA",
        "BOYA",
    ):
        room_table.add_text(value)
    opening_table = document.blocks.new("OPENING_TABLE")
    for value in (
        "KAPI-PEN. İSMİ",
        "KAPI-PENCERE ÖLÇÜSÜ",
        "KAPI-PENCERE AÇILIMI",
        "AK-1",
        "90 / 220",
        "LAMİNE AHŞAP KAPI",
    ):
        opening_table.add_text(value)

    plan = document.blocks.new("ZEMIN_PLAN")
    plan.add_lwpolyline(
        [(0, 0), (5000, 0), (5000, 4000), (0, 4000)],
        close=True,
        dxfattribs={"layer": "MAHAL"},
    )
    plan.add_text("ZK01", dxfattribs={"insert": (2500, 2000), "layer": "MAHAL NO"})
    plan.add_lwpolyline(
        [(0, 0), (5000, 0), (5000, 200), (0, 200)],
        close=True,
        dxfattribs={"layer": "DUVAR"},
    )
    door = document.blocks.new("KAPI_AK1")
    door.add_line((0, 0), (900, 0), dxfattribs={"layer": "KAPI"})
    plan.add_blockref("KAPI_AK1", (2050, 100), dxfattribs={"layer": "KAPI"})
    plan.add_text("AK-1", dxfattribs={"insert": (2500, 350), "layer": "KAPIPOZ"})

    modelspace = document.modelspace()
    modelspace.add_blockref("ROOM_TABLE", (30000, 0))
    modelspace.add_blockref("OPENING_TABLE", (30000, 5000))
    modelspace.add_text("ZEMİN KAT PLANI", dxfattribs={"insert": (8000, 15500)})
    modelspace.add_blockref(
        "ZEMIN_PLAN",
        (10000, 10000),
        dxfattribs={"rotation": 90, "xscale": 1, "yscale": 1},
    )
    modelspace.add_blockref(
        "ZEMIN_PLAN",
        (50000, 10000),
        dxfattribs={"rotation": 90, "xscale": 1, "yscale": 1},
    )
    document.saveas(path)

    elements, _, _ = DxfAnalyzer().analyze(source(path), path)

    room = next(item for item in elements if item.element_type == "room")
    door_element = next(item for item in elements if item.element_type == "door")
    assert room.properties["room_code"] == "ZK01"
    assert room.measurements["area_m2"] == pytest.approx(20)
    assert room.measurements["perimeter_m"] == pytest.approx(18)
    assert door_element.measurements["width_m"] == pytest.approx(0.9)
    assert door_element.measurements["height_m"] == pytest.approx(2.2)
    assert door_element.measurements["opening_area_m2"] == pytest.approx(1.98)
    assert door_element.properties["host_wall_id"]
    assert door_element.properties["adjacent_room_ids"] == [room.id]
    assert len([item for item in elements if item.element_type == "room"]) == 1


def test_finish_bands_deduct_every_verified_opening_from_room_face() -> None:
    source_file = SourceFile(
        project_id="p",
        original_name="a.dxf",
        stored_path="a.dxf",
        sha256="c" * 64,
        size_bytes=1,
        discipline=Discipline.ARCHITECTURAL,
        role="plan",
        drawing_unit=DrawingUnit.M,
        unit_confirmed=True,
    )
    boundary = DetectedElement(
        id="elm_boundary",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="room_boundary", bbox=(0, 0, 5, 4)),
        measurements={"area_m2": 20, "perimeter_m": 18},
        properties={"room_code": "ZK01"},
        required_inputs=["area_m2", "perimeter_m"],
        confidence=1,
    )
    room = DetectedElement(
        id="elm_room",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="architectural_schedule_row"),
        measurements={"area_m2": 20, "height_m": 3},
        properties={
            "room_code": "ZK01",
            "wall_finish": "h:120cm SERAMİK + BOYA",
        },
        required_inputs=["area_m2"],
        confidence=1,
    )
    opening = DetectedElement(
        id="elm_door",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="door",
        geometry=Geometry(kind="door_opening", bbox=(2, 0, 3, 0.2)),
        measurements={"count": 1, "width_m": 1, "height_m": 2, "opening_area_m2": 2},
        properties={"adjacent_room_ids": [boundary.id], "host_wall_id": "elm_wall"},
        required_inputs=["count", "width_m", "height_m"],
        confidence=1,
    )

    reconciled, _ = reconcile_architectural_elements(source_file, [room, boundary, opening])
    wall_finishes = [
        item
        for item in reconciled
        if item.element_type == "finish_area" and item.properties["surface_type"] == "wall"
    ]

    assert len(wall_finishes) == 2
    assert sum(item.measurements["gross_area_m2"] for item in wall_finishes) == pytest.approx(54)
    assert sum(item.measurements["opening_area_m2"] for item in wall_finishes) == pytest.approx(2)
    assert sum(item.measurements["net_area_m2"] for item in wall_finishes) == pytest.approx(52)


def test_written_room_area_blocks_wrong_dxf_unit_instead_of_silent_scaling(
    tmp_path: Path,
) -> None:
    path = tmp_path / "wrong-unit.dxf"
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = 4
    modelspace = document.modelspace()
    modelspace.add_lwpolyline(
        [(0, 0), (500, 0), (500, 400), (0, 400)],
        close=True,
        dxfattribs={"layer": "METREKARE"},
    )
    modelspace.add_text("20.00 m²", dxfattribs={"insert": (250, 200), "layer": "MAHAL NO"})
    modelspace.add_lwpolyline(
        [(0, 0), (500, 0), (500, 20), (0, 20)],
        close=True,
        dxfattribs={"layer": "DUVAR"},
    )
    document.saveas(path)

    elements, warnings, _ = DxfAnalyzer().analyze(source(path), path)

    assert any(item.code == "ARCHITECTURAL_UNIT_EVIDENCE_MISMATCH" for item in warnings)
    assert all(
        "blocking:drawing_unit_evidence_mismatch" in item.issues for item in elements
    )


def test_schema_v3_persists_traceable_architectural_assignment(tmp_path: Path) -> None:
    drawing = tmp_path / "plan.dxf"
    drawing.write_text("test", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "project", "Architecture")
    imported = workspace.add_source(
        drawing, discipline=Discipline.ARCHITECTURAL, role="mimari plan"
    )
    room = DetectedElement(
        id="elm_room",
        source_id=imported.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="architectural_schedule_row"),
        required_inputs=["area_m2"],
        review_status=ReviewStatus.NEEDS_REVIEW,
    )
    boundary = DetectedElement(
        id="elm_boundary",
        source_id=imported.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="room_boundary", bbox=(0, 0, 1, 1)),
        measurements={"area_m2": 1, "perimeter_m": 4},
    )
    workspace.replace_source_elements(imported.id, [room, boundary])

    saved = workspace.put_architectural_assignment(
        ArchitecturalAssignment(
            project_id=workspace.manifest.project_id,
            source_id=imported.id,
            subject_element_id=room.id,
            kind=ArchitecturalAssignmentKind.ROOM_BOUNDARY,
            target_element_ids=[boundary.id],
            approved=True,
            reviewer="Mühendis",
            reason="Plan sınırı kontrol edildi",
        )
    )

    assert workspace.manifest.schema_version == CURRENT_SCHEMA_VERSION == 3
    assert workspace.list_architectural_assignments()[0] == saved
