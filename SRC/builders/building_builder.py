# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.models.building import Building
from SRC.models.room import Room


class BuildingBuilder:

    def __init__(self, rooms: list[Room]):

        self.rooms = rooms

    # -------------------------------------------------

    def build(self) -> Building:

        building = Building(
            id=1,
            name=None,
        )

        unique_wall_ids: set[int] = set()

        for room in self.rooms:

            building.room_ids.append(room.id)

            for wall_id in room.boundary_wall_ids:

                if wall_id in unique_wall_ids:
                    continue

                unique_wall_ids.add(wall_id)
                building.wall_ids.append(wall_id)

        building.door_ids = []
        building.window_ids = []
        building.level_ids = []
        building.properties = {}
        building.is_valid = True

        return building
