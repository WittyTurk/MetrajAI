"""
SRC/domain/slab.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .entity import Entity
from .enums import SlabType

if TYPE_CHECKING:
    from .floor import Floor


@dataclass(slots=True)
class Slab(Entity):
    """
    Structural slab element.

    Taşıyıcı döşeme, radye temel, çatı döşemesi
    ve teknik döşemeleri temsil eder.

    Metraj hesaplaması burada yapılmaz.
    Quantity Engine tarafından yapılacaktır.
    """

    floor: Floor | None = None

    slab_type: SlabType = SlabType.NORMAL_SLAB

    name: str = ""

    geometry: object | None = None

    area: float = 0.0

    thickness: float = 0.0

    elevation: float = 0.0

    # ---------------------------------------------------------

    def set_floor(self, floor: Floor) -> None:
        """
        Assign slab to floor.
        """

        self.floor = floor
        self.touch()

    # ---------------------------------------------------------

    def set_geometry(self, geometry: object) -> None:
        """
        Assign geometric representation.
        """

        self.geometry = geometry
        self.touch()

    # ---------------------------------------------------------

    def set_dimensions(
        self,
        area: float,
        thickness: float,
    ) -> None:
        """
        Set slab dimensions.
        """

        self.area = area
        self.thickness = thickness

        self.touch()

    # ---------------------------------------------------------

    @property
    def volume(self) -> float:
        """
        Concrete volume.

        Daha sonra Quantity Engine'e taşınabilir.
        """

        return self.area * self.thickness