"""
SRC/domain/beam.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .entity import Entity

if TYPE_CHECKING:
    from .floor import Floor


@dataclass(slots=True)
class Beam(Entity):
    """
    Structural reinforced concrete beam.

    Betonarme kiriş elemanı.
    """

    floor: Floor | None = None

    geometry: object | None = None

    name: str = ""

    length: float = 0.0

    width: float = 0.0

    height: float = 0.0

    material: str = "C30"

    # ---------------------------------------------------------

    def set_floor(self, floor: Floor) -> None:
        """
        Assign beam to floor.
        """

        self.floor = floor
        self.touch()

    # ---------------------------------------------------------

    def set_dimensions(
        self,
        length: float,
        width: float,
        height: float,
    ) -> None:
        """
        Set beam dimensions.
        """

        self.length = length
        self.width = width
        self.height = height

        self.touch()

    # ---------------------------------------------------------

    @property
    def volume(self) -> float:
        """
        Approximate concrete volume.
        """

        return self.length * self.width * self.height