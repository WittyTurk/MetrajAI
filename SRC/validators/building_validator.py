# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.models.building import Building


class BuildingValidator:

    def validate(self, building: Building) -> bool:

        building_count = 1

        room_count = len(building.room_ids)
        unique_wall_count = len(set(building.wall_ids))
        door_count = len(building.door_ids)
        window_count = len(building.window_ids)
        level_count = len(building.level_ids)
        is_valid = bool(building.is_valid)

        passed = (
            building_count == 1
            and room_count > 0
            and unique_wall_count > 0
            and is_valid is True
        )

        print("BUILDING VALIDATOR")
        print()
        print(f"Building Count : {building_count}")
        print()
        print(f"Room Count : {room_count}")
        print()
        print(f"Unique Wall Count : {unique_wall_count}")
        print()
        print(f"Door Count : {door_count}")
        print()
        print(f"Window Count : {window_count}")
        print()
        print(f"Level Count : {level_count}")
        print()
        print(f"Is Valid : {is_valid}")
        print()
        print(f"PASS / FAIL : {'PASS' if passed else 'FAIL'}")

        return passed
