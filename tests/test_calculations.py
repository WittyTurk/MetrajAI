from __future__ import annotations

import pytest

from metrajai.calculations import calculate_quantities
from metrajai.contracts import (
    Assumption,
    DetectedElement,
    Discipline,
    Geometry,
    ReviewStatus,
)


def element(element_type: str, measurements: dict[str, float], *, accepted: bool = True):
    return DetectedElement(
        id=f"elm_{element_type}",
        source_id="src_1",
        discipline=Discipline.STRUCTURAL,
        element_type=element_type,
        floor="Z01",
        geometry=Geometry(kind="synthetic"),
        measurements=measurements,
        required_inputs=list(measurements),
        confidence=1.0,
        review_status=ReviewStatus.ACCEPTED if accepted else ReviewStatus.PENDING,
    )


def test_structural_formulas_are_exact_and_unapproved_elements_are_excluded() -> None:
    column = element("column", {"width_m": 0.4, "depth_m": 0.6, "height_m": 3.0})
    pending_beam = element(
        "beam", {"width_m": 0.3, "height_m": 0.5, "length_m": 5.0}, accepted=False
    )

    lines, warnings = calculate_quantities([column, pending_beam])

    assert warnings == []
    assert [(line.description, line.unit) for line in lines] == [
        ("Kolon betonu", "m³"),
        ("Kolon yan kalıbı (brüt; birleşimler düşülmemiş)", "m²"),
    ]
    assert lines[0].quantity == pytest.approx(0.72)
    assert lines[1].quantity == pytest.approx(6.0)


def test_beam_formwork_uses_reconciled_direct_area() -> None:
    beam = element(
        "beam",
        {
            "width_m": 0.4,
            "height_m": 0.6,
            "length_m": 5.0,
            "formwork_area_m2": 6.0,
        },
    )

    lines, _ = calculate_quantities([beam])

    concrete = next(line for line in lines if line.category == "Beton")
    formwork = next(line for line in lines if line.category == "Kalıp")
    assert concrete.quantity == pytest.approx(1.2)
    assert formwork.quantity == pytest.approx(6.0)
    assert formwork.formula == "formwork_area_m2"


def test_rebar_net_lap_hook_and_waste_are_separate_lines() -> None:
    rebar = element("rebar", {"length_m": 12.0, "count": 10, "diameter_mm": 16})
    assumptions = [
        Assumption(key="rebar_lap_percent", value=8.0, unit="%", approved=True),
        Assumption(key="rebar_hook_percent", value=2.0, unit="%", approved=True),
        Assumption(key="rebar_waste_percent", value=5.0, unit="%", approved=True),
    ]

    lines, warnings = calculate_quantities([rebar], assumptions)

    assert warnings == []
    assert [line.description for line in lines] == [
        "Net donatı",
        "Bindirme ilavesi",
        "Kanca ilavesi",
        "Fire ilavesi",
    ]
    assert lines[0].quantity == pytest.approx(12 * 10 * 16**2 / 162)
    assert lines[1].quantity == pytest.approx(lines[0].quantity * 0.08)
    assert lines[2].quantity == pytest.approx(lines[0].quantity * 0.02)
    assert lines[3].quantity == pytest.approx(lines[0].quantity * 0.05)


def test_stair_quantity_requires_explicit_section_and_uses_inclined_length() -> None:
    stair = element(
        "stair",
        {
            "plan_area_m2": 4.8,
            "horizontal_run_m": 4.0,
            "total_rise_m": 3.0,
            "waist_thickness_m": 0.15,
        },
    )

    lines, warnings = calculate_quantities([stair])

    assert warnings == []
    assert lines[0].description == "Merdiven eğimli plak betonu"
    assert lines[0].quantity == pytest.approx(4.8 * 1.25 * 0.15)
    assert lines[1].description == "Merdiven eğimli alt kalıbı"
    assert lines[1].quantity == pytest.approx(4.8 * 1.25)
