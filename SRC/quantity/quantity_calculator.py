# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.models.building import Building
from SRC.models.door import Door
from SRC.models.quantity_item import QuantityItem
from SRC.models.room import Room
from SRC.models.window import Window


class QuantityCalculator:

    WALL_HEIGHT = 3.00

    def calculate(
        self,
        building: Building,
        rooms: list[Room],
        doors: list[Door],
        windows: list[Window],
    ) -> list[QuantityItem]:

        _ = building
        _ = doors
        _ = windows

        items: list[QuantityItem] = []

        for room in rooms:

            room_area = self._to_non_negative_float(getattr(room, "area", 0.0))
            room_perimeter = self._to_non_negative_float(getattr(room, "perimeter", 0.0))
            door_count = float(len(getattr(room, "door_ids", [])))
            window_count = float(len(getattr(room, "window_ids", [])))

            items.append(
                self._new_item(
                    item_id=len(items) + 1,
                    room_id=room.id,
                    category="floor",
                    description="Floor Area",
                    quantity=room_area,
                    unit="m²",
                )
            )

            items.append(
                self._new_item(
                    item_id=len(items) + 1,
                    room_id=room.id,
                    category="ceiling",
                    description="Ceiling Area",
                    quantity=room_area,
                    unit="m²",
                )
            )

            items.append(
                self._new_item(
                    item_id=len(items) + 1,
                    room_id=room.id,
                    category="wall",
                    description="Wall Area",
                    quantity=room_perimeter * self.WALL_HEIGHT,
                    unit="m²",
                )
            )

            items.append(
                self._new_item(
                    item_id=len(items) + 1,
                    room_id=room.id,
                    category="door",
                    description="Door Count",
                    quantity=door_count,
                    unit="adet",
                )
            )

            items.append(
                self._new_item(
                    item_id=len(items) + 1,
                    room_id=room.id,
                    category="window",
                    description="Window Count",
                    quantity=window_count,
                    unit="adet",
                )
            )

        return items

    # -------------------------------------------------

    @staticmethod
    def _new_item(
        item_id: int,
        room_id: int,
        category: str,
        description: str,
        quantity: float,
        unit: str,
    ) -> QuantityItem:

        return QuantityItem(
            id=item_id,
            room_id=room_id,
            wall_id=None,
            door_id=None,
            window_id=None,
            category=category,
            description=description,
            quantity=quantity,
            unit=unit,
            properties={},
            is_valid=True,
        )

    # -------------------------------------------------

    @staticmethod
    def _to_non_negative_float(value) -> float:

        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0

        if number < 0.0:
            return 0.0

        return number
