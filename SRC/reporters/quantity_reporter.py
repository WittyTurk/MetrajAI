# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field

from SRC.models.quantity_item import QuantityItem


@dataclass(slots=True)
class QuantityReport:

    item_count: int

    floor_area_total: float
    ceiling_area_total: float
    wall_area_total: float
    door_count_total: float
    window_count_total: float

    category_summary: dict[str, float] = field(default_factory=dict)
    unit_summary: dict[str, float] = field(default_factory=dict)


class QuantityReporter:

    CATEGORIES = ("floor", "ceiling", "wall", "door", "window")
    UNITS = ("m²", "m", "adet")

    def generate(self, items: list[QuantityItem]) -> QuantityReport:

        category_summary = {category: 0.0 for category in self.CATEGORIES}
        unit_summary = {unit: 0.0 for unit in self.UNITS}

        for item in items:

            quantity = self._to_float(getattr(item, "quantity", 0.0))
            category = self._to_text(getattr(item, "category", None))
            unit = self._to_text(getattr(item, "unit", None))

            if category in category_summary:
                category_summary[category] += quantity

            if unit in unit_summary:
                unit_summary[unit] += quantity

        report = QuantityReport(
            item_count=len(items),
            floor_area_total=category_summary["floor"],
            ceiling_area_total=category_summary["ceiling"],
            wall_area_total=category_summary["wall"],
            door_count_total=category_summary["door"],
            window_count_total=category_summary["window"],
            category_summary=category_summary,
            unit_summary=unit_summary,
        )

        self._print_report(report)

        return report

    # -------------------------------------------------

    def _print_report(self, report: QuantityReport) -> None:

        print("QUANTITY REPORT")
        print()
        print("-" * 40)
        print()
        print(f"Item Count : {report.item_count}")
        print()
        print(f"Floor Area Total : {report.floor_area_total:.4f}")
        print()
        print(f"Ceiling Area Total : {report.ceiling_area_total:.4f}")
        print()
        print(f"Wall Area Total : {report.wall_area_total:.4f}")
        print()
        print(f"Door Count Total : {report.door_count_total:.4f}")
        print()
        print(f"Window Count Total : {report.window_count_total:.4f}")
        print()
        print("-" * 40)
        print()
        print("Category Summary")
        print()
        print(f"floor : {report.category_summary['floor']:.4f}")
        print()
        print(f"ceiling : {report.category_summary['ceiling']:.4f}")
        print()
        print(f"wall : {report.category_summary['wall']:.4f}")
        print()
        print(f"door : {report.category_summary['door']:.4f}")
        print()
        print(f"window : {report.category_summary['window']:.4f}")
        print()
        print("-" * 40)
        print()
        print("Unit Summary")
        print()
        print(f"m² : {report.unit_summary['m²']:.4f}")
        print()
        print(f"m : {report.unit_summary['m']:.4f}")
        print()
        print(f"adet : {report.unit_summary['adet']:.4f}")
        print()
        print("-" * 40)
        print()
        print("END REPORT")

    # -------------------------------------------------

    @staticmethod
    def _to_float(value) -> float:

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    # -------------------------------------------------

    @staticmethod
    def _to_text(value) -> str | None:

        if value is None:
            return None

        text = str(value).strip()

        if text == "":
            return None

        return text.lower()
