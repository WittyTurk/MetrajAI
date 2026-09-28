from __future__ import annotations

import math

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


def suggest_unit_from_area_ratio(
    selected_unit: DrawingUnit, declared_to_geometric_ratio: float
) -> DrawingUnit | None:
    """Find the single mm/cm/m unit consistent with independently written area.

    Room polygons may include wall faces while schedules give net area, so this
    is a scale check with a 20% tolerance, not approval of the room boundary.
    """
    if selected_unit not in UNIT_TO_METRE or not math.isfinite(declared_to_geometric_ratio):
        return None
    if declared_to_geometric_ratio <= 0:
        return None
    matches = [
        candidate for candidate, candidate_scale in UNIT_TO_METRE.items()
        if 0.8 <= declared_to_geometric_ratio
        * (UNIT_TO_METRE[selected_unit] / candidate_scale) ** 2 <= 1.2
    ]
    return matches[0] if len(matches) == 1 else None


def resolve_unit(
    confirmed: DrawingUnit,
    detected: DrawingUnit,
) -> tuple[DrawingUnit, float]:
    chosen = confirmed if confirmed != DrawingUnit.UNKNOWN else detected
    return chosen, unit_scale(chosen)
