"""
Geometry3

Cost Reporter V1

Pure Reporter
"""

from __future__ import annotations

from dataclasses import dataclass

from SRC.models.cost_item import CostItem


@dataclass(slots=True)
class CostReport:
    item_count: int = 0

    total_cost: float = 0.0

    category_summary: dict[str, float] | None = None
    unit_summary: dict[str, float] | None = None


class CostReporter:
    """
    Pure Reporter

    Entity değiştirmez.

    Sadece rapor üretir.
    """

    def generate(self, items: list[CostItem]) -> CostReport:

        report = CostReport(
            category_summary={},
            unit_summary={}
        )

        for item in items:

            report.item_count += 1
            report.total_cost += item.total_cost

            report.category_summary[item.category] = (
                report.category_summary.get(item.category, 0.0)
                + item.total_cost
            )

            report.unit_summary[item.unit] = (
                report.unit_summary.get(item.unit, 0.0)
                + item.total_cost
            )

        print()
        print("========== COST REPORT ==========")
        print(f"Item Count : {report.item_count}")
        print(f"Total Cost : {report.total_cost:.2f}")
        print()

        print("Category Summary")
        for category, total in report.category_summary.items():
            print(f"  {category:15} {total:.2f}")

        print()

        print("Unit Summary")
        for unit, total in report.unit_summary.items():
            print(f"  {unit:8} {total:.2f}")

        print("=================================")

        return report