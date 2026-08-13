"""
SRC/domain/floor.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .entity import Entity

if TYPE_CHECKING:
    
    from .wall import Wall
    from .slab import Slab
    from .column import Column
    from .beam import Beam
    from .shear_wall import ShearWall
    from .room import Room
    from ..architectural.door import Door
    from ..architectural.window import Window


@dataclass(slots=True)
class Floor(Entity):
    """
    Building floor.

    Examples
    --------
    - 2. Basement
    - 1. Basement
    - Ground Floor
    - 1st Floor
    - Roof Floor
    """

    level: int = 0

    elevation: float = 0.0

    height: float = 0.0

    rooms: list["Room"] = field(default_factory=list)

    walls: list["Wall"] = field(default_factory=list)

    slabs: list["Slab"] = field(default_factory=list)

    columns: list["Column"] = field(default_factory=list)

    beams: list["Beam"] = field(default_factory=list)

    shear_walls: list["ShearWall"] = field(default_factory=list)

    doors: list["Door"] = field(default_factory=list)

    windows: list["Window"] = field(default_factory=list)

    # ---------------------------------------------------------

    def add_room(self, room: "Room") -> None:

        if room not in self.rooms:
            self.rooms.append(room)
            self.touch()

    # ---------------------------------------------------------

    def add_wall(self, wall: "Wall") -> None:

        if wall not in self.walls:
            self.walls.append(wall)
            self.touch()

    # ---------------------------------------------------------

    def add_slab(self, slab: "Slab") -> None:

        if slab not in self.slabs:
            self.slabs.append(slab)
            self.touch()

    # ---------------------------------------------------------

    def add_column(self, column: "Column") -> None:

        if column not in self.columns:
            self.columns.append(column)
            self.touch()

    # ---------------------------------------------------------

    def add_beam(self, beam: "Beam") -> None:

        if beam not in self.beams:
            self.beams.append(beam)
            self.touch()

    # ---------------------------------------------------------

    def add_shear_wall(self, shear_wall: "ShearWall") -> None:

        if shear_wall not in self.shear_walls:
            self.shear_walls.append(shear_wall)
            self.touch()

    # ---------------------------------------------------------

    def add_door(self, door: "Door") -> None:

        if door not in self.doors:
            self.doors.append(door)
            self.touch()

    # ---------------------------------------------------------

    def add_window(self, window: "Window") -> None:

        if window not in self.windows:
            self.windows.append(window)
            self.touch()

    # ---------------------------------------------------------

    def clear(self) -> None:
        """
        Remove all floor objects.
        """

        self.rooms.clear()
        self.walls.clear()
        self.slabs.clear()
        self.columns.clear()
        self.beams.clear()
        self.shear_walls.clear()
        self.doors.clear()
        self.windows.clear()

        self.touch()