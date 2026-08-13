from __future__ import annotations

from pathlib import Path

import pytest

from metrajai.contracts import (
    AnalysisRun,
    AnalysisWarning,
    DetectedElement,
    Discipline,
    FloorKind,
    Geometry,
    ReviewDecision,
    ReviewStatus,
    SheetKind,
)
from metrajai.service import EngineService
from metrajai.workspace import ProjectWorkspace


def detected(source_id: str, *, height: float | None = None) -> DetectedElement:
    measurements = {"width_m": 0.4, "depth_m": 0.6}
    if height is not None:
        measurements["height_m"] = height
    return DetectedElement(
        id="elm_stable",
        source_id=source_id,
        discipline=Discipline.STRUCTURAL,
        element_type="column",
        geometry=Geometry(kind="lwpolyline"),
        measurements=measurements,
        required_inputs=["width_m", "depth_m", "height_m"],
        confidence=0.8,
        review_status=ReviewStatus.NEEDS_REVIEW,
    )


def rebar_revision(
    source_id: str,
    *,
    element_id: str,
    table_handle: str,
    row_label: str,
) -> DetectedElement:
    return DetectedElement(
        id=element_id,
        source_id=source_id,
        discipline=Discipline.STRUCTURAL,
        element_type="rebar",
        source_handle=f"{table_handle}:{row_label}",
        geometry=Geometry(kind="table_row"),
        measurements={"diameter_mm": 12.0, "length_m": 5.0, "count": 4.0},
        properties={
            "revision_group": "beam_schedule:KZ01-KZ16",
            "revision_candidate_label": "A" if table_handle == "TABLE_A" else "B",
            "revision_selected": False,
            "table_handle": table_handle,
            "table_declared_total_kg": 2065.26 if table_handle == "TABLE_A" else 2059.97,
            "revision_candidates": [
                {"label": "A", "table_handle": "TABLE_A", "declared_total_kg": 2065.26},
                {"label": "B", "table_handle": "TABLE_B", "declared_total_kg": 2059.97},
            ],
        },
        required_inputs=["diameter_mm", "length_m", "count"],
        confidence=0.85,
        review_status=ReviewStatus.NEEDS_REVIEW,
        issues=["blocking:rebar_revision_selection_required"],
    )


def test_workspace_copies_source_and_preserves_review_on_reanalysis(tmp_path: Path) -> None:
    source_path = tmp_path / "drawing.dxf"
    source_path.write_text("immutable test source", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "pilot.metrajai", "Pilot")
    source = workspace.add_source(source_path, discipline=Discipline.STRUCTURAL, role="kalip")
    workspace.replace_source_elements(source.id, [detected(source.id)])

    with pytest.raises(ValueError, match="height_m"):
        workspace.review_element(
            ReviewDecision(element_id="elm_stable", status=ReviewStatus.ACCEPTED)
        )

    reviewed = workspace.review_element(
        ReviewDecision(
            element_id="elm_stable",
            status=ReviewStatus.ACCEPTED,
            reviewer="Engineer",
            reason="Kesit paftası kontrol edildi",
            measurement_overrides={"height_m": 3.2},
        )
    )
    assert reviewed.review_status == ReviewStatus.ACCEPTED
    assert reviewed.measurements["height_m"] == 3.2

    workspace.replace_source_elements(source.id, [detected(source.id)])
    reloaded = workspace.get_element("elm_stable")
    assert reloaded.review_status == ReviewStatus.ACCEPTED
    assert reloaded.measurements["height_m"] == 3.2
    assert len(workspace.list_reviews()) == 1
    assert workspace.source_path(source).read_text("utf-8") == "immutable test source"
    assert workspace.verify_source_integrity(source)
    workspace.source_path(source).write_text("tampered", encoding="utf-8")
    assert not workspace.verify_source_integrity(source)


def test_delete_source_removes_derived_records_and_only_project_copy(tmp_path: Path) -> None:
    original = tmp_path / "drawing.dxf"
    original.write_text("immutable original", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "pilot.metrajai", "Pilot")
    source = workspace.add_source(original, discipline=Discipline.STRUCTURAL, role="kalip")
    project_copy = workspace.source_path(source)
    workspace.replace_source_elements(source.id, [detected(source.id, height=3.0)])
    EngineService(workspace).review(
        ReviewDecision(
            element_id="elm_stable",
            status=ReviewStatus.ACCEPTED,
            reviewer="Engineer",
        )
    )
    run = AnalysisRun(source_ids=[source.id])
    workspace.save_run(run)
    workspace.replace_warnings(
        run.id,
        [AnalysisWarning(code="TEST", message="Source warning", source_id=source.id)],
    )

    result = workspace.delete_source(source.id)

    assert result["deleted_element_count"] == 1
    assert result["deleted_warning_count"] == 1
    assert result["project_copy_removed"] is True
    assert workspace.list_sources() == []
    assert workspace.list_elements() == []
    assert workspace.list_reviews() == []
    assert workspace.list_quantities() == []
    assert workspace.list_warnings(run.id) == []
    assert not project_copy.exists()
    assert original.read_text("utf-8") == "immutable original"


def test_delete_source_keeps_copy_shared_by_another_source_record(tmp_path: Path) -> None:
    original = tmp_path / "drawing.dxf"
    original.write_text("same bytes", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "pilot.metrajai", "Pilot")
    first = workspace.add_source(original, discipline=Discipline.STRUCTURAL, role="kalip")
    second = workspace.add_source(original, discipline=Discipline.STRUCTURAL, role="detay")
    assert workspace.source_path(first) == workspace.source_path(second)

    result = workspace.delete_source(first.id)

    assert result["project_copy_removed"] is False
    assert workspace.source_path(second).is_file()
    assert [source.id for source in workspace.list_sources()] == [second.id]


def test_changing_source_discipline_invalidates_old_detections(tmp_path: Path) -> None:
    original = tmp_path / "architectural.dxf"
    original.write_text("immutable source", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "pilot.metrajai", "Pilot")
    source = workspace.add_source(
        original,
        discipline=Discipline.STRUCTURAL,
        role="kalip",
    )
    workspace.replace_source_elements(source.id, [detected(source.id, height=3.0)])
    run = AnalysisRun(source_ids=[source.id])
    workspace.save_run(run)
    workspace.replace_warnings(
        run.id,
        [AnalysisWarning(code="OLD", message="Old classification", source_id=source.id)],
    )

    updated, cleared_count = workspace.update_source_discipline(
        source.id,
        Discipline.ARCHITECTURAL,
    )

    assert updated.discipline == Discipline.ARCHITECTURAL
    assert cleared_count == 1
    assert workspace.list_elements() == []
    assert workspace.list_warnings(run.id) == []
    assert workspace.source_path(updated).is_file()


def test_rebar_revision_selection_is_exclusive_and_survives_reanalysis(
    tmp_path: Path,
) -> None:
    original = tmp_path / "rebar-schedule.dxf"
    original.write_text("immutable schedule", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "pilot.metrajai", "Pilot")
    source = workspace.add_source(original, discipline=Discipline.STRUCTURAL, role="donati")

    def candidates() -> list[DetectedElement]:
        return [
            rebar_revision(
                source.id,
                element_id="rebar_a_1",
                table_handle="TABLE_A",
                row_label="KZ01",
            ),
            rebar_revision(
                source.id,
                element_id="rebar_a_2",
                table_handle="TABLE_A",
                row_label="KZ02",
            ),
            rebar_revision(
                source.id,
                element_id="rebar_b_1",
                table_handle="TABLE_B",
                row_label="KZ01",
            ),
        ]

    workspace.replace_source_elements(source.id, candidates())
    result = workspace.select_rebar_revision(source.id, "TABLE_A")

    assert result["selected_element_count"] == 2
    assert result["rejected_element_count"] == 1
    by_id = {item.id: item for item in workspace.list_elements(source_id=source.id)}
    assert by_id["rebar_a_1"].review_status == ReviewStatus.PENDING
    assert by_id["rebar_a_1"].properties["revision_selected"] is True
    assert "blocking:rebar_revision_selection_required" not in by_id["rebar_a_1"].issues
    assert by_id["rebar_b_1"].review_status == ReviewStatus.REJECTED
    assert by_id["rebar_b_1"].properties["revision_selected"] is False

    workspace.select_rebar_revision(source.id, "TABLE_B")
    by_id = {item.id: item for item in workspace.list_elements(source_id=source.id)}
    assert by_id["rebar_a_1"].review_status == ReviewStatus.REJECTED
    assert by_id["rebar_b_1"].review_status == ReviewStatus.PENDING
    assert by_id["rebar_b_1"].properties["revision_selected"] is True
    assert (
        len(
            [
                item
                for item in workspace.list_assumptions()
                if item.key.startswith(f"rebar_revision_selection:{source.id}:")
            ]
        )
        == 1
    )

    workspace.replace_source_elements(source.id, candidates())
    workspace.apply_rebar_revision_assumptions(source.id)
    by_id = {item.id: item for item in workspace.list_elements(source_id=source.id)}
    assert by_id["rebar_a_1"].review_status == ReviewStatus.REJECTED
    assert by_id["rebar_b_1"].review_status == ReviewStatus.PENDING
    assert by_id["rebar_b_1"].properties["revision_selected"] is True


def test_source_mapping_clears_old_detections_and_records_explicit_repeats(
    tmp_path: Path,
) -> None:
    original = tmp_path / "normal-floor.dxf"
    original.write_text("immutable source", encoding="utf-8")
    workspace = ProjectWorkspace.create(tmp_path / "pilot.metrajai", "Pilot")
    source = workspace.add_source(original, discipline=Discipline.STRUCTURAL, role="kalip")
    workspace.replace_source_elements(source.id, [detected(source.id, height=3.0)])

    updated, cleared = workspace.update_source_mapping(
        source.id,
        role="kalip plani",
        floor="1. KAT",
        floor_kind=FloorKind.TYPICAL,
        sheet_kind=SheetKind.PLAN,
        repeat_floors=["2. KAT", "3. KAT", "2. kat"],
        revision="R01",
    )

    assert cleared == 1
    assert workspace.list_elements(source_id=source.id) == []
    assert updated.floor == "1. KAT"
    assert updated.floor_kind == FloorKind.TYPICAL
    assert updated.sheet_kind == SheetKind.PLAN
    assert updated.repeat_floors == ["2. KAT", "3. KAT"]
    assert updated.revision == "R01"

    with pytest.raises(ValueError, match="Kat tekrarı"):
        workspace.update_source_mapping(
            source.id,
            role="detay",
            floor="DETAY",
            floor_kind=FloorKind.DETAIL,
            sheet_kind=SheetKind.DETAIL,
            repeat_floors=["2. KAT"],
            revision="R01",
        )
