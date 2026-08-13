# -*- coding: utf-8 -*-

from __future__ import annotations

from math import isfinite
from typing import Any

from SRC.models.mahal import Mahal
from SRC.models.room import Room


class RoomMahalMatcher:

    def __init__(self, area_tolerance: float = 0.5):

        self.area_tolerance = float(area_tolerance)

    # -------------------------------------------------

    def match(self, rooms: list[Room], mahals: list[Mahal]) -> list[dict[str, Any]]:

        conflicts: list[dict[str, Any]] = []

        for room in rooms:

            # Matcher owns only semantic relation fields on Room.
            room.mahal_no = None
            room.mahal_name = None

            room_area = self._to_valid_area(getattr(room, "area", None))

            if room_area is None:
                conflicts.append(
                    self._build_conflict(
                        room_id=room.id,
                        room_area=getattr(room, "area", None),
                        candidates=[],
                        reason="missing_area",
                    )
                )
                continue

            area_candidates = self._area_candidates(room_area, mahals)

            candidates = self._prioritize_by_level_name(area_candidates)

            if len(candidates) == 0:
                conflicts.append(
                    self._build_conflict(
                        room_id=room.id,
                        room_area=room_area,
                        candidates=candidates,
                        reason="no_candidate",
                    )
                )
                continue

            if len(candidates) == 1:
                selected = candidates[0]
                room.mahal_no = selected.mahal_no
                room.mahal_name = selected.mahal_name
                continue

            conflicts.append(
                self._build_conflict(
                    room_id=room.id,
                    room_area=room_area,
                    candidates=candidates,
                    reason="multiple_candidates",
                )
            )

        return conflicts

    # -------------------------------------------------

    def _area_candidates(self, room_area: float, mahals: list[Mahal]) -> list[Mahal]:

        candidates: list[Mahal] = []

        for mahal in mahals:

            expected_area = self._to_valid_area(getattr(mahal, "expected_area", None))

            if expected_area is None:
                continue

            if abs(room_area - expected_area) <= self.area_tolerance:
                candidates.append(mahal)

        return candidates

    # -------------------------------------------------

    @staticmethod
    def _prioritize_by_level_name(candidates: list[Mahal]) -> list[Mahal]:

        with_level_name: list[Mahal] = []

        for mahal in candidates:
            level_name = getattr(mahal, "level_name", None)

            if level_name is None:
                continue

            if str(level_name).strip() == "":
                continue

            with_level_name.append(mahal)

        if with_level_name:
            return with_level_name

        return candidates

    # -------------------------------------------------

    @staticmethod
    def _to_valid_area(value) -> float | None:

        if value is None:
            return None

        try:
            area = float(value)
        except (TypeError, ValueError):
            return None

        if not isfinite(area):
            return None

        return area

    # -------------------------------------------------

    @staticmethod
    def _build_conflict(
        room_id: int,
        room_area,
        candidates: list[Mahal],
        reason: str,
    ) -> dict[str, Any]:

        return {
            "room_id": room_id,
            "room_area": room_area,
            "candidate_mahal_ids": [mahal.id for mahal in candidates],
            "candidate_mahal_nos": [mahal.mahal_no for mahal in candidates],
            "reason": reason,
        }
