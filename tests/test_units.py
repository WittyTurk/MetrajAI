from __future__ import annotations

import pytest

from metrajai.contracts import DrawingUnit
from metrajai.units import UnitConfirmationRequired, resolve_unit, unit_from_insunits, unit_scale


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
