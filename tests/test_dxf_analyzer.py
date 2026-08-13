from __future__ import annotations

import math
from pathlib import Path

import ezdxf
import pytest

from metrajai.analyzers import DxfAnalyzer
from metrajai.analyzers.architectural_height import (
    apply_architectural_heights,
    extract_architectural_height_evidence,
)
from metrajai.calculations import calculate_quantities
from metrajai.contracts import (
    DetectedElement,
    Discipline,
    DrawingUnit,
    FloorKind,
    Geometry,
    ReviewStatus,
    SheetKind,
    SourceFile,
)


def source(path: Path, discipline: Discipline, *, confirmed: DrawingUnit | None = None):
    return SourceFile(
        project_id="prj_test",
        original_name=path.name,
        stored_path=path.name,
        sha256="a" * 64,
        size_bytes=path.stat().st_size,
        discipline=discipline,
        role="test",
        drawing_unit=confirmed or DrawingUnit.UNKNOWN,
        unit_confirmed=confirmed is not None,
    )


def test_mm_geometry_is_measured_but_missing_sections_require_review(tmp_path: Path) -> None:
    path = tmp_path / "structural.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (400, 0), (400, 600), (0, 600)],
        close=True,
        dxfattribs={"layer": "S-KOLON"},
    )
    msp.add_lwpolyline(
        [(0, 1000), (5000, 1000), (5000, 1300), (0, 1300)],
        close=True,
        dxfattribs={"layer": "S-KIRIS"},
    )
    msp.add_lwpolyline(
        [(0, 2000), (5000, 2000), (5000, 7000), (0, 7000)],
        close=True,
        dxfattribs={"layer": "S-DOSEME"},
    )
    doc.saveas(path)

    elements, warnings, detected_unit = DxfAnalyzer().analyze(
        source(path, Discipline.STRUCTURAL), path
    )

    assert detected_unit == DrawingUnit.MM
    column = next(item for item in elements if item.element_type == "column")
    beam = next(item for item in elements if item.element_type == "beam")
    slab = next(item for item in elements if item.element_type == "slab")
    assert column.measurements["width_m"] == pytest.approx(0.4)
    assert column.measurements["depth_m"] == pytest.approx(0.6)
    assert column.review_status == ReviewStatus.NEEDS_REVIEW
    assert beam.measurements["length_m"] == pytest.approx(5.0)
    assert beam.measurements["width_m"] == pytest.approx(0.3)
    assert slab.measurements["area_m2"] == pytest.approx(25.0)
    assert any(warning.code == "REBAR_SOURCE_MISSING" for warning in warnings)


def test_unknown_insunits_never_silently_scales_geometry(tmp_path: Path) -> None:
    path = tmp_path / "unitless.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 0
    doc.modelspace().add_lwpolyline(
        [(0, 0), (400, 0), (400, 600), (0, 600)],
        close=True,
        dxfattribs={"layer": "S-KOLON"},
    )
    doc.saveas(path)

    elements, warnings, detected_unit = DxfAnalyzer().analyze(
        source(path, Discipline.STRUCTURAL), path
    )

    assert detected_unit == DrawingUnit.UNKNOWN
    assert elements[0].review_status == ReviewStatus.NEEDS_REVIEW
    assert "length_m" not in elements[0].measurements
    assert any(warning.code == "UNIT_CONFIRMATION_REQUIRED" for warning in warnings)


def test_hatch_hole_is_subtracted_from_net_area(tmp_path: Path) -> None:
    path = tmp_path / "slab_with_hole.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    hatch = doc.modelspace().add_hatch(dxfattribs={"layer": "S-DOSEME"})
    hatch.paths.add_polyline_path([(0, 0), (10, 0), (10, 10), (0, 10)], is_closed=True, flags=1)
    hatch.paths.add_polyline_path([(4, 4), (6, 4), (6, 6), (4, 6)], is_closed=True, flags=0)
    doc.saveas(path)

    elements, _, _ = DxfAnalyzer().analyze(source(path, Discipline.STRUCTURAL), path)

    slab = next(item for item in elements if item.element_type == "slab")
    assert slab.measurements["area_m2"] == pytest.approx(96.0)
    assert slab.measurements["gross_area_m2"] == pytest.approx(100.0)
    assert slab.measurements["void_area_m2"] == pytest.approx(4.0)
    assert slab.measurements["void_count"] == 1
    assert slab.measurements["perimeter_m"] == pytest.approx(48.0)
    assert slab.properties["opening_evidence"]["void_count"] == 1


def test_foundation_shear_wall_and_stair_are_detected_without_invented_sections(
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing-structural-types.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (200, 0), (200, 5000), (0, 5000)],
        close=True,
        dxfattribs={"layer": "S-PERDE"},
    )
    msp.add_lwpolyline(
        [(10000, 0), (14000, 0), (14000, 3000), (10000, 3000)],
        close=True,
        dxfattribs={"layer": "S-TEKIL-TEMEL"},
    )
    msp.add_lwpolyline(
        [(20000, 0), (21200, 0), (21200, 4000), (20000, 4000)],
        close=True,
        dxfattribs={"layer": "S-MERDIVEN"},
    )
    doc.saveas(path)

    elements, _, _ = DxfAnalyzer().analyze(source(path, Discipline.STRUCTURAL), path)

    wall = next(item for item in elements if item.element_type == "shear_wall")
    assert wall.measurements["thickness_m"] == pytest.approx(0.2)
    assert wall.measurements["length_m"] == pytest.approx(5.0)
    assert "missing:height_m" in wall.issues
    foundation = next(item for item in elements if item.element_type == "foundation")
    assert foundation.measurements["area_m2"] == pytest.approx(12.0)
    assert foundation.measurements["perimeter_m"] == pytest.approx(14.0)
    assert "missing:thickness_m" in foundation.issues
    stair = next(item for item in elements if item.element_type == "stair")
    assert stair.measurements["plan_area_m2"] == pytest.approx(4.8)
    assert stair.measurements["horizontal_run_m"] == pytest.approx(4.0)
    assert "total_rise_m" not in stair.measurements
    assert "waist_thickness_m" not in stair.measurements
    assert stair.review_status == ReviewStatus.NEEDS_REVIEW


def test_bulge_arc_and_scaled_rotated_block_are_respected(tmp_path: Path) -> None:
    mechanical_path = tmp_path / "mechanical.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_lwpolyline(
        [(0, 0, 1), (1000, 0, 0)], format="xyb", dxfattribs={"layer": "M-BORU"}
    )
    doc.saveas(mechanical_path)
    pipe = DxfAnalyzer().analyze(source(mechanical_path, Discipline.MECHANICAL), mechanical_path)[
        0
    ][0]
    assert pipe.measurements["length_m"] == pytest.approx(math.pi / 2, rel=2e-3)

    structural_path = tmp_path / "block.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    block = doc.blocks.new("C40X60")
    block.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True)
    doc.modelspace().add_blockref(
        "C40X60",
        (0, 0),
        dxfattribs={"layer": "S-KOLON", "xscale": 2, "yscale": 1, "rotation": 90},
    )
    doc.saveas(structural_path)
    column = DxfAnalyzer().analyze(source(structural_path, Discipline.STRUCTURAL), structural_path)[
        0
    ][0]
    actual_section = sorted((column.measurements["width_m"], column.measurements["depth_m"]))
    assert actual_section == pytest.approx([0.6, 0.8])


def test_architectural_section_levels_supply_reviewable_column_height(
    tmp_path: Path,
) -> None:
    path = tmp_path / "architectural.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    level_block = doc.blocks.new("DIS_OLCU")
    level_block.add_text("+4.15")
    level_block.add_text("+0.15")
    level_block.add_mtext("ZEMİN KAT")
    doc.modelspace().add_blockref("DIS_OLCU", (0, 0))
    doc.saveas(path)
    architectural_source = source(path, Discipline.ARCHITECTURAL)

    evidence = extract_architectural_height_evidence(doc, architectural_source)

    assert len(evidence) == 1
    assert evidence[0].height_m == pytest.approx(4.0)
    column = DetectedElement(
        source_id="src_structural",
        discipline=Discipline.STRUCTURAL,
        element_type="column",
        floor="GENEL",
        geometry=Geometry(kind="closed_outline"),
        measurements={"width_m": 0.4, "depth_m": 0.6},
        required_inputs=["width_m", "depth_m", "height_m"],
        review_status=ReviewStatus.NEEDS_REVIEW,
        issues=["missing:height_m"],
    )

    elements, applied = apply_architectural_heights([column], evidence)

    assert applied == 1
    assert elements[0].measurements["height_m"] == pytest.approx(4.0)
    assert "missing:height_m" not in elements[0].issues
    trace = elements[0].properties["height_evidence"]
    assert trace["lower_level_m"] == pytest.approx(0.15)
    assert trace["upper_level_m"] == pytest.approx(4.15)


def test_architectural_room_boundaries_enter_engineer_review(tmp_path: Path) -> None:
    path = tmp_path / "architectural_plan.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_lwpolyline(
        [(0, 0), (5000, 0), (5000, 4000), (0, 4000)],
        close=True,
        dxfattribs={"layer": "ALAN"},
    )
    doc.saveas(path)

    elements, warnings, _ = DxfAnalyzer().analyze(source(path, Discipline.ARCHITECTURAL), path)

    room = next(item for item in elements if item.element_type == "room")
    assert room.measurements["area_m2"] == pytest.approx(20.0)
    assert room.measurements["perimeter_m"] == pytest.approx(18.0)
    assert room.review_status == ReviewStatus.PENDING
    assert any(warning.code == "ARCHITECTURAL_ENGINE_REVIEW_MODE" for warning in warnings)


def test_architectural_room_schedule_replaces_tiny_alan_symbols_and_reconciles_area(
    tmp_path: Path,
) -> None:
    path = tmp_path / "architectural_schedule.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    room_table = doc.blocks.new("ROOM_TABLE")
    for value in (
        "ZEMİN KAT MAHAL TABLOSU",
        "MAHAL KODU",
        "MAHAL ADI",
        "NET ALAN",
        "ZK01",
        "GİRİŞ",
        "9.90 M2",
        "SERAMİK",
        "BOYA",
        "BOYA",
        "ZK02",
        "SALON",
        "10.10 M2",
        "SERAMİK",
        "BOYA",
        "BOYA",
    ):
        room_table.add_text(value)
    msp.add_blockref("ROOM_TABLE", (0, 0))
    totals = doc.blocks.new("AREA_TOTALS")
    for value in (
        "BAĞIMSIZ BÖLÜM TABLOSU",
        "BB NET ALAN",
        "BB BRÜT ALAN",
        "20.10 M2",
        "25.00 M2",
    ):
        totals.add_text(value)
    msp.add_blockref("AREA_TOTALS", (1000, 0))
    msp.add_lwpolyline(
        [(0, 0), (200, 0), (200, 100), (0, 100)],
        close=True,
        dxfattribs={"layer": "ALAN"},
    )
    doc.saveas(path)

    elements, warnings, _ = DxfAnalyzer().analyze(
        source(path, Discipline.ARCHITECTURAL),
        path,
    )

    rooms = [item for item in elements if item.element_type == "room"]
    assert [item.properties["room_code"] for item in rooms] == ["ZK01", "ZK02"]
    assert sum(item.measurements["area_m2"] for item in rooms) == pytest.approx(20.0)
    assert all(item.geometry.kind == "architectural_schedule_row" for item in rooms)
    assert all(item.floor == "Zemin Kat" for item in rooms)
    codes = {warning.code for warning in warnings}
    assert "ARCHITECTURAL_ROOM_SCHEDULE_EXTRACTED" in codes
    assert "ARCHITECTURAL_NET_AREA_MISMATCH" in codes
    assert "ARCHITECTURAL_GROSS_AREA_EVIDENCE" in codes


def test_exported_foundation_edges_and_wall_labels_are_deduplicated(
    tmp_path: Path,
) -> None:
    path = tmp_path / "exported-foundation.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 5
    msp = doc.modelspace()

    for index, points in enumerate(
        (
            [(0, 0), (1000, 0)],
            [(1000, 0), (1000, 600)],
            [(1000, 600), (0, 600)],
            [(0, 600), (0, 0)],
        )
    ):
        block = doc.blocks.new(f"RAFT_EDGE_{index}")
        block.add_lwpolyline(points, dxfattribs={"layer": "RadyeDöşemeKenarı"})

    for label, y in (("PZ01", 200), ("PZ02", 400)):
        hatch_block = doc.blocks.new(f"WALL_{label}")
        hatch = hatch_block.add_hatch(dxfattribs={"layer": "Perde"})
        hatch.paths.add_polyline_path(
            [(100, y), (600, y), (600, y + 25), (100, y + 25)],
            is_closed=True,
        )
        label_block = doc.blocks.new(f"LABEL_{label}")
        label_block.add_text(
            f"{label} [+15.00] 500/75/25",
            dxfattribs={"insert": (200, y)},
        )

    for root_y in (0, 2000):
        for index in range(4):
            msp.add_blockref(
                f"RAFT_EDGE_{index}",
                (0, root_y),
                dxfattribs={"layer": "RadyeDöşemeKenarı"},
            )
        for label in ("PZ01", "PZ02"):
            msp.add_blockref(
                f"WALL_{label}",
                (0, root_y),
                dxfattribs={"layer": "Perde"},
            )
            msp.add_blockref(
                f"LABEL_{label}",
                (0, root_y),
                dxfattribs={"layer": "Perde"},
            )
    doc.saveas(path)

    elements, warnings, _ = DxfAnalyzer().analyze(
        source(path, Discipline.STRUCTURAL),
        path,
    )

    rafts = [item for item in elements if item.element_type == "raft"]
    walls = [item for item in elements if item.element_type == "shear_wall"]
    assert len(rafts) == 1
    assert rafts[0].measurements["area_m2"] == pytest.approx(60.0)
    assert rafts[0].measurements["perimeter_m"] == pytest.approx(32.0)
    assert "missing:thickness_m" in rafts[0].issues
    assert len(walls) == 2
    assert {item.properties["element_label"] for item in walls} == {"PZ01", "PZ02"}
    assert all(item.measurements["length_m"] == pytest.approx(5.0) for item in walls)
    assert all(item.measurements["height_m"] == pytest.approx(0.75) for item in walls)
    assert all(item.measurements["thickness_m"] == pytest.approx(0.25) for item in walls)
    assert any(warning.code == "FOUNDATION_APPLICATION_PLAN_PARSED" for warning in warnings)
    assert any(warning.code == "FOUNDATION_THICKNESS_REQUIRED" for warning in warnings)


def test_structural_detail_sheet_is_reference_only_even_with_quantity_layers(
    tmp_path: Path,
) -> None:
    path = tmp_path / "beam-details.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_line(
        (0, 0),
        (5000, 0),
        dxfattribs={"layer": "S-KIRIS-DETAY"},
    )
    doc.saveas(path)
    detail_source = source(path, Discipline.STRUCTURAL)
    detail_source.floor_kind = FloorKind.DETAIL
    detail_source.sheet_kind = SheetKind.DETAIL

    elements, warnings, _ = DxfAnalyzer().analyze(detail_source, path)

    assert elements == []
    assert [warning.code for warning in warnings] == ["REFERENCE_SHEET_EXCLUDED_FROM_COUNTS"]


def test_multiview_structural_plans_use_explicit_elevations_and_drawn_beam_edges(
    tmp_path: Path,
) -> None:
    path = tmp_path / "multi-floor-structural.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 5  # centimetres
    msp = doc.modelspace()

    def add_formwork_view(root_x: float, elevation: str, prefix: str) -> None:
        msp.add_text(
            f"{elevation} KOTU KALIP  PLANI",
            dxfattribs={"insert": (root_x, -1500), "layer": "BASLIK"},
        )
        beam_rows = (
            ((root_x - 800, 0), (root_x + 800, 0)),
            ((root_x - 800, 40), (root_x + 800, 40)),
            ((root_x - 800, 960), (root_x + 800, 960)),
            ((root_x - 800, 1000), (root_x + 800, 1000)),
            ((root_x - 800, 40), (root_x - 800, 960)),
            ((root_x - 760, 40), (root_x - 760, 960)),
            ((root_x + 760, 40), (root_x + 760, 960)),
            ((root_x + 800, 40), (root_x + 800, 960)),
        )
        for start, end in beam_rows:
            msp.add_line(start, end, dxfattribs={"layer": "KIRIS"})
        msp.add_text(
            f"K{prefix}01 (40/80)",
            dxfattribs={"insert": (root_x - 780, -25), "layer": "KIRIS YAZI"},
        )
        msp.add_text(
            f"K{prefix}02 (40/80)",
            dxfattribs={"insert": (root_x - 780, 1025), "layer": "KIRIS YAZI"},
        )
        msp.add_text(
            f"K{prefix}03 (40/80)",
            dxfattribs={
                "insert": (root_x - 825, 60),
                "rotation": 90,
                "layer": "KIRIS YAZI",
            },
        )
        msp.add_text(
            f"K{prefix}04 (40/80)",
            dxfattribs={
                "insert": (root_x + 825, 60),
                "rotation": 90,
                "layer": "KIRIS YAZI",
            },
        )
        msp.add_text(
            f"D{prefix}01",
            dxfattribs={"insert": (root_x, 500), "layer": "DOSEME ADI"},
        )
        msp.add_text(
            "D=20cm",
            dxfattribs={"insert": (root_x, 475), "layer": "DOSEME ADI"},
        )

    add_formwork_view(0, "+1.20", "A")
    msp.add_lwpolyline(
        [(-200, 400), (200, 400), (200, 600), (-200, 600)],
        close=True,
        dxfattribs={"layer": "BOSLUK"},
    )
    msp.add_text(
        "+1.20 KOTU DONATI PLANI",
        dxfattribs={"insert": (4000, -1500), "layer": "BASLIK"},
    )
    msp.add_text(
        "KOTLARI ARASI KOLON APLİKASYON PLANI",
        dxfattribs={"insert": (6000, -1500), "layer": "BASLIK"},
    )
    msp.add_lwpolyline(
        [(5900, 0), (5940, 0), (5940, 60), (5900, 60)],
        close=True,
        dxfattribs={"layer": "KOLON KA"},
    )
    add_formwork_view(10000, "+5.20", "B")
    msp.add_text(
        "+5.20 KOTU DONATI PLANI",
        dxfattribs={"insert": (14000, -1500), "layer": "BASLIK"},
    )
    doc.saveas(path)

    elements, warnings, detected_unit = DxfAnalyzer().analyze(
        source(path, Discipline.STRUCTURAL), path
    )

    assert detected_unit == DrawingUnit.CM
    beams = [item for item in elements if item.element_type == "beam"]
    slabs = [item for item in elements if item.element_type == "slab"]
    columns = [item for item in elements if item.element_type == "column"]
    assert len(beams) == 8
    assert len(slabs) == 2
    assert {item.floor for item in beams} == {"+1.20 Kotu", "+5.20 Kotu"}
    assert all(item.measurements["width_m"] == pytest.approx(0.4) for item in beams)
    assert all(item.measurements["height_m"] == pytest.approx(0.8) for item in beams)
    assert all(item.measurements["thickness_m"] == pytest.approx(0.2) for item in slabs)
    first_slab = next(item for item in slabs if item.floor == "+1.20 Kotu")
    assert first_slab.measurements["gross_area_m2"] == pytest.approx(139.84)
    assert first_slab.measurements["void_area_m2"] == pytest.approx(8.0)
    assert first_slab.measurements["area_m2"] == pytest.approx(131.84)
    assert first_slab.properties["slab_evidence"]["void_count"] == 1
    assert all(item.measurements.get("formwork_area_m2", 0) > 0 for item in beams)
    assert all("missing:formwork_area_m2" not in item.issues for item in beams)
    assert len(columns) == 1
    assert columns[0].floor == "+5.20 Kotu"
    assert columns[0].measurements["height_m"] == pytest.approx(4.0)
    assert any(warning.code == "MULTIVIEW_STRUCTURAL_PLANS_PARSED" for warning in warnings)
    assert any(warning.code == "MULTIVIEW_SOURCE_OWNERSHIP_APPLIED" for warning in warnings)

    blocked_elements, blocked_warnings, _ = DxfAnalyzer().analyze(
        source(path, Discipline.STRUCTURAL, confirmed=DrawingUnit.MM), path
    )
    assert blocked_elements == []
    assert any(warning.code == "UNIT_MISMATCH_SUSPECTED" for warning in blocked_warnings)


def test_multiview_foundation_deduplicates_translated_boundary_and_reads_thickness(
    tmp_path: Path,
) -> None:
    path = tmp_path / "translated-foundation.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 5
    msp = doc.modelspace()
    msp.add_text(
        "TEMEL KALIP PLANI",
        dxfattribs={"insert": (0, -1500), "layer": "BASLIK"},
    )
    msp.add_text(
        "TEMEL DONATI PLANI",
        dxfattribs={"insert": (10000, -1500), "layer": "BASLIK"},
    )
    msp.add_text(
        "+1.20 KOTU KALIP PLANI",
        dxfattribs={"insert": (20000, -1500), "layer": "BASLIK"},
    )
    for root_x in (-2000, 1000):
        msp.add_lwpolyline(
            [(root_x, 0), (root_x + 1000, 0), (root_x + 1000, 600), (root_x, 600)],
            close=True,
            dxfattribs={"layer": "PENC3"},
        )
        msp.add_text(
            "H=80 cm",
            dxfattribs={"insert": (root_x + 500, 300), "layer": "DOSEME ADI KA"},
        )
    msp.add_text(
        "Betonarme Radye Temel 80 cm",
        dxfattribs={"insert": (-2500, -500), "layer": "ACIKLAMA"},
    )
    doc.saveas(path)

    elements, warnings, detected_unit = DxfAnalyzer().analyze(
        source(path, Discipline.STRUCTURAL), path
    )

    assert detected_unit == DrawingUnit.CM
    rafts = [item for item in elements if item.element_type == "raft"]
    assert len(rafts) == 1
    raft = rafts[0]
    assert raft.floor == "TEMEL"
    assert raft.measurements["area_m2"] == pytest.approx(60.0)
    assert raft.measurements["perimeter_m"] == pytest.approx(32.0)
    assert raft.measurements["thickness_m"] == pytest.approx(0.8)
    assert raft.properties["foundation_evidence"]["translated_copy_count"] == 2
    assert raft.review_status == ReviewStatus.NEEDS_REVIEW
    assert "review:translated_foundation_views_deduplicated" in raft.issues
    assert any(warning.code == "MULTIVIEW_STRUCTURAL_PLANS_PARSED" for warning in warnings)


def test_multiview_stair_annotations_require_geometry_and_explicit_floor_repeat(
    tmp_path: Path,
) -> None:
    path = tmp_path / "stair-plan-annotations.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 5
    msp = doc.modelspace()
    for root_x, title in (
        (0, "TEMEL KALIP PLANI"),
        (10000, "TEMEL DONATI PLANI"),
        (20000, "+1.20 KOTU KALIP PLANI"),
    ):
        msp.add_text(title, dxfattribs={"insert": (root_x, -1500), "layer": "BASLIK"})
    msp.add_text(
        "-3.30 İLE +1.20 KOTLARI ARASI MERDİVEN KALIP DONATI PLANI",
        dxfattribs={"insert": (30000, 0), "layer": "KA MAHAL ADI"},
    )
    msp.add_text(
        "M1 MERDİVENİ 27 (30/16.66)",
        dxfattribs={"insert": (30050, 20), "layer": "Y_MERDIVEN"},
    )
    msp.add_text(
        "KOTLARI ARASI MERDİVEN KALIP DONATI PLANI",
        dxfattribs={"insert": (33000, 0), "layer": "KA MAHAL ADI"},
    )
    msp.add_text(
        "M2 MERDİVENİ 24 (30/16.66)",
        dxfattribs={"insert": (33050, 20), "layer": "Y_MERDIVEN"},
    )
    doc.saveas(path)

    elements, warnings, _ = DxfAnalyzer().analyze(source(path, Discipline.STRUCTURAL), path)

    stairs = [item for item in elements if item.element_type == "stair"]
    assert len(stairs) == 2
    explicit = next(item for item in stairs if item.properties["element_label"] == "M1")
    typical = next(item for item in stairs if item.properties["element_label"] == "M2")
    assert explicit.floor == "-3.30 → +1.20 Merdiveni"
    assert explicit.measurements["total_rise_m"] == pytest.approx(4.5)
    assert explicit.measurements["step_count"] == 27
    assert "missing:plan_area_m2" in explicit.issues
    assert "missing:waist_thickness_m" in explicit.issues
    assert typical.measurements["total_rise_m"] == pytest.approx(3.9984)
    assert "blocking:stair_floor_repeat_required" in typical.issues
    assert any(warning.code == "STAIR_PLAN_ANNOTATIONS_LINKED" for warning in warnings)
    assert any(warning.code == "TYPICAL_STAIR_REPEAT_REQUIRED" for warning in warnings)


def test_multiview_stair_uses_explicit_boundary_thickness_and_step_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "stair-with-explicit-evidence.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 5
    msp = doc.modelspace()
    for root_x, title in (
        (0, "TEMEL KALIP PLANI"),
        (10000, "TEMEL DONATI PLANI"),
        (20000, "+3.00 KOTU KALIP PLANI"),
    ):
        msp.add_text(title, dxfattribs={"insert": (root_x, -1500), "layer": "BASLIK"})
    msp.add_text(
        "+0.00 İLE +3.00 KOTLARI ARASI MERDİVEN KALIP DONATI PLANI",
        dxfattribs={"insert": (30000, 0), "layer": "KA MAHAL ADI"},
    )
    msp.add_text(
        "M1 MERDİVENİ 18 (28/16.67)",
        dxfattribs={"insert": (30050, 20), "layer": "Y_MERDIVEN"},
    )
    msp.add_text(
        "H=15 CM",
        dxfattribs={"insert": (30060, 40), "layer": "Y_MERDIVEN"},
    )
    msp.add_lwpolyline(
        [(30000, 100), (30400, 100), (30400, 220), (30000, 220)],
        close=True,
        dxfattribs={"layer": "Y_MERDIVEN"},
    )
    doc.saveas(path)

    elements, _, _ = DxfAnalyzer().analyze(source(path, Discipline.STRUCTURAL), path)

    stair = next(item for item in elements if item.element_type == "stair")
    assert stair.properties["element_label"] == "M1"
    assert stair.measurements["plan_area_m2"] == pytest.approx(4.8)
    assert stair.measurements["horizontal_run_m"] == pytest.approx(4.0)
    assert stair.measurements["stair_width_m"] == pytest.approx(1.2)
    assert stair.measurements["waist_thickness_m"] == pytest.approx(0.15)
    assert stair.measurements["step_volume_m3"] == pytest.approx(0.5041008)
    assert stair.measurements["riser_formwork_m2"] == pytest.approx(3.60072)
    assert stair.measurements["side_formwork_m2"] == pytest.approx(1.5)
    stair.review_status = ReviewStatus.ACCEPTED
    lines, warnings = calculate_quantities([stair])
    assert not warnings
    assert {line.description for line in lines} >= {
        "Merdiven eğimli plak betonu",
        "Merdiven basamak betonu",
        "Merdiven eğimli alt kalıbı",
        "Merdiven yan kalıbı",
        "Merdiven rıht kalıbı",
    }


def test_structural_plan_filter_skips_translated_duplicate_and_blocks_wrong_unit(
    tmp_path: Path,
) -> None:
    path = tmp_path / "specialized_structural.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    column_blocks: list[str] = []
    for index, x_position in enumerate((0, 200, 400, 600, 800), start=1):
        name = f"COLUMN_{index}"
        block = doc.blocks.new(name)
        block.add_lwpolyline(
            [
                (x_position, 0),
                (x_position + 40, 0),
                (x_position + 40, 60),
                (x_position, 60),
            ],
            close=True,
        )
        block.add_text(f"SZ{index:02d}", dxfattribs={"insert": (x_position, 0)})
        column_blocks.append(name)
    beam_blocks: list[str] = []
    for index, y_position in enumerate((200, 240, 400, 440, 600, 640), start=1):
        name = f"BEAM_EDGE_{index}"
        block = doc.blocks.new(name)
        block.add_line((0, y_position), (500, y_position))
        beam_blocks.append(name)
    beam_label_blocks: list[str] = []
    for index, y_position in enumerate((200, 400, 600), start=1):
        name = f"BEAM_LABEL_{index}"
        block = doc.blocks.new(name)
        block.add_text(
            f"KZ{index:02d} 40/60",
            dxfattribs={"insert": (20, y_position + 10), "height": 10},
        )
        beam_label_blocks.append(name)

    for root in ((1000, 1000), (1000, -2000)):
        for name in column_blocks:
            msp.add_blockref(name, root, dxfattribs={"layer": "Kolon"})
        for name in beam_blocks:
            msp.add_blockref(name, root, dxfattribs={"layer": "Kiriş"})
        for name in beam_label_blocks:
            msp.add_blockref(name, root, dxfattribs={"layer": "Kiriş"})
        msp.add_text(
            "DONATISIZ KALIP PLANI",
            dxfattribs={"insert": (root[0], root[1] + 900)},
        )
    doc.saveas(path)

    elements, warnings, _ = DxfAnalyzer().analyze(
        source(path, Discipline.STRUCTURAL, confirmed=DrawingUnit.MM), path
    )

    assert sum(item.element_type == "column" for item in elements) == 5
    assert sum(item.element_type == "beam" for item in elements) == 3
    assert any(warning.code == "REPEATED_STRUCTURAL_PLANS_SKIPPED" for warning in warnings)
    assert any(warning.code == "UNIT_MISMATCH_SUSPECTED" for warning in warnings)
    beams = [item for item in elements if item.element_type == "beam"]
    assert {item.properties["element_label"] for item in beams} == {"KZ01", "KZ02", "KZ03"}
    assert all(item.measurements["height_m"] == pytest.approx(0.6) for item in beams)
    assert all(
        "blocking:unit_mismatch_suspected" in item.issues
        for item in elements
        if item.element_type in {"column", "beam"}
    )


def test_generic_multi_view_filter_keeps_confirmed_plan_once_and_skips_details(
    tmp_path: Path,
) -> None:
    path = tmp_path / "multi-view.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    roots = (0, 20000, 40000)
    for root in roots:
        msp.add_text(
            "1. KAT KALIP PLANI",
            dxfattribs={"insert": (root, -1000)},
        )
    for root in roots[:2]:
        for offset in (0, 3000, 6000, 9000):
            msp.add_lwpolyline(
                [
                    (root + offset, 0),
                    (root + offset + 400, 0),
                    (root + offset + 400, 600),
                    (root + offset, 600),
                ],
                close=True,
                dxfattribs={"layer": "S-KOLON"},
            )
    msp.add_lwpolyline(
        [(40000, 0), (40400, 0), (40400, 600), (40000, 600)],
        close=True,
        dxfattribs={"layer": "S-KOLON"},
    )
    doc.saveas(path)

    elements, warnings, _ = DxfAnalyzer().analyze(source(path, Discipline.STRUCTURAL), path)

    columns = [item for item in elements if item.element_type == "column"]
    assert len(columns) == 4
    assert all(item.properties["plan_region_title"] == "1. KAT KALIP PLANI" for item in columns)
    assert any(warning.code == "MULTI_VIEW_PLAN_REGIONS_FILTERED" for warning in warnings)
    assert any(warning.code == "DUPLICATE_PLAN_REGIONS_SKIPPED" for warning in warnings)
