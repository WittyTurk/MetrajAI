"""
SRC/domain/building.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .entity import Entity
from .enums import BuildingType

if TYPE_CHECKING:
    from .floor import Floor


@dataclass(slots=True)
class Building(Entity):
    """
    Building domain entity.

    Bir projedeki tek bir binayı temsil eder.

    Örnek:
        - A Blok
        - B Blok
        - Ana Bina
        - İdari Bina

    Building yalnızca katları yönetir.
    Metraj hesabı yapmaz.
    """

    code: str = ""

    description: str = ""

    building_type: BuildingType = BuildingType.UNKNOWN

    floors: list["Floor"] = field(default_factory=list)

    # -----------------------------------------------------

    def add_floor(self, floor: "Floor") -> None:
        """Kat ekle."""

        if floor is None:
            raise ValueError("floor is None")

        if floor not in self.floors:
            self.floors.append(floor)
            self.touch()

    # -----------------------------------------------------

    def remove_floor(self, floor: "Floor") -> None:
        """Kat sil."""

        if floor in self.floors:
            self.floors.remove(floor)
            self.touch()

    # -----------------------------------------------------

    def clear_floors(self) -> None:
        """Tüm katları sil."""

        self.floors.clear()
        self.touch()

    # -----------------------------------------------------

    def get_floor(self, name: str) -> "Floor | None":
        """İsme göre kat bul."""

        for floor in self.floors:
            if floor.name == name:
                return floor

        return None

    # -----------------------------------------------------

    @property
    def floor_count(self) -> int:
        """Kat sayısı."""

        return len(self.floors)