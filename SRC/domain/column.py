"""
SRC/domain/column.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .entity import Entity

if TYPE_CHECKING:
    from .floor import Floor


@dataclass(slots=True)
class Column(Entity):
    """
    Structural reinforced concrete column.

    Betonarme kolon elemanı.
    """

    floor: Floor | None = None

    geometry: object | None = None

    name: str = ""

    section_width: float = 0.0

    section_depth: float = 0.0

    height: float = 0.0

    material: str = "C30"

    # ---------------------------------------------------------

    def set_floor(self, floor: Floor) -> None:
        """
        Assign column to floor.
        """

        self.floor = floor
        self.touch()

    # ---------------------------------------------------------

    def set_section(
        self,
        width: float,
        depth: float,
    ) -> None:
        """
        Set column cross section.
        """

        self.section_width = width
        self.section_depth = depth

        self.touch()

    # ---------------------------------------------------------

    @property
    def cross_section_area(self) -> float:
        """
        Column cross section area.
        """

        return self.section_width * self.section_depth

    # ---------------------------------------------------------

    @property
    def volume(self) -> float:
        """
        Approximate concrete volume.

        Quantity Engine tarafında geliştirilecektir.
        """

        return self.cross_section_area * self.height