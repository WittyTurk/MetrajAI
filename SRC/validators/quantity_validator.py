# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.models.quantity_item import QuantityItem


class QuantityValidator:

    VALID_UNITS = {"m²", "m", "adet"}

    def validate(self, items: list[QuantityItem]) -> bool:

        quantity_item_count = 0
        negative_quantity = 0
        invalid_unit = 0
        missing_category = 0
        missing_description = 0
        missing_room_id = 0
        invalid_quantity_count = 0

        for item in items:

            quantity_item_count += 1

            quantity = self._to_float(getattr(item, "quantity", 0.0))

            if quantity < 0.0:
                negative_quantity += 1

            unit = self._to_text(getattr(item, "unit", None))
            category = self._to_text(getattr(item, "category", None))
            description = self._to_text(getattr(item, "description", None))
            room_id = getattr(item, "room_id", None)

            unit_ok = unit in self.VALID_UNITS
            category_ok = category is not None
            description_ok = description is not None
            room_id_ok = room_id is not None

            if not unit_ok:
                invalid_unit += 1

            if not category_ok:
                missing_category += 1

            if not description_ok:
                missing_description += 1

            if not room_id_ok:
                missing_room_id += 1

            item_is_valid = (
                quantity >= 0.0
                and unit_ok
                and category_ok
                and description_ok
                and room_id_ok
            )

            item.is_valid = item_is_valid

            if not item_is_valid:
                invalid_quantity_count += 1

        passed = (
            quantity_item_count > 0
            and negative_quantity == 0
            and invalid_unit == 0
            and missing_category == 0
            and missing_description == 0
            and missing_room_id == 0
        )

        print("QUANTITY VALIDATOR")
        print()
        print(f"Quantity Item Count : {quantity_item_count}")
        print()
        print(f"Negative Quantity : {negative_quantity}")
        print()
        print(f"Invalid Unit : {invalid_unit}")
        print()
        print(f"Missing Category : {missing_category}")
        print()
        print(f"Missing Description : {missing_description}")
        print()
        print(f"Missing Room Id : {missing_room_id}")
        print()
        print(f"Invalid Quantity Count : {invalid_quantity_count}")
        print()
        print(f"PASS / FAIL : {'PASS' if passed else 'FAIL'}")

        return passed

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

        return text
