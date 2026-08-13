"""
SRC/domain/ceiling_surface.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .surface import Surface

if TYPE_CHECKING:
    from .room import Room


@dataclass(slots=True)
class CeilingSurface(Surface):
    """
    Ceiling surface.

    Bir mahallin tavan yüzeyini temsil eder.

    Örnek:
        - Plastik boya tavan
        - Alçı tavan
        - Asma tavan
    """

    room: Room | None = None

    elevation: float = 0.0

    # ---------------------------------------------------------

    def set_room(self, room: Room) -> None:
        """
        Assign room relation.
        """

        self.room = room
        self.touch()

    # ---------------------------------------------------------

    def set_elevation(self, elevation: float) -> None:
        """
        Set ceiling elevation.
        """

        self.elevation = elevation
        self.touch()