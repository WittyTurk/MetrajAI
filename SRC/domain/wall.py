"""
SRC/architectural/wall.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..domain.entity import Entity

if TYPE_CHECKING:
    from ..domain.floor import Floor
    from ..domain.room import Room

    from .wall_surface import WallSurface


@dataclass(slots=True)
class Wall(Entity):
    """
    Architectural wall.
    """

    code: str = ""

    description: str = ""

    floor: Floor | None = None

    start_room: Room | None = None

    end_room: Room | None = None

    surface_a: WallSurface | None = None

    surface_b: WallSurface | None = None

    thickness: float = 0.0

    height: float = 0.0

    geometry: object | None = None

    # ---------------------------------------------------------

    def set_surface_a(self, surface: WallSurface) -> None:
        """Assign first wall surface."""

        self.surface_a = surface
        self.touch()

    # ---------------------------------------------------------

    def set_surface_b(self, surface: WallSurface) -> None:
        """Assign second wall surface."""

        self.surface_b = surface
        self.touch()

    # ---------------------------------------------------------

    @property
    def rooms(self) -> tuple[Room | None, Room | None]:
        """Return adjacent rooms."""

        return self.start_room, self.end_room