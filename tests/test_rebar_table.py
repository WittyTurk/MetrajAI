from pathlib import Path

import ezdxf
import pytest

from metrajai.analyzers.rebar_table import extract_beam_rebar_table
from metrajai.contracts import Discipline, DrawingUnit, SourceFile


def _source(path: Path) -> SourceFile:
    return SourceFile(
        project_id="prj_test",
        original_name=path.name,
        stored_path=path.name,
        sha256="b" * 64,
        size_bytes=1,
        discipline=Discipline.STRUCTURAL,
        role="reinforcement",
        drawing_unit=DrawingUnit.CM,
        unit_confirmed=True,
    )


def test_explicit_beam_rebar_schedule_is_parsed_without_estimating(tmp_path: Path) -> None:
    path = tmp_path / "rebar_schedule.dxf"
    document = ezdxf.new("R2018")
    table = document.blocks.new("GENERIC_REBAR_TABLE")
    headers = ("Poz", "Adet", "Çap", "Uzunluk (cm)", "Ağırlık (Kg)")
    for x_position, value in zip((0, 60, 120, 180, 360), headers, strict=True):
        table.add_text(value, dxfattribs={"insert": (x_position, 0), "height": 8})
    for y_position, values in (
        (-20, (1, 4, 16, 500, 31.60)),
        (-40, (2, 10, 8, 120, 4.74)),
    ):
        for x_position, value in zip((0, 60, 120, 180, 360), values, strict=True):
            table.add_text(str(value), dxfattribs={"insert": (x_position, y_position), "height": 8})

    scope = document.blocks.new("GENERIC_SCOPE")
    scope.add_text("KZ01 - KZ02", dxfattribs={"insert": (0, 0), "height": 8})
    modelspace = document.modelspace()
    modelspace.add_blockref("GENERIC_REBAR_TABLE", (0, 0), dxfattribs={"layer": "Standart"})
    modelspace.add_blockref("GENERIC_SCOPE", (0, -70), dxfattribs={"layer": "Standart"})
    document.saveas(path)

    elements, warnings = extract_beam_rebar_table(
        document,
        _source(path),
        [(0, 300)],
        {"KZ01", "KZ02"},
        0.01,
    )

    assert len(elements) == 2
    first = next(item for item in elements if item.properties["position_number"] == 1)
    assert first.measurements == {"length_m": 5.0, "count": 4.0, "diameter_mm": 16.0}
    assert first.properties["declared_weight_kg"] == pytest.approx(31.6)
    assert first.properties["calculated_weight_kg"] == pytest.approx(31.6049)
    assert any(warning.code == "BEAM_REBAR_TABLE_LINKED" for warning in warnings)
    assert not any(warning.code == "BEAM_REBAR_SCOPE_PARTIAL" for warning in warnings)
