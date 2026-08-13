# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.models.cost_item import CostItem
from SRC.models.quantity_item import QuantityItem


class CostCalculator:

    def calculate(
        self,
        quantity_items: list[QuantityItem],
        price_book: dict[tuple[str, str], float],
        price_book_name: str | None = None,
        price_year: int | None = None,
    ) -> list[CostItem]:

        items: list[CostItem] = []

        for index, quantity_item in enumerate(quantity_items, start=1):

            category = self._to_text(getattr(quantity_item, "category", ""))
            description = self._to_text(getattr(quantity_item, "description", ""))
            unit = self._to_text(getattr(quantity_item, "unit", ""))
            quantity = self._to_float(getattr(quantity_item, "quantity", 0.0))

            key = (category, unit)

            if key in price_book:
                unit_price = self._to_float(price_book[key])
            else:
                unit_price = 0.0

            total_cost = quantity * unit_price

            item = CostItem(
                id=index,
                quantity_item_id=quantity_item.id,
                category=category,
                description=description,
                unit=unit,
                quantity=quantity,
                unit_price=unit_price,
                total_cost=total_cost,
                price_book=price_book_name,
                price_year=price_year,
                properties={},
                is_valid=True,
            )

            items.append(item)

        return items

    # -------------------------------------------------

    @staticmethod
    def _to_text(value) -> str:

        if value is None:
            return ""

        return str(value).strip()

    # -------------------------------------------------

    @staticmethod
    def _to_float(value) -> float:

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
