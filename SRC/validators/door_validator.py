# -*- coding: utf-8 -*-

from __future__ import annotations

from math import isfinite

from SRC.models.door import Door


class DoorValidator:

    def validate(self, doors: list[Door]) -> bool:

        door_count = 0
        zero_width = 0
        zero_height = 0
        invalid_rotation = 0
        missing_room_links = 0
        duplicate_room_links = 0
        exterior_door_count = 0
        interior_door_count = 0
        invalid_door_count = 0

        for door in doors:

            door_count += 1

            width = self._to_float(getattr(door, "width", 0.0))
            height = self._to_float(getattr(door, "height", 0.0))

            if width <= 0.0:
                zero_width += 1

            if height <= 0.0:
                zero_height += 1

            rotation_ok = self._is_valid_rotation(getattr(door, "rotation", None))

            if not rotation_ok:
                invalid_rotation += 1

            room_ids = getattr(door, "room_ids", [])

            if room_ids is None:
                room_ids = []

            if not isinstance(room_ids, list):
                room_ids = list(room_ids)

            if len(room_ids) == 0:
                missing_room_links += 1

            has_duplicate_links = len(room_ids) != len(set(room_ids))

            if has_duplicate_links:
                duplicate_room_links += 1

            if len(room_ids) == 1:
                exterior_door_count += 1
            elif len(room_ids) == 2:
                interior_door_count += 1

            door_is_valid = (
                width > 0.0
                and height > 0.0
                and rotation_ok
                and (not has_duplicate_links)
            )

            door.is_valid = door_is_valid

            if not door_is_valid:
                invalid_door_count += 1

        passed = (
            door_count > 0
            and zero_width == 0
            and zero_height == 0
            and invalid_rotation == 0
            and duplicate_room_links == 0
        )

        print("DOOR VALIDATOR")
        print()
        print(f"Door Count : {door_count}")
        print()
        print(f"Zero Width : {zero_width}")
        print()
        print(f"Zero Height : {zero_height}")
        print()
        print(f"Invalid Rotation : {invalid_rotation}")
        print()
        print(f"Missing Room Links : {missing_room_links}")
        print()
        print(f"Duplicate Room Links : {duplicate_room_links}")
        print()
        print(f"Exterior Door Count : {exterior_door_count}")
        print()
        print(f"Interior Door Count : {interior_door_count}")
        print()
        print(f"Invalid Door Count : {invalid_door_count}")
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
    def _is_valid_rotation(value) -> bool:

        try:
            rotation = float(value)
        except (TypeError, ValueError):
            return False

        return isfinite(rotation)
