# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.models.room import Room


class RoomValidator:

    def validate(self, rooms: list[Room]) -> bool:

        room_count = len(rooms)

        invalid_polygon = 0
        zero_area = 0
        negative_area = 0

        total_area = 0.0
        total_perimeter = 0.0

        for room in rooms:

            polygon = getattr(room, "polygon", None)

            if not self.is_valid_polygon(polygon):
                invalid_polygon += 1

            area = self.to_float(getattr(room, "area", 0.0))
            perimeter = self.to_float(getattr(room, "perimeter", 0.0))

            if area == 0.0:
                zero_area += 1

            if area < 0.0:
                negative_area += 1

            total_area += area
            total_perimeter += perimeter

        if room_count == 0:
            average_area = 0.0
            average_perimeter = 0.0
        else:
            average_area = total_area / room_count
            average_perimeter = total_perimeter / room_count

        passed = (
            room_count > 0
            and zero_area == 0
            and negative_area == 0
            and invalid_polygon == 0
        )

        print("ROOM VALIDATOR")
        print()
        print(f"Room Count : {room_count}")
        print()
        print(f"Invalid Polygon : {invalid_polygon}")
        print()
        print(f"Zero Area : {zero_area}")
        print()
        print(f"Negative Area : {negative_area}")
        print()
        print(f"Average Area : {average_area:.4f}")
        print()
        print(f"Average Perimeter : {average_perimeter:.4f}")
        print()
        print(f"PASS / FAIL : {'PASS' if passed else 'FAIL'}")

        return passed

    # -------------------------------------------------

    @staticmethod
    def to_float(value) -> float:

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    # -------------------------------------------------

    @staticmethod
    def is_valid_polygon(polygon) -> bool:

        if polygon is None:
            return False

        points = getattr(polygon, "points", None)

        if points is None:
            points = getattr(polygon, "corners", None)

        if points is None:
            points = getattr(polygon, "vertices", None)

        if points is None:
            return True

        return len(points) >= 3
