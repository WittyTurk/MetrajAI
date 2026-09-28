from __future__ import annotations

from metrajai.contracts import DetectedElement, Discipline, Geometry, ReviewStatus
from metrajai.structural_readiness import structural_completion_blockers


def _element(
    element_id: str,
    source_id: str,
    element_type: str,
    *,
    measurements: dict[str, float] | None = None,
    properties: dict | None = None,
    issues: list[str] | None = None,
) -> DetectedElement:
    return DetectedElement(
        id=element_id,
        source_id=source_id,
        discipline=Discipline.STRUCTURAL,
        element_type=element_type,
        geometry=Geometry(kind="test"),
        measurements=measurements or {},
        properties=properties or {},
        issues=issues or [],
        review_status=ReviewStatus.ACCEPTED,
    )


def test_completion_accepts_rebar_from_separate_source() -> None:
    column = _element("column", "plan", "column")
    raft = _element("raft", "plan", "raft", measurements={"thickness_m": 0.5})
    rebar = _element("rebar", "schedule", "rebar")
    assert structural_completion_blockers([column, raft, rebar]) == []


def test_completion_requires_revision_selection_and_thickness() -> None:
    raft = _element("raft", "plan", "raft")
    rebar = _element(
        "rebar", "schedule", "rebar",
        properties={"revision_candidates": [{"label": "A"}, {"label": "B"}]},
    )
    assert {item.code for item in structural_completion_blockers([raft, rebar])} == {
        "RAFT_THICKNESS_REQUIRED", "REBAR_REVISION_REQUIRED",
    }
    raft.measurements["thickness_m"] = 0.5
    rebar.properties["revision_selected"] = True
    assert structural_completion_blockers([raft, rebar]) == []


def test_completion_blocks_written_unit_conflict() -> None:
    column = _element(
        "column", "plan", "column",
        issues=["blocking:drawing_unit_evidence_mismatch"],
    )
    rebar = _element("rebar", "schedule", "rebar")
    assert [item.code for item in structural_completion_blockers([column, rebar])] == [
        "STRUCTURAL_UNIT_UNRESOLVED",
    ]
