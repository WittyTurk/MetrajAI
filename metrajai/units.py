from __future__ import annotations

from .contracts import DrawingUnit

UNIT_TO_METRE: dict[DrawingUnit, float] = {
    DrawingUnit.MM: 0.001,
    DrawingUnit.CM: 0.01,
    DrawingUnit.M: 1.0,
}

DXF_INSUNITS: dict[int, DrawingUnit] = {
    4: DrawingUnit.MM,
    5: DrawingUnit.CM,
    6: DrawingUnit.M,
}


class UnitConfirmationRequired(ValueError):
    pass


def unit_from_insunits(code: int | None) -> DrawingUnit:
    if code is None:
        return DrawingUnit.UNKNOWN
    return DXF_INSUNITS.get(int(code), DrawingUnit.UNKNOWN)


def unit_scale(unit: DrawingUnit) -> float:
    if unit not in UNIT_TO_METRE:
        raise UnitConfirmationRequired("DXF drawing unit must be confirmed before calculation")
    return UNIT_TO_METRE[unit]


def resolve_unit(
    confirmed: DrawingUnit,
    detected: DrawingUnit,
) -> tuple[DrawingUnit, float]:
    chosen = confirmed if confirmed != DrawingUnit.UNKNOWN else detected
    return chosen, unit_scale(chosen)
