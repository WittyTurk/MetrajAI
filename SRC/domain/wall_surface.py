"""
SRC/architectural/wall_surface.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..domain.surface import Surface

if TYPE_CHECKING:
    from ..domain.room import Room


@dataclass(slots=True)
class WallSurface(Surface):
    """
    Architectural wall surface.

    Bir duvarın tek yüzünü temsil eder.

    Örnek:
        - Koridor tarafı duvar yüzeyi
        - Oda tarafı duvar yüzeyi
        - Seramik kaplı yüzey
        - Boyalı yüzey
    """

    room: Room | None = None

    side: str = ""

    # ---------------------------------------------------------

    def set_room(self, room: Room) -> None:
        """
        Assign room relation.
        """

        self.room = room
        self.touch()

    # ---------------------------------------------------------

    def set_side(self, side: str) -> None:
        """
        Define surface side information.

        Örnek:
            "inside"
            "outside"
            "corridor"
            "room"
        """

        self.side = side
        self.touch()