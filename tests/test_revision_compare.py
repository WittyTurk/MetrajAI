from __future__ import annotations

from metrajai.contracts import DetectedElement, Discipline, Geometry, SourceFile
from metrajai.revision_compare import compare_revisions


def source(source_id: str, revision: str) -> SourceFile:
    return SourceFile(
        id=source_id,
        project_id="prj_revision",
        original_name=f"plan-{revision}.dxf",
        stored_path=f"sources/{source_id}.dxf",
        sha256=source_id * 32,
        size_bytes=1,
        discipline=Discipline.STRUCTURAL,
        role="kalip",
        floor="ZEMIN",
        revision=revision,
    )


def element(
    source_id: str,
    element_id: str,
    element_type: str,
    box: tuple[float, float, float, float],
    measurements: dict[str, float],
    label: str = "",
) -> DetectedElement:
    return DetectedElement(
        id=element_id,
        source_id=source_id,
        discipline=Discipline.STRUCTURAL,
        element_type=element_type,
        floor="ZEMIN",
        geometry=Geometry(kind="synthetic", bbox=box),
        measurements=measurements,
        properties={"element_label": label},
    )


def test_revision_compare_reports_added_deleted_modified_and_translation_safe_match() -> None:
    old = source("old", "R00")
    new = source("new", "R01")
    elements = [
        element(
            old.id,
            "old-column",
            "column",
            (0, 0, 0.4, 0.6),
            {"width_m": 0.4, "depth_m": 0.6, "height_m": 3.0},
            "K01",
        ),
        element(
            new.id,
            "new-column",
            "column",
            (100, 50, 100.4, 50.6),
            {"width_m": 0.4, "depth_m": 0.6, "height_m": 3.0},
            "K01",
        ),
        element(
            old.id,
            "old-beam",
            "beam",
            (1, 1, 6, 1.4),
            {"length_m": 5.0, "width_m": 0.4, "height_m": 0.6},
            "KZ01",
        ),
        element(
            new.id,
            "new-beam",
            "beam",
            (101, 51, 107, 51.4),
            {"length_m": 6.0, "width_m": 0.4, "height_m": 0.6},
            "KZ01",
        ),
        element(
            old.id,
            "old-slab",
            "slab",
            (0, 10, 5, 15),
            {"area_m2": 25.0, "thickness_m": 0.15},
            "D01",
        ),
        element(
            new.id,
            "new-column-added",
            "column",
            (110, 50, 110.4, 50.6),
            {"width_m": 0.4, "depth_m": 0.6, "height_m": 3.0},
            "K02",
        ),
    ]

    result = compare_revisions(old, new, elements)

    assert result.summary == {"added": 1, "deleted": 1, "modified": 1, "unchanged": 1}
    beam = next(item for item in result.changes if item.label == "KZ01")
    assert beam.kind == "modified"
    assert beam.changed_measurements["length_m"] == (5.0, 6.0)
    column = next(item for item in result.changes if item.label == "K01")
    assert column.kind == "unchanged"
    assert column.match_method == "unique_label"


def test_revision_compare_rejects_same_source() -> None:
    item = source("same", "R00")
    try:
        compare_revisions(item, item, [])
    except ValueError as exc:
        assert "iki farklı kaynak" in str(exc)
    else:
        raise AssertionError("same source comparison must fail")
