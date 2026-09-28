from __future__ import annotations

import pytest

from metrajai.contracts import DrawingUnit
from metrajai.units import (
    UnitConfirmationRequired,
    resolve_unit,
    suggest_unit_from_area_ratio,
    unit_from_insunits,
    unit_scale,
)


@pytest.mark.parametrize(
    ("selected", "ratio", "expected"),
    [
        (DrawingUnit.MM, 100, DrawingUnit.CM),
        (DrawingUnit.CM, 0.01, DrawingUnit.MM),
        (DrawingUnit.M, 0.0001, DrawingUnit.CM),
        (DrawingUnit.CM, 10000, DrawingUnit.M),
        (DrawingUnit.MM, 87, DrawingUnit.CM),
        (DrawingUnit.CM, 1.5, None),
    ],
)
def test_written_area_suggests_only_consistent_unit(selected, ratio, expected) -> None:
    assert suggest_unit_from_area_ratio(selected, ratio) == expected


def test_supported_dxf_units_are_converted_to_metres() -> None:
    assert unit_from_insunits(4) == DrawingUnit.MM
    assert unit_from_insunits(5) == DrawingUnit.CM
    assert unit_from_insunits(6) == DrawingUnit.M
    assert unit_scale(DrawingUnit.MM) == pytest.approx(0.001)
    assert unit_scale(DrawingUnit.CM) == pytest.approx(0.01)
    assert unit_scale(DrawingUnit.M) == pytest.approx(1.0)


def test_unknown_unit_requires_explicit_confirmation() -> None:
    assert unit_from_insunits(0) == DrawingUnit.UNKNOWN
    with pytest.raises(UnitConfirmationRequired):
        resolve_unit(DrawingUnit.UNKNOWN, DrawingUnit.UNKNOWN)
