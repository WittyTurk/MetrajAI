"""
SRC/domain/shear_wall.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .entity import Entity

if TYPE_CHECKING:
    from .floor import Floor


@dataclass(slots=True)
class ShearWall(Entity):
    """
    Structural reinforced concrete shear wall.

    Betonarme perde elemanı.
    """

    floor: Floor | None = None

    geometry: object | None = None

    name: str = ""

    length: float = 0.0

    thickness: float = 0.0

    height: float = 0.0

    material: str = "C30"

    # ---------------------------------------------------------

    def set_floor(self, floor: Floor) -> None:
        """
        Assign shear wall to floor.
        """

        self.floor = floor
        self.touch()

    # ---------------------------------------------------------

    def set_dimensions(
        self,
        length: float,
        thickness: float,
        height: float,
    ) -> None:
        """
        Set shear wall dimensions.
        """

        self.length = length
        self.thickness = thickness
        self.height = height

        self.touch()

    # ---------------------------------------------------------

    @property
    def volume(self) -> float:
        """
        Approximate concrete volume.
        """

        return self.length * self.thickness * self.height