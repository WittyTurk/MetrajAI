"""
SRC/domain/floor_surface.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .surface import Surface

if TYPE_CHECKING:
    from .room import Room


@dataclass(slots=True)
class FloorSurface(Surface):
    """
    Floor surface.

    Bir mahalin zemin kaplama yüzeyini temsil eder.

    Örnek:
        - Seramik zemin
        - Mermer zemin
        - Epoksi zemin
        - PVC zemin
    """

    room: Room | None = None

    level: float = 0.0

    # ---------------------------------------------------------

    def set_room(self, room: Room) -> None:
        """
        Assign room relation.
        """

        self.room = room
        self.touch()

    # ---------------------------------------------------------

    def set_level(self, level: float) -> None:
        """
        Set floor elevation.
        """

        self.level = level
        self.touch()