"""
MetrajAI
Building Entity Base Class

Bu modüldeki Entity sınıfı, Building Model içindeki tüm nesnelerin
ortak temel sınıfıdır.

Türeyecek sınıflar:

    Project
    Building
    Floor
    Grid
    Room
    Wall
    Column
    Beam
    Slab
    Door
    Window
    Roof
    Foundation

Bu sınıf geometri içermez.
DXF bilmez.
Geometry3 bilmez.
Metraj hesabı yapmaz.

Sadece ortak kimlik ve metadata bilgisini tutar.
"""

from datetime import UTC, datetime
from uuid import uuid4
from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class Entity:
    """
    Building Model temel sınıfı.

    Attributes
    ----------
    id
        Proje içindeki sayısal kimlik.

    guid
        Evrensel benzersiz kimlik.

    name
        Kullanıcı tarafından görünen isim.

    properties
        Genişletilebilir özellik sözlüğü.

    metadata
        Sistem tarafından kullanılan ek bilgiler.

    created_at
        Nesnenin oluşturulma zamanı.

    updated_at
        Son güncellenme zamanı.

    is_deleted
        Mantıksal silinme durumu.

    version
        Nesnenin sürüm numarası.

    tags
        Nesneye ait etiketler.
    """
    id: int = 0

    guid: str = field(default_factory=lambda: str(uuid4()))

    name: str = ""

    properties: dict[str, Any] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    is_deleted: bool = False

    version: int = 1

    tags: set[str] = field(default_factory=set)
    # ------------------------------------------------------------

    def set_property(self, key: str, value: Any) -> None:
        """Özel bir özellik ekler veya günceller."""
        self.properties[key] = value

    # ------------------------------------------------------------

    def get_property(self, key: str, default: Any = None) -> Any:
        """Özel bir özelliği döndürür."""
        return self.properties.get(key, default)

    # ------------------------------------------------------------

    def set_metadata(self, key: str, value: Any) -> None:
        """Metadata alanına bilgi yazar."""
        self.metadata[key] = value

    # ------------------------------------------------------------

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Metadata bilgisini döndürür."""
        return self.metadata.get(key, default)

    # ------------------------------------------------------------
    

    def touch(self) -> None:
        """Nesnenin güncellenme zamanını yeniler."""
        self.updated_at = datetime.now(UTC)

    # ------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """
        Nesneyi sözlüğe dönüştürür.

        JSON kayıtları ve raporlar için kullanılacaktır.
        """

        return {
            "id": self.id,
            "guid": self.guid,
            "name": self.name,
            "properties": dict(self.properties),
            "metadata": dict(self.metadata),
        }

    # ------------------------------------------------------------

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id}, name='{self.name}')"

    # ------------------------------------------------------------

    def __repr__(self) -> str:
        return self.__str__()