from __future__ import annotations

from metrajai.contracts import (
    DetectedElement,
    Discipline,
    FloorKind,
    Geometry,
    ReviewStatus,
    SheetKind,
    SourceFile,
)
from metrajai.floor_management import (
    apply_sheet_ownership,
    expand_explicit_floor_repeats,
    infer_floor_kind,
    infer_sheet_kind,
)


def source_file(
    *,
    floor_kind: FloorKind = FloorKind.TYPICAL,
    sheet_kind: SheetKind = SheetKind.PLAN,
    repeat_floors: list[str] | None = None,
) -> SourceFile:
    return SourceFile(
        id="src_floor",
        project_id="prj_floor",
        original_name="NORMAL KAT KALIP PLANI.dxf",
        stored_path="sources/plan.dxf",
        sha256="a" * 64,
        size_bytes=1,
        discipline=Discipline.STRUCTURAL,
        role="kalip",
        floor="1. KAT",
        floor_kind=floor_kind,
        sheet_kind=sheet_kind,
        repeat_floors=repeat_floors or [],
    )


def physical(element_type: str, element_id: str) -> DetectedElement:
    return DetectedElement(
        id=element_id,
        source_id="src_floor",
        discipline=Discipline.STRUCTURAL,
        element_type=element_type,
        floor="1. KAT",
        geometry=Geometry(kind="synthetic"),
        measurements={"area_m2": 12.0},
        required_inputs=["area_m2"],
        review_status=ReviewStatus.PENDING,
    )


def test_floor_and_sheet_kind_are_inferred_from_turkish_names() -> None:
    assert infer_floor_kind("B1", "BODRUM KAT KALIP.dxf") == FloorKind.BASEMENT
    assert infer_floor_kind("Z01", "ZEMİN KAT.dxf") == FloorKind.GROUND
    assert infer_floor_kind("N01", "NORMAL KAT.dxf") == FloorKind.TYPICAL
    assert infer_floor_kind("T01", "TEMEL PLANI.dxf") == FloorKind.FOUNDATION
    assert infer_sheet_kind("SU.03 KOLON DETAYLARI.dxf") == SheetKind.DETAIL
    assert infer_sheet_kind("SU.01 KALIP VE DONATI.dxf") == SheetKind.PLAN
    assert infer_sheet_kind("SU.02 KOLON APLİKASYON.dxf") == SheetKind.COLUMN_APPLICATION
    assert infer_sheet_kind("KİRİŞ DONATI PLANI.dxf") == SheetKind.REBAR_PLAN


def test_only_explicit_physical_floor_repeats_are_created() -> None:
    source = source_file(repeat_floors=["2. KAT", "3. KAT", "2. kat", "1. KAT", ""])
    slab = physical("slab", "elm_slab")
    rebar = physical("rebar", "elm_rebar")

    expanded, warnings = expand_explicit_floor_repeats([slab, rebar], source)

    assert [(item.element_type, item.floor) for item in expanded] == [
        ("slab", "1. KAT"),
        ("rebar", "1. KAT"),
        ("slab", "2. KAT"),
        ("slab", "3. KAT"),
    ]
    clones = [item for item in expanded if item.properties.get("explicit_floor_repeat")]
    assert len({item.id for item in clones}) == 2
    assert all(item.properties["repeated_from_element_id"] == slab.id for item in clones)
    assert {warning.code for warning in warnings} == {
        "EXPLICIT_FLOOR_REPETITION_APPLIED",
        "NON_PHYSICAL_ITEMS_NOT_REPEATED",
    }


def test_repeat_mapping_never_applies_to_detail_or_non_typical_sheet() -> None:
    source = source_file(
        floor_kind=FloorKind.DETAIL,
        sheet_kind=SheetKind.DETAIL,
        repeat_floors=["2. KAT"],
    )
    item = physical("column", "elm_column")

    expanded, warnings = expand_explicit_floor_repeats([item], source)

    assert expanded == [item]
    assert [warning.code for warning in warnings] == ["FLOOR_REPEAT_MAPPING_INVALID"]


def test_column_application_is_authoritative_and_plan_columns_are_not_duplicated() -> None:
    plan = source_file()
    application = source_file(sheet_kind=SheetKind.COLUMN_APPLICATION)
    application.id = "src_application"
    column = physical("column", "elm_column")
    beam = physical("beam", "elm_beam")

    plan_elements, plan_warnings = apply_sheet_ownership([column, beam], plan, [plan, application])
    app_elements, app_warnings = apply_sheet_ownership(
        [column, beam], application, [plan, application]
    )

    assert [item.element_type for item in plan_elements] == ["beam"]
    assert [warning.code for warning in plan_warnings] == ["COLUMNS_DEFERRED_TO_APPLICATION_SHEET"]
    assert [item.element_type for item in app_elements] == ["column"]
    assert [warning.code for warning in app_warnings] == ["COLUMN_APPLICATION_ROLE_FILTERED"]
