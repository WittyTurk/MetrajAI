from __future__ import annotations

from pathlib import Path

import ezdxf
import pytest

from metrajai.analyzers import DxfAnalyzer
from metrajai.analyzers.architectural_plan import (
    apply_architectural_assignments,
    reconcile_architectural_elements,
)
from metrajai.calculations import (
    calculate_quantities,
    derive_element_measurements,
    synchronize_opening_dependencies,
)
from metrajai.contracts import (
    ArchitecturalAssignment,
    ArchitecturalAssignmentKind,
    DetectedElement,
    Discipline,
    DrawingUnit,
    Geometry,
    ReviewDecision,
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
    plan.add_blockref("KAPI_AK1", (2050, 100), dxfattribs={"layer": "OLCU"})
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
    door_element = next(
        item
        for item in elements
        if item.element_type == "door" and not item.properties.get("evidence_only")
    )
    assert room.properties["room_code"] == "ZK01"
    assert room.measurements["area_m2"] == pytest.approx(20)
    assert room.measurements["perimeter_m"] == pytest.approx(18)
    assert door_element.measurements["width_m"] == pytest.approx(0.9)
    assert door_element.measurements["height_m"] == pytest.approx(2.2)
    assert door_element.measurements["opening_area_m2"] == pytest.approx(1.98)
    assert door_element.properties["host_wall_id"]
    assert door_element.properties["adjacent_room_ids"] == [room.id]
    annotation_doors = [
        item
        for item in elements
        if item.element_type == "door" and item.properties.get("evidence_only")
    ]
    assert len(annotation_doors) == 1
    assert "blocking:annotation_opening_not_physical" in annotation_doors[0].issues
    assert len([item for item in elements if item.element_type == "room"]) == 1


def test_unmatched_plan_room_is_evidence_not_approvable_quantity() -> None:
    source_file = SourceFile(
        project_id="p",
        original_name="plan.dxf",
        stored_path="plan.dxf",
        sha256="c" * 64,
        size_bytes=1,
        discipline=Discipline.ARCHITECTURAL,
        role="plan",
        drawing_unit=DrawingUnit.M,
        unit_confirmed=True,
    )
    boundary = DetectedElement(
        id="unmatched-boundary",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="room_boundary", bbox=(0, 0, 4, 3)),
        measurements={"area_m2": 12, "perimeter_m": 14},
        properties={"room_code": ""},
        required_inputs=["area_m2", "perimeter_m"],
        confidence=0.9,
    )
    reconciled, _ = reconcile_architectural_elements(source_file, [boundary])
    candidate = reconciled[0]
    assert candidate.properties["evidence_only"] is True
    assert "blocking:unmatched_room_boundary_evidence_only" in candidate.issues
    assert candidate.review_status == ReviewStatus.NEEDS_REVIEW
    candidate.review_status = ReviewStatus.ACCEPTED
    quantities, warnings = calculate_quantities([candidate])
    assert quantities == []
    assert any(item.code == "ACCEPTED_ELEMENT_HAS_UNRESOLVED_EVIDENCE" for item in warnings)


def test_reconciling_matched_schedule_room_twice_preserves_quantity_candidate() -> None:
    source_file = SourceFile(
        project_id="p",
        original_name="plan.dxf",
        stored_path="plan.dxf",
        sha256="c" * 64,
        size_bytes=1,
        discipline=Discipline.ARCHITECTURAL,
        role="plan",
        drawing_unit=DrawingUnit.M,
        unit_confirmed=True,
    )
    room = DetectedElement(
        id="schedule-ZK01",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="architectural_schedule_row"),
        measurements={"area_m2": 9.33},
        properties={"room_code": "ZK01", "schedule_evidence": {"table": "A"}},
        required_inputs=["area_m2", "perimeter_m"],
        confidence=0.9,
    )
    boundary = DetectedElement(
        id="boundary-ZK01",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="room_boundary", bbox=(0, 0, 3.11, 3)),
        measurements={"area_m2": 9.33, "perimeter_m": 12.22},
        properties={"room_code": "ZK01", "boundary_method": "lwpolyline"},
        required_inputs=["area_m2", "perimeter_m"],
        confidence=0.9,
    )

    once, _ = reconcile_architectural_elements(source_file, [room, boundary])
    twice, _ = reconcile_architectural_elements(source_file, once)

    for result in (once, twice):
        candidates = [
            item
            for item in result
            if item.element_type == "room" and not item.properties.get("evidence_only")
        ]
        assert len(candidates) == 1
        assert candidates[0].id == room.id
        assert candidates[0].geometry.kind == "room_boundary"
        assert candidates[0].properties["boundary_element_id"] == boundary.id
        assert candidates[0].measurements["area_m2"] == pytest.approx(9.33)
        assert "blocking:room_boundary_assignment_required" not in candidates[0].issues


def test_unmatched_plan_room_cannot_be_accepted_via_review_api(tmp_path: Path) -> None:
    drawing = tmp_path / "drawing.dxf"
    drawing.write_text("test", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "project", "Architecture")
    source_file = workspace.add_source(
        drawing, discipline=Discipline.ARCHITECTURAL, role="Mimari plan"
    )
    candidate = DetectedElement(
        id="unmatched-boundary",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="room_boundary", bbox=(0, 0, 4, 3)),
        measurements={"area_m2": 12, "perimeter_m": 14},
        properties={"evidence_only": True},
        required_inputs=["area_m2", "perimeter_m"],
        confidence=0.9,
        issues=["blocking:unmatched_room_boundary_evidence_only"],
    )
    workspace.replace_source_elements(source_file.id, [candidate])
    with pytest.raises(ValueError, match="unmatched_room_boundary_evidence_only"):
        workspace.review_element(
            ReviewDecision(element_id=candidate.id, status=ReviewStatus.ACCEPTED)
        )


def test_collinear_wall_footprints_are_joined_across_reviewable_opening(
    tmp_path: Path,
) -> None:
    path = tmp_path / "wall-with-opening.dxf"
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = 4
    modelspace = document.modelspace()
    modelspace.add_text("ZEMİN KAT PLANI")
    wall = document.blocks.new("WALL_WITH_OPENING")
    wall.add_lwpolyline(
        [(0, 0), (2000, 0), (2000, 200), (0, 200)],
        close=True,
        dxfattribs={"layer": "A-WALL"},
    )
    wall.add_lwpolyline(
        [(2900, 0), (5000, 0), (5000, 200), (2900, 200)],
        close=True,
        dxfattribs={"layer": "A-WALL"},
    )
    modelspace.add_blockref("WALL_WITH_OPENING", (0, 0), dxfattribs={"layer": "A-WALL"})
    document.saveas(path)

    elements, _, _ = DxfAnalyzer().analyze(source(path), path)

    walls = [item for item in elements if item.element_type == "wall"]
    assert len(walls) == 1
    assert walls[0].measurements["length_m"] == pytest.approx(5.0)
    assert walls[0].measurements["thickness_m"] == pytest.approx(0.2)
    assert walls[0].measurements["opening_gap_width_m"] == pytest.approx(0.9)
    assert "blocking:opening_dimensions_required" in walls[0].issues


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
    assert all(
        "blocking:opening_vertical_position_required" in item.issues for item in wall_finishes
    )
    opening.review_status = ReviewStatus.ACCEPTED
    synchronize_opening_dependencies([*wall_finishes, opening])
    assert all("blocking:opening_decision_required" in item.issues for item in wall_finishes)
    opening.measurements["sill_height_m"] = 0.4
    synchronize_opening_dependencies([*wall_finishes, opening])
    lower, upper = sorted(wall_finishes, key=lambda item: item.properties["band_bottom_m"])
    assert lower.measurements["opening_area_m2"] == pytest.approx(0.8)
    assert upper.measurements["opening_area_m2"] == pytest.approx(1.2)
    assert all(
        "blocking:opening_vertical_position_required" not in item.issues for item in wall_finishes
    )


def test_finish_waits_for_opening_decision_and_recalculates_after_change() -> None:
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
    room = DetectedElement(
        id="room",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="room_boundary", bbox=(0, 0, 4, 3)),
        measurements={"area_m2": 12, "perimeter_m": 14, "height_m": 3},
        properties={"room_code": "ZK01", "wall_finish": "BOYA"},
        required_inputs=["area_m2"],
        confidence=1,
    )
    schedule = room.model_copy(deep=True)
    schedule.id = "schedule"
    schedule.geometry = Geometry(kind="architectural_schedule_row")
    opening = DetectedElement(
        id="door",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="door",
        geometry=Geometry(kind="door_opening", bbox=(1, 0, 2, 0.2)),
        measurements={"count": 1, "width_m": 1, "height_m": 2, "opening_area_m2": 2},
        properties={"adjacent_room_ids": [room.id]},
        required_inputs=["count", "width_m", "height_m"],
        confidence=1,
    )
    reconciled, _ = reconcile_architectural_elements(source_file, [schedule, room, opening])
    finish = next(item for item in reconciled if item.element_type == "finish_area")
    assert finish.properties["opening_element_ids"] == [opening.id]

    finish.review_status = ReviewStatus.ACCEPTED
    assert calculate_quantities([finish, opening])[0] == []
    synchronize_opening_dependencies([finish, opening])
    assert finish.review_status == ReviewStatus.NEEDS_REVIEW
    assert "blocking:opening_decision_required" in finish.issues

    opening.review_status = ReviewStatus.ACCEPTED
    synchronize_opening_dependencies([finish, opening])
    assert "blocking:opening_decision_required" not in finish.issues
    finish.review_status = ReviewStatus.ACCEPTED
    assert calculate_quantities([finish, opening])[0]

    opening.measurements["width_m"] = 1.5
    derive_element_measurements(opening)
    stale_lines, _ = calculate_quantities([finish, opening])
    assert all(line.element_id != finish.id for line in stale_lines)
    synchronize_opening_dependencies([finish, opening])
    assert finish.review_status == ReviewStatus.NEEDS_REVIEW
    assert finish.measurements["opening_area_m2"] == pytest.approx(3)
    assert finish.measurements["net_area_m2"] == pytest.approx(39)

    opening.review_status = ReviewStatus.REJECTED
    synchronize_opening_dependencies([finish, opening])
    assert finish.measurements["opening_area_m2"] == 0
    assert finish.measurements["net_area_m2"] == pytest.approx(42)


def test_opening_change_revokes_persisted_finish_approval(tmp_path: Path) -> None:
    drawing = tmp_path / "plan.dxf"
    drawing.write_text("test", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "project", "Açıklık bağımlılığı")
    source_file = workspace.add_source(drawing, discipline=Discipline.ARCHITECTURAL, role="mimari")
    opening = DetectedElement(
        id="door",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="door",
        geometry=Geometry(kind="door_opening"),
        measurements={"count": 1, "width_m": 1, "height_m": 2, "opening_area_m2": 2},
        required_inputs=["count", "width_m", "height_m"],
    )
    finish = DetectedElement(
        id="finish",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="finish_area",
        geometry=Geometry(kind="finish_area"),
        measurements={"gross_area_m2": 20, "opening_area_m2": 2, "net_area_m2": 18, "area_m2": 18},
        properties={"opening_element_ids": [opening.id], "opening_area_basis_m2": 2},
        required_inputs=["area_m2"],
    )
    workspace.replace_source_elements(source_file.id, [opening, finish])
    workspace.synchronize_opening_dependencies()
    with pytest.raises(ValueError, match="kapı/pencere kararları"):
        workspace.review_element(ReviewDecision(element_id=finish.id, status=ReviewStatus.ACCEPTED))
    workspace.review_element(ReviewDecision(element_id=opening.id, status=ReviewStatus.ACCEPTED))
    workspace.synchronize_opening_dependencies()
    workspace.review_element(ReviewDecision(element_id=finish.id, status=ReviewStatus.ACCEPTED))
    assert any(
        line.element_id == finish.id for line in calculate_quantities(workspace.list_elements())[0]
    )
    workspace.review_element(
        ReviewDecision(
            element_id=opening.id,
            status=ReviewStatus.ACCEPTED,
            measurement_overrides={"width_m": 1.5},
            reason="Kapı çizelgesindeki yeni ölçü",
        )
    )
    assert all(
        line.element_id != finish.id for line in calculate_quantities(workspace.list_elements())[0]
    )
    workspace.synchronize_opening_dependencies()
    reloaded = workspace.get_element(finish.id)
    assert reloaded.review_status == ReviewStatus.NEEDS_REVIEW
    assert reloaded.measurements["net_area_m2"] == pytest.approx(17)
    assert reloaded.properties["opening_area_basis_m2"] == pytest.approx(3)


def test_wall_volume_uses_opening_deducted_area() -> None:
    wall = DetectedElement(
        id="wall",
        source_id="source",
        discipline=Discipline.ARCHITECTURAL,
        element_type="wall",
        geometry=Geometry(kind="wall_centerline"),
        measurements={"length_m": 10, "height_m": 3, "thickness_m": 0.2, "opening_area_m2": 2},
        required_inputs=["length_m", "height_m"],
        review_status=ReviewStatus.ACCEPTED,
    )
    derive_element_measurements(wall)
    lines, _ = calculate_quantities([wall])
    volume = next(line for line in lines if line.unit == "m³")
    assert wall.measurements["net_area_m2"] == pytest.approx(28)
    assert volume.quantity == pytest.approx(5.6)


def test_written_room_area_blocks_wrong_dxf_unit_instead_of_silent_scaling(
    tmp_path: Path,
) -> None:
    path = tmp_path / "wrong-unit.dxf"
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = 4
    modelspace = document.modelspace()
    modelspace.add_text("ZEMIN KAT PLANI", dxfattribs={"insert": (0, 500)})
    modelspace.add_text("MAHAL TABLOSU", dxfattribs={"insert": (0, 600)})
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

    from metrajai.analyzers.source_inspection import inspect_source_file

    inspection = inspect_source_file(path)
    assert inspection["header_unit"] == "mm"
    assert inspection["suggested_unit"] == "cm"
    assert inspection["unit_evidence_basis"] == "architectural_area"

    elements, warnings, _ = DxfAnalyzer().analyze(source(path), path)

    mismatch = next(
        item for item in warnings if item.code == "ARCHITECTURAL_UNIT_EVIDENCE_MISMATCH"
    )
    assert "cm olarak doğrulanması" in mismatch.message
    assert all("blocking:drawing_unit_evidence_mismatch" in item.issues for item in elements)


def test_approved_room_boundary_selects_one_candidate_without_changing_area() -> None:
    source_file = SourceFile(
        project_id="p",
        original_name="plan.dxf",
        stored_path="plan.dxf",
        sha256="d" * 64,
        size_bytes=1,
        discipline=Discipline.ARCHITECTURAL,
        role="mimari",
        drawing_unit=DrawingUnit.M,
        unit_confirmed=True,
    )
    room = DetectedElement(
        id="elm_room",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="architectural_schedule_row"),
        measurements={"area_m2": 20},
        properties={"room_code": "ZK01"},
        required_inputs=["area_m2"],
    )
    first = DetectedElement(
        id="elm_first",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="room_boundary", bbox=(0, 0, 3, 6)),
        measurements={"area_m2": 18, "perimeter_m": 18},
        properties={"room_code": "ZK01", "plan_region_id": "A1", "boundary_method": "lwpolyline"},
    )
    second = DetectedElement(
        id="elm_second",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="room_boundary", bbox=(10, 0, 15, 4)),
        measurements={"area_m2": 20, "perimeter_m": 18},
        properties={"room_code": "ZK01", "plan_region_id": "A2", "boundary_method": "lwpolyline"},
    )
    ambiguous, _ = reconcile_architectural_elements(
        source_file,
        [room.model_copy(deep=True), first.model_copy(deep=True), second.model_copy(deep=True)],
    )
    ambiguous_room = next(item for item in ambiguous if item.id == room.id)
    assert "blocking:room_boundary_assignment_required" in ambiguous_room.issues
    assert {item["id"] for item in ambiguous_room.properties["boundary_candidates"]} == {
        first.id,
        second.id,
    }
    assignment = ArchitecturalAssignment(
        project_id="p",
        source_id=source_file.id,
        subject_element_id=room.id,
        kind=ArchitecturalAssignmentKind.ROOM_BOUNDARY,
        target_element_ids=[second.id],
        approved=True,
        reviewer="Mühendis",
        reason="Plan sınırı ve çizelge ölçüsü karşılaştırıldı",
    )
    assigned = apply_architectural_assignments([room, first, second], [assignment])
    reconciled, _ = reconcile_architectural_elements(source_file, assigned)
    matched = next(item for item in reconciled if item.id == room.id)
    assert matched.properties["boundary_element_id"] == second.id
    assert matched.properties["plan_region_id"] == "A2"
    assert matched.measurements["area_m2"] == 20
    assert matched.measurements["geometric_area_m2"] == 20
    assert "blocking:room_schedule_geometry_mismatch" not in matched.issues


def test_approved_schedule_net_keeps_gross_geometry_and_blocks_wall_finish() -> None:
    source_file = SourceFile(
        project_id="p",
        original_name="plan.dxf",
        stored_path="plan.dxf",
        sha256="d" * 64,
        size_bytes=1,
        discipline=Discipline.ARCHITECTURAL,
        role="mimari",
        drawing_unit=DrawingUnit.M,
        unit_confirmed=True,
    )
    rooms = [
        DetectedElement(
            id=f"room-{code}",
            source_id=source_file.id,
            discipline=Discipline.ARCHITECTURAL,
            element_type="room",
            geometry=Geometry(kind="architectural_schedule_row"),
            measurements={"area_m2": area, "height_m": 3},
            properties={
                "room_code": code,
                "schedule_evidence": {"table_handle": "TABLE"},
                "room_schedule_total_area_m2": 27,
                "reference_net_area_m2": 27.1,
                "reference_gross_area_m2": 30,
                "floor_finish": "Seramik",
                "wall_finish": "Boya",
            },
            required_inputs=["area_m2"],
        )
        for code, area in (("ZK01", 9), ("ZK02", 18))
    ]
    boundaries = [
        DetectedElement(
            id=f"boundary-{code}",
            source_id=source_file.id,
            discipline=Discipline.ARCHITECTURAL,
            element_type="room",
            geometry=Geometry(kind="room_boundary", bbox=(index * 5, 0, index * 5 + 4, 4)),
            measurements={"area_m2": area, "perimeter_m": 16},
            properties={
                "room_code": code,
                "plan_region_id": "PLAN",
                "boundary_method": "lwpolyline",
            },
        )
        for index, (code, area) in enumerate((("ZK01", 10), ("ZK02", 20)))
    ]
    unapproved, _ = reconcile_architectural_elements(
        source_file, [item.model_copy(deep=True) for item in rooms + boundaries]
    )
    assert all(
        "blocking:room_schedule_geometry_mismatch" in item.issues
        for item in unapproved
        if item.id in {room.id for room in rooms}
    )
    assignments = [
        ArchitecturalAssignment(
            project_id="p",
            source_id=source_file.id,
            subject_element_id=room.id,
            kind=ArchitecturalAssignmentKind.ROOM_AREA_BASIS,
            values={"net_area_source": "schedule", "plan_area_role": "gross"},
            approved=True,
            reviewer="Mühendis",
            reason="Çizelge net, plan brüt alan",
        )
        for room in rooms
    ]
    approved = apply_architectural_assignments(
        [item.model_copy(deep=True) for item in rooms + boundaries], assignments
    )
    resolved, warnings = reconcile_architectural_elements(source_file, approved)
    resolved_rooms = [item for item in resolved if item.id in {room.id for room in rooms}]
    assert sum(item.measurements["area_m2"] for item in resolved_rooms) == 27
    assert sum(item.measurements["gross_region_area_m2"] for item in resolved_rooms) == 30
    assert all(
        "blocking:room_schedule_geometry_mismatch" not in item.issues for item in resolved_rooms
    )
    assert all(item.review_status == ReviewStatus.PENDING for item in resolved_rooms)
    floor_finishes = [
        item
        for item in resolved
        if item.element_type == "finish_area" and item.properties["surface_type"] == "floor"
    ]
    wall_finishes = [
        item
        for item in resolved
        if item.element_type == "finish_area" and item.properties["surface_type"] == "wall"
    ]
    assert sum(item.measurements["area_m2"] for item in floor_finishes) == 27
    assert all("blocking:net_room_perimeter_required" in item.issues for item in wall_finishes)
    assert any(item.code == "ARCHITECTURAL_GROSS_NET_AREA_BASIS" for item in warnings)


def test_schedule_net_assignment_requires_independent_gross_evidence(tmp_path: Path) -> None:
    drawing = tmp_path / "plan.dxf"
    drawing.write_text("test", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "project", "Alan dayanağı")
    source_file = workspace.add_source(drawing, discipline=Discipline.ARCHITECTURAL, role="mimari")
    rooms = [
        DetectedElement(
            id=f"room-{index}",
            source_id=source_file.id,
            discipline=Discipline.ARCHITECTURAL,
            element_type="room",
            geometry=Geometry(kind="room_boundary"),
            measurements={"area_m2": net, "geometric_area_m2": gross},
            properties={
                "room_code": f"ZK0{index}",
                "schedule_evidence": {"table_handle": "A"},
                "boundary_element_id": f"boundary-{index}",
                "room_schedule_total_area_m2": 27,
                "reference_gross_area_m2": 30,
            },
        )
        for index, (net, gross) in enumerate(((9, 10), (18, 20)), start=1)
    ]
    workspace.replace_source_elements(source_file.id, rooms)
    assignment = ArchitecturalAssignment(
        project_id=workspace.manifest.project_id,
        source_id=source_file.id,
        subject_element_id=rooms[0].id,
        kind=ArchitecturalAssignmentKind.ROOM_AREA_BASIS,
        values={"net_area_source": "schedule", "plan_area_role": "gross"},
        approved=True,
        reviewer="Mühendis",
        reason="Çizelge ve brüt plan toplamları uzlaşıyor",
    )
    workspace.put_architectural_assignment(assignment)
    rooms[1].properties["reference_gross_area_m2"] = 0
    rooms[0].properties["reference_gross_area_m2"] = 0
    workspace.replace_source_elements(source_file.id, rooms)
    with pytest.raises(ValueError, match="brüt alan kanıtıyla"):
        workspace.put_architectural_assignment(
            assignment.model_copy(update={"id": "new-assignment"})
        )


def test_room_boundary_candidates_prioritize_distinct_code_plan_region() -> None:
    source_file = SourceFile(
        project_id="p",
        original_name="plan.dxf",
        stored_path="plan.dxf",
        sha256="d" * 64,
        size_bytes=1,
        discipline=Discipline.ARCHITECTURAL,
        role="mimari",
        drawing_unit=DrawingUnit.M,
        unit_confirmed=True,
    )
    schedule = [
        DetectedElement(
            id=f"schedule-{code}",
            source_id=source_file.id,
            discipline=Discipline.ARCHITECTURAL,
            element_type="room",
            geometry=Geometry(kind="architectural_schedule_row"),
            measurements={"area_m2": 9 if code == "ZK02" else 10},
            properties={"room_code": code},
            required_inputs=["area_m2"],
        )
        for code in ("ZK01", "ZK02")
    ]
    boundaries = [
        DetectedElement(
            id=f"{region}-{code}",
            source_id=source_file.id,
            discipline=Discipline.ARCHITECTURAL,
            element_type="room",
            geometry=Geometry(kind="room_boundary", bbox=(0, 0, 2, 5)),
            measurements={"area_m2": 10, "perimeter_m": 14},
            properties={
                "room_code": code,
                "plan_region_id": region,
                "boundary_method": "lwpolyline",
            },
        )
        for region, code in (("main", "ZK01"), ("main", "ZK02"), ("detail", "ZK01"))
    ]
    result, _ = reconcile_architectural_elements(source_file, [*schedule, *boundaries])
    for room in (item for item in result if item.id.startswith("schedule-")):
        assert room.properties["preferred_plan_region_id"] == "main"
        assert (
            sum(
                bool(candidate["preferred_plan_region"])
                for candidate in room.properties["boundary_candidates"]
            )
            == 2
        )
        assert room.properties["boundary_element_id"] == f"main-{room.properties['room_code']}"
        assert room.properties["boundary_match_method"] == "unique_room_code_in_primary_plan"
    second = next(item for item in result if item.id == "schedule-ZK02")
    assert second.measurements["area_m2"] == 9
    assert second.measurements["geometric_area_m2"] == 10
    assert "blocking:room_schedule_geometry_mismatch" in second.issues
    repeated, _ = reconcile_architectural_elements(source_file, result)
    assert all(
        "blocking:room_boundary_assignment_required" not in item.issues
        for item in repeated
        if item.id.startswith("schedule-")
    )
    assert (
        next(item for item in repeated if item.id == "schedule-ZK02").properties[
            "boundary_element_id"
        ]
        == "main-ZK02"
    )


def test_consumed_room_boundary_can_be_assigned_from_recorded_candidates(tmp_path: Path) -> None:
    drawing = tmp_path / "plan.dxf"
    drawing.write_text("test", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "project", "Architecture")
    source_file = workspace.add_source(drawing, discipline=Discipline.ARCHITECTURAL, role="mimari")
    room = DetectedElement(
        id="elm_schedule",
        source_id=source_file.id,
        discipline=Discipline.ARCHITECTURAL,
        element_type="room",
        geometry=Geometry(kind="room_boundary", bbox=(0, 0, 3, 6)),
        measurements={"area_m2": 20, "geometric_area_m2": 18},
        properties={
            "room_code": "ZK01",
            "boundary_candidates": [
                {
                    "id": "elm_consumed",
                    "room_code": "ZK01",
                    "area_m2": 18,
                    "source_handle": "2DB1/v1",
                    "plan_region_id": "2DB1",
                },
                {
                    "id": "elm_alternative",
                    "room_code": "ZK01",
                    "area_m2": 20,
                    "source_handle": "2DB1/v2",
                    "plan_region_id": "2DB1",
                },
            ],
        },
    )
    workspace.replace_source_elements(source_file.id, [room])
    assignment = workspace.put_architectural_assignment(
        ArchitecturalAssignment(
            project_id=workspace.manifest.project_id,
            source_id=source_file.id,
            subject_element_id=room.id,
            kind=ArchitecturalAssignmentKind.ROOM_BOUNDARY,
            target_element_ids=["elm_alternative"],
            approved=True,
            reviewer="Mühendis",
            reason="Plan sınırı doğrulandı",
        )
    )
    assert assignment.target_element_ids == ["elm_alternative"]
    with pytest.raises(ValueError, match="plan sınırı adayı"):
        workspace.put_architectural_assignment(
            ArchitecturalAssignment(
                project_id=workspace.manifest.project_id,
                source_id=source_file.id,
                subject_element_id=room.id,
                kind=ArchitecturalAssignmentKind.ROOM_BOUNDARY,
                target_element_ids=["elm_untrusted"],
                approved=True,
                reviewer="Mühendis",
                reason="Plan sınırı doğrulandı",
            )
        )


def test_openable_window_description_is_not_mistaken_for_detail_title(
    tmp_path: Path,
) -> None:
    path = tmp_path / "openable-window-plan.dxf"
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = 4
    modelspace = document.modelspace()
    modelspace.add_text(
        "ZEMİN KAT PLANI",
        dxfattribs={"insert": (0, -1000), "layer": "BASLIK"},
    )
    modelspace.add_text(
        "ahşap görünümlü çift açılımlı pencere",
        dxfattribs={"insert": (2000, 1500), "layer": "MALZEME"},
    )
    modelspace.add_text("ZK01", dxfattribs={"insert": (2000, 1500), "layer": "MAHAL NO"})
    modelspace.add_lwpolyline(
        [(0, 0), (4000, 0), (4000, 3000), (0, 3000)],
        close=True,
        dxfattribs={"layer": "ALAN"},
    )
    document.saveas(path)

    elements, _, _ = DxfAnalyzer().analyze(source(path), path)

    rooms = [item for item in elements if item.element_type == "room"]
    assert len(rooms) == 1
    assert rooms[0].properties["room_code"] == "ZK01"
    assert rooms[0].measurements["area_m2"] == pytest.approx(12.0)


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
