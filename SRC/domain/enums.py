"""
------------------------------------------------------------
MetrajAI

Building Enumerations

Bu modül Building Model içerisinde kullanılan ortak
enum tanımlarını içerir.

Geometry3 bağımlılığı yoktur.

------------------------------------------------------------
"""

from __future__ import annotations

from enum import Enum, auto


class BuildingType(Enum):
    """Yapı türleri."""

    UNKNOWN = auto()
    RESIDENTIAL = auto()
    SCHOOL = auto()
    HOSPITAL = auto()
    GOVERNMENT = auto()
    SOCIAL_FACILITY = auto()
    INDUSTRIAL = auto()


class FloorType(Enum):
    """Kat türleri."""

    BASEMENT = auto()
    GROUND = auto()
    NORMAL = auto()
    ROOF = auto()


class WallType(Enum):
    """Duvar türleri."""

    UNKNOWN = auto()
    INTERIOR = auto()
    EXTERIOR = auto()
    SHEAR = auto()
    FIRE = auto()


class ColumnType(Enum):
    """Kolon türleri."""

    RECTANGULAR = auto()
    SQUARE = auto()
    CIRCULAR = auto()


class BeamType(Enum):
    """Kiriş türleri."""

    RECTANGULAR = auto()
    INVERTED = auto()
    T_BEAM = auto()


class SlabType(Enum):
    """Döşeme türleri."""

    SOLID = auto()
    RIBBED = auto()
    WAFFLE = auto()


class DoorType(Enum):
    """Kapı türleri."""

    SINGLE = auto()
    DOUBLE = auto()
    FIRE = auto()
    SLIDING = auto()


class WindowType(Enum):
    """Pencere türleri."""

    FIXED = auto()
    CASEMENT = auto()
    SLIDING = auto()


class MaterialType(Enum):
    """Yapı malzemeleri."""

    CONCRETE = auto()
    STEEL = auto()
    MASONRY = auto()
    WOOD = auto()
    GLASS = auto()

from enum import Enum


class SlabType(Enum):
    """
    Structural slab classification.
    """

    NORMAL_SLAB = "normal_slab"

    RAFT_FOUNDATION = "raft_foundation"

    GROUND_SLAB = "ground_slab"

    ROOF_SLAB = "roof_slab"

    TECHNICAL_SLAB = "technical_slab"