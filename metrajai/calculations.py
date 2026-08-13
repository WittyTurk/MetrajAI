from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .contracts import (
    AnalysisWarning,
    Assumption,
    DetectedElement,
    Discipline,
    QuantityLine,
    ReviewStatus,
)


@dataclass(frozen=True)
class QuantityDefinition:
    category: str
    description: str
    unit: str
    formula: str
    required: tuple[str, ...]
    calculate: Callable[[dict[str, float]], float]
    optional: bool = False


DEFINITIONS: dict[str, tuple[QuantityDefinition, ...]] = {
    "column": (
        QuantityDefinition(
            "Beton",
            "Kolon betonu",
            "m³",
            "width_m * depth_m * height_m",
            ("width_m", "depth_m", "height_m"),
            lambda v: v["width_m"] * v["depth_m"] * v["height_m"],
        ),
        QuantityDefinition(
            "Kalıp",
            "Kolon yan kalıbı (brüt; birleşimler düşülmemiş)",
            "m²",
            "2 * (width_m + depth_m) * height_m",
            ("width_m", "depth_m", "height_m"),
            lambda v: 2 * (v["width_m"] + v["depth_m"]) * v["height_m"],
        ),
    ),
    "beam": (
        QuantityDefinition(
            "Beton",
            "Kiriş betonu (net açıklık, brüt kesit)",
            "m³",
            "width_m * height_m * length_m",
            ("width_m", "height_m", "length_m"),
            lambda v: v["width_m"] * v["height_m"] * v["length_m"],
        ),
        QuantityDefinition(
            "Kalıp",
            "Kiriş alt ve açık yan kalıbı",
            "m²",
            "formwork_area_m2",
            ("formwork_area_m2",),
            lambda v: v["formwork_area_m2"],
        ),
    ),
    "shear_wall": (
        QuantityDefinition(
            "Beton",
            "Perde betonu",
            "m³",
            "thickness_m * length_m * height_m",
            ("thickness_m", "length_m", "height_m"),
            lambda v: v["thickness_m"] * v["length_m"] * v["height_m"],
        ),
        QuantityDefinition(
            "Kalıp",
            "Perde kalıbı",
            "m²",
            "2 * length_m * height_m",
            ("length_m", "height_m"),
            lambda v: 2 * v["length_m"] * v["height_m"],
        ),
    ),
    "slab": (
        QuantityDefinition(
            "Beton",
            "Döşeme betonu",
            "m³",
            "area_m2 * thickness_m",
            ("area_m2", "thickness_m"),
            lambda v: v["area_m2"] * v["thickness_m"],
        ),
        QuantityDefinition(
            "Kalıp", "Döşeme altı kalıbı", "m²", "area_m2", ("area_m2",), lambda v: v["area_m2"]
        ),
    ),
    "raft": (
        QuantityDefinition(
            "Beton",
            "Radye temel betonu",
            "m³",
            "area_m2 * thickness_m",
            ("area_m2", "thickness_m"),
            lambda v: v["area_m2"] * v["thickness_m"],
        ),
        QuantityDefinition(
            "Kalıp",
            "Radye temel yan kalıbı",
            "m²",
            "perimeter_m * thickness_m",
            ("perimeter_m", "thickness_m"),
            lambda v: v["perimeter_m"] * v["thickness_m"],
        ),
    ),
    "foundation": (
        QuantityDefinition(
            "Beton",
            "Temel betonu",
            "m³",
            "area_m2 * thickness_m",
            ("area_m2", "thickness_m"),
            lambda v: v["area_m2"] * v["thickness_m"],
        ),
        QuantityDefinition(
            "Kalıp",
            "Temel yan kalıbı",
            "m²",
            "perimeter_m * thickness_m",
            ("perimeter_m", "thickness_m"),
            lambda v: v["perimeter_m"] * v["thickness_m"],
        ),
    ),
    "stair": (
        QuantityDefinition(
            "Beton",
            "Merdiven eğimli plak betonu",
            "m³",
            "plan_area_m2 * sqrt(1 + (total_rise_m / horizontal_run_m)^2) * waist_thickness_m",
            ("plan_area_m2", "horizontal_run_m", "total_rise_m", "waist_thickness_m"),
            lambda v: (
                v["plan_area_m2"]
                * (1 + (v["total_rise_m"] / v["horizontal_run_m"]) ** 2) ** 0.5
                * v["waist_thickness_m"]
            ),
        ),
        QuantityDefinition(
            "Beton",
            "Merdiven basamak betonu",
            "m³",
            "step_volume_m3",
            ("step_volume_m3",),
            lambda v: v["step_volume_m3"],
            optional=True,
        ),
        QuantityDefinition(
            "Beton",
            "Merdiven sahanlık betonu",
            "m³",
            "landing_volume_m3",
            ("landing_volume_m3",),
            lambda v: v["landing_volume_m3"],
            optional=True,
        ),
        QuantityDefinition(
            "Kalıp",
            "Merdiven yan kalıbı",
            "m²",
            "side_formwork_m2",
            ("side_formwork_m2",),
            lambda v: v["side_formwork_m2"],
            optional=True,
        ),
        QuantityDefinition(
            "Kalıp",
            "Merdiven rıht kalıbı",
            "m²",
            "riser_formwork_m2",
            ("riser_formwork_m2",),
            lambda v: v["riser_formwork_m2"],
            optional=True,
        ),
        QuantityDefinition(
            "Kalıp",
            "Merdiven sahanlık alt kalıbı",
            "m²",
            "landing_formwork_m2",
            ("landing_formwork_m2",),
            lambda v: v["landing_formwork_m2"],
            optional=True,
        ),
        QuantityDefinition(
            "Kalıp",
            "Merdiven eğimli alt kalıbı",
            "m²",
            "plan_area_m2 * sqrt(1 + (total_rise_m / horizontal_run_m)^2)",
            ("plan_area_m2", "horizontal_run_m", "total_rise_m"),
            lambda v: (
                v["plan_area_m2"] * (1 + (v["total_rise_m"] / v["horizontal_run_m"]) ** 2) ** 0.5
            ),
        ),
    ),
    "rebar": (
        QuantityDefinition(
            "Donatı",
            "Net donatı",
            "kg",
            "length_m * count * diameter_mm^2 / 162",
            ("length_m", "count", "diameter_mm"),
            lambda v: v["length_m"] * v["count"] * v["diameter_mm"] ** 2 / 162,
        ),
    ),
    "wall": (
        QuantityDefinition(
            "Mimari", "Duvar uzunluğu", "m", "length_m", ("length_m",), lambda v: v["length_m"]
        ),
        QuantityDefinition(
            "Mimari",
            "Duvar yüzeyi (tek yüz)",
            "m²",
            "length_m * height_m",
            ("length_m", "height_m"),
            lambda v: v["length_m"] * v["height_m"],
        ),
    ),
    "door": (
        QuantityDefinition(
            "Mimari", "Kapı adedi", "adet", "count", ("count",), lambda v: v["count"]
        ),
    ),
    "window": (
        QuantityDefinition(
            "Mimari", "Pencere adedi", "adet", "count", ("count",), lambda v: v["count"]
        ),
    ),
    "room": (
        QuantityDefinition(
            "Mimari", "Net döşeme alanı", "m²", "area_m2", ("area_m2",), lambda v: v["area_m2"]
        ),
        QuantityDefinition(
            "Mimari", "Tavan alanı", "m²", "area_m2", ("area_m2",), lambda v: v["area_m2"]
        ),
        QuantityDefinition(
            "Mimari",
            "Mahal çevresi",
            "m",
            "perimeter_m",
            ("perimeter_m",),
            lambda v: v["perimeter_m"],
            optional=True,
        ),
    ),
}


def derive_element_measurements(element: DetectedElement) -> None:
    """Derive only formulaic values from already explicit measurements."""
    values = element.measurements
    if element.element_type == "stair":
        step_inputs = ("stair_width_m", "tread_m", "riser_m", "step_count")
        if all(values.get(key, 0) > 0 for key in step_inputs):
            values["step_volume_m3"] = round(
                0.5
                * values["stair_width_m"]
                * values["tread_m"]
                * values["riser_m"]
                * values["step_count"],
                6,
            )
            values["riser_formwork_m2"] = round(
                values["stair_width_m"] * values["riser_m"] * values["step_count"],
                6,
            )
        side_inputs = ("horizontal_run_m", "total_rise_m", "waist_thickness_m")
        if all(values.get(key, 0) > 0 for key in side_inputs):
            values["side_formwork_m2"] = round(
                2
                * math.hypot(values["horizontal_run_m"], values["total_rise_m"])
                * values["waist_thickness_m"],
                6,
            )


def _value_of(key: str) -> Callable[[dict[str, float]], float]:
    def calculate(values: dict[str, float]) -> float:
        return values[key]

    return calculate


for element_type, category, description, unit, variable in (
    ("landscape_area", "Peyzaj", "Peyzaj alanı", "m²", "area_m2"),
    ("finish_area", "Mimari", "Kaplama alanı", "m²", "area_m2"),
    ("landscape_linear", "Peyzaj", "Bordür/hat uzunluğu", "m", "length_m"),
    ("landscape_item", "Peyzaj", "Bitki/ekipman adedi", "adet", "count"),
    ("pipe", "Mekanik", "Boru merkez hattı", "m", "length_m"),
    ("duct", "Mekanik", "Kanal merkez hattı", "m", "length_m"),
    ("mechanical_equipment", "Mekanik", "Mekanik cihaz adedi", "adet", "count"),
    ("cable", "Elektrik", "Kablo güzergâhı", "m", "length_m"),
    ("cable_tray", "Elektrik", "Kablo tavası", "m", "length_m"),
    ("light", "Elektrik", "Armatür adedi", "adet", "count"),
    ("socket", "Elektrik", "Priz adedi", "adet", "count"),
    ("panel", "Elektrik", "Pano adedi", "adet", "count"),
    ("electrical_item", "Elektrik", "Elektrik ekipmanı adedi", "adet", "count"),
    ("mechanical_fitting", "Mekanik", "Fittings adedi", "adet", "count"),
):
    DEFINITIONS[element_type] = (
        QuantityDefinition(
            category,
            description,
            unit,
            variable,
            (variable,),
            _value_of(variable),
        ),
    )


def _approved_assumptions(assumptions: Iterable[Assumption]) -> dict[str, Assumption]:
    return {item.key: item for item in assumptions if item.approved}


def calculate_quantities(
    elements: Iterable[DetectedElement],
    assumptions: Iterable[Assumption] = (),
    blocked_disciplines: set[Discipline] | None = None,
) -> tuple[list[QuantityLine], list[AnalysisWarning]]:
    """Calculate only engineer-accepted elements; never substitute missing dimensions."""
    approved = _approved_assumptions(assumptions)
    quantities: list[QuantityLine] = []
    warnings: list[AnalysisWarning] = []
    locked = blocked_disciplines or set()
    for element in elements:
        if element.review_status != ReviewStatus.ACCEPTED:
            continue
        if element.discipline in locked:
            warnings.append(
                AnalysisWarning(
                    code="DISCIPLINE_RELIABILITY_GATE_LOCKED",
                    message=(
                        f"{element.discipline.value} disiplini gerçek küçük ve karmaşık "
                        "proje doğrulamasını tamamlamadığı için kesin metraj kilitli."
                    ),
                    source_id=element.source_id,
                    element_id=element.id,
                    severity="error",
                )
            )
            continue
        definitions = DEFINITIONS.get(element.element_type)
        if not definitions:
            warnings.append(
                AnalysisWarning(
                    code="UNSUPPORTED_ACCEPTED_ELEMENT",
                    message=f"Accepted element type has no quantity policy: {element.element_type}",
                    source_id=element.source_id,
                    element_id=element.id,
                    severity="error",
                )
            )
            continue
        for index, definition in enumerate(definitions):
            missing = [
                key
                for key in definition.required
                if key not in element.measurements or element.measurements[key] <= 0
            ]
            if missing:
                if definition.optional:
                    continue
                warnings.append(
                    AnalysisWarning(
                        code="ACCEPTED_ELEMENT_MISSING_INPUT",
                        message=f"{element.id}: missing {', '.join(missing)}; quantity excluded.",
                        source_id=element.source_id,
                        element_id=element.id,
                        severity="error",
                    )
                )
                continue
            variables = {key: float(element.measurements[key]) for key in definition.required}
            quantity = definition.calculate(variables)
            quantities.append(
                QuantityLine(
                    id=f"qty_{element.id.removeprefix('elm_')}_{index}",
                    element_id=element.id,
                    source_id=element.source_id,
                    discipline=element.discipline,
                    floor=element.floor,
                    category=definition.category,
                    description=definition.description,
                    unit=definition.unit,
                    quantity=quantity,
                    formula=definition.formula,
                    formula_key=f"{element.element_type}:{index}",
                    variables=variables,
                    assumption_ids=[],
                    review_status=element.review_status,
                )
            )

        if element.element_type == "rebar":
            _append_rebar_additions(element, approved, quantities)
    return quantities, warnings


def _append_rebar_additions(
    element: DetectedElement,
    assumptions: dict[str, Assumption],
    quantities: list[QuantityLine],
) -> None:
    base = next((line for line in reversed(quantities) if line.element_id == element.id), None)
    if base is None:
        return
    additions = (
        ("rebar_lap_percent", "Bindirme ilavesi", 1),
        ("rebar_hook_percent", "Kanca ilavesi", 2),
        ("rebar_waste_percent", "Fire ilavesi", 3),
    )
    for key, description, index in additions:
        assumption = assumptions.get(key)
        if assumption is None or not isinstance(assumption.value, (int, float)):
            continue
        percent = float(assumption.value)
        if percent <= 0:
            continue
        quantities.append(
            QuantityLine(
                id=f"qty_{element.id.removeprefix('elm_')}_{index}",
                element_id=element.id,
                source_id=element.source_id,
                discipline=element.discipline,
                floor=element.floor,
                category="Donatı",
                description=description,
                unit="kg",
                quantity=base.quantity * percent / 100,
                formula=f"net_rebar_kg * {key} / 100",
                formula_key=f"rebar:{index}",
                variables={"net_rebar_kg": base.quantity, key: percent},
                assumption_ids=[assumption.id],
                review_status=element.review_status,
            )
        )
