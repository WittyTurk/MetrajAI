"""
------------------------------------------------------------
MetrajAI

Project Domain Entity

Bir mühendislik projesini temsil eder.

Örnek:
    - YIĞMATEPE TAZİYE EVİ
    - 24 Derslik İlkokul
    - Hükümet Konağı

Project, Domain katmanının Aggregate Root nesnesidir.

------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .entity import Entity

if TYPE_CHECKING:
    from .building import Building


@dataclass(slots=True)
class Project(Entity):
    """
    Engineering Project.

    Notes
    -----
    Bir Project;

    * Bir veya daha fazla Building içerir.
    * Proje dokümanlarını tutar.
    * Genel ayarları saklar.
    * Building nesnelerinin sahibidir.
    """

    location: str = ""

    employer: str = ""

    contractor: str = ""

    description: str = ""

    buildings: list["Building"] = field(default_factory=list)

    documents: list["Document"] = field(default_factory=list)

    settings: dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------------------

    def add_building(self, building: "Building") -> None:
        """
        Add building.
        """

        if self.get_building(building.name) is None:
            self.buildings.append(building)
            self.touch()

    # ---------------------------------------------------------

    def remove_building(self, building: "Building") -> None:
        """
        Remove building.
        """

        if building in self.buildings:
            self.buildings.remove(building)
            self.touch()

    # ---------------------------------------------------------

    def clear_buildings(self) -> None:
        """
        Remove all buildings.
        """

        self.buildings.clear()
        self.touch()

    # ---------------------------------------------------------

    @property
    def building_count(self) -> int:
        """
        Number of buildings.
        """

        return len(self.buildings)

    # ---------------------------------------------------------

    def get_building(self, name: str) -> Building | None:
        """
        Find building by name.
        """

        for building in self.buildings:
            if building.name == name:
                return building

        return None

    # ---------------------------------------------------------

    def add_document(self, filename: str) -> None:
        """
        Add document.
        """

        if filename not in self.documents:
            self.documents.append(filename)
            self.touch()

    # ---------------------------------------------------------

    def remove_document(self, filename: str) -> None:
        """
        Remove document.
        """

        if filename in self.documents:
            self.documents.remove(filename)
            self.touch()

    # ---------------------------------------------------------

    @property
    def document_count(self) -> int:
        """
        Number of documents.
        """

        return len(self.documents)

    # ---------------------------------------------------------

    def set_setting(self, key: str, value: Any) -> None:
        """
        Store project setting.
        """

        self.settings[key] = value
        self.touch()

    # ---------------------------------------------------------

    def get_setting(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Read project setting.
        """

        return self.settings.get(key, default)

    # ---------------------------------------------------------

    @property
    def floor_count(self) -> int:
        """
        Total floors.
        """

        return sum(
            building.floor_count()
            for building in self.buildings
        )

    # ---------------------------------------------------------

    @property
    def room_count(self) -> int:
        """
        Total rooms.
        """

        return sum(
            building.room_count
            for building in self.buildings
        )

    # ---------------------------------------------------------

    @property
    def wall_count(self) -> int:
        """
        Total walls.
        """

        return sum(
            building.wall_count
            for building in self.buildings
        )

    # ---------------------------------------------------------

    @property
    def column_count(self) -> int:
        """
        Total columns.
        """

        return sum(
            building.column_count
            for building in self.buildings
        )

    # ---------------------------------------------------------

    @property
    def door_count(self) -> int:
        """
        Total doors.
        """

        return sum(
            building.door_count
            for building in self.buildings
        )

    # ---------------------------------------------------------

    @property
    def window_count(self) -> int:
        """
        Total windows.
        """

        return sum(
            building.window_count
            for building in self.buildings
        )

    # ---------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize project.
        """

        data = super().to_dict()

        data.update(
            {
                "location": self.location,
                "employer": self.employer,
                "contractor": self.contractor,
                "description": self.description,
                "building_count": self.building_count,
                "document_count": self.document_count,
                "floor_count": self.floor_count,
                "room_count": self.room_count,
                "wall_count": self.wall_count,
                "column_count": self.column_count,
                "door_count": self.door_count,
                "window_count": self.window_count,
                "documents": list(self.documents),
                "settings": dict(self.settings),
                "buildings": [
                    building.to_dict()
                    for building in self.buildings
                ],
            }
        )

        return data

    # ---------------------------------------------------------

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "Project":
        """
        Deserialize project.

        Notes
        -----
        Building nesneleri daha sonra Reader tarafından
        oluşturulacaktır.
        """

        project = cls()

        project.id = data.get("id", 0)
        project.guid = data.get("guid", project.guid)
        project.name = data.get("name", "")

        project.location = data.get("location", "")
        project.employer = data.get("employer", "")
        project.contractor = data.get("contractor", "")
        project.description = data.get("description", "")

        project.properties = data.get("properties", {})
        project.metadata = data.get("metadata", {})

        project.documents = data.get("documents", [])
        project.settings = data.get("settings", {})

        return project