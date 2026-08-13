"""
SRC/domain/room.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .entity import Entity

if TYPE_CHECKING:
    from .floor import Floor

    from ..architectural.wall_surface import WallSurface
    from ..architectural.floor_surface import FloorSurface
    from ..architectural.ceiling_surface import CeilingSurface


@dataclass(slots=True)
class Room(Entity):
    """
    Building room (space).

    Examples
    --------
    - Classroom
    - Office
    - WC
    - Corridor
    - Stair Hall
    """

    code: str = ""

    description: str = ""

    floor: Floor | None = None

    wall_surfaces: list["WallSurface"] = field(default_factory=list)

    floor_surface: "FloorSurface | None" = None

    ceiling_surface: "CeilingSurface | None" = None

    # ---------------------------------------------------------

    def add_wall_surface(self, surface: "WallSurface") -> None:
        """Add a wall surface to the room."""

        if surface is None:
            raise ValueError("surface is None")

        if surface not in self.wall_surfaces:
            self.wall_surfaces.append(surface)
            self.touch()

    # ---------------------------------------------------------

    def remove_wall_surface(self, surface: "WallSurface") -> None:
        """Remove a wall surface from the room."""

        if surface in self.wall_surfaces:
            self.wall_surfaces.remove(surface)
            self.touch()

    # ---------------------------------------------------------

    def clear_wall_surfaces(self) -> None:
        """Remove all wall surfaces."""

        self.wall_surfaces.clear()
        self.touch()

    # ---------------------------------------------------------

    def set_floor_surface(self, surface: "FloorSurface") -> None:
        """Assign floor surface."""

        self.floor_surface = surface
        self.touch()

    # ---------------------------------------------------------

    def set_ceiling_surface(self, surface: "CeilingSurface") -> None:
        """Assign ceiling surface."""

        self.ceiling_surface = surface
        self.touch()