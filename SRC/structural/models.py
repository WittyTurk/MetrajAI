# -*- coding: utf-8 -*-
"""
Statik metraj modelleri — cok katli / DXF birebir.
Kolon, kiris, perde, radye, doseme, demir.
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Column:
    id: int
    mark: str
    section: Tuple[float, float]
    x: float
    y: float
    height_cm: float = 300.0
    floor: str = "GENEL"
    rebar_notes: List[str] = field(default_factory=list)
    source_block: str = ""

    @property
    def area_cm2(self) -> float:
        return self.section[0] * self.section[1]

    @property
    def concrete_m3(self) -> float:
        return (self.area_cm2 * self.height_cm) / 1_000_000.0

    @property
    def formwork_m2(self) -> float:
        a, b = self.section
        return (2.0 * (a + b) * self.height_cm) / 10_000.0


@dataclass
class Beam:
    id: int
    mark: str
    section: Tuple[float, float]
    length_m: float
    x: float = 0.0
    y: float = 0.0
    floor: str = "GENEL"
    rebar_notes: List[str] = field(default_factory=list)
    source_block: str = ""
    length_from_geometry: bool = False

    @property
    def concrete_m3(self) -> float:
        b, h = self.section
        return (b / 100.0) * (h / 100.0) * self.length_m

    @property
    def formwork_m2(self) -> float:
        b, h = self.section
        return (2.0 * (h / 100.0) + (b / 100.0)) * self.length_m


@dataclass
class ShearWall:
    """
    kind:
      kat          — normal kat perdesi
      bodrum       — bodrum perdesi
      stair_core   — merdiven kova duvari
      elevator     — asansor shaft duvari
    thickness_cm=0 → beton 0 (uydurma yok)
    """
    id: int
    thickness_cm: float
    length_m: float
    height_cm: float = 300.0
    mark: str = ""
    x: float = 0.0
    y: float = 0.0
    floor: str = "GENEL"
    kind: str = "kat"

    @property
    def concrete_m3(self) -> float:
        if self.thickness_cm <= 0 or self.length_m <= 0 or self.height_cm <= 0:
            return 0.0
        return (self.thickness_cm / 100.0) * self.length_m * (self.height_cm / 100.0)

    @property
    def formwork_m2(self) -> float:
        if self.length_m <= 0 or self.height_cm <= 0:
            return 0.0
        return 2.0 * self.length_m * (self.height_cm / 100.0)


@dataclass
class Raft:
    id: int
    area_m2: float
    thickness_cm: float
    perimeter_m: float = 0.0
    floor: str = "TEMEL"

    @property
    def concrete_m3(self) -> float:
        if self.thickness_cm <= 0 or self.area_m2 <= 0:
            return 0.0
        return self.area_m2 * (self.thickness_cm / 100.0)

    @property
    def formwork_m2(self) -> float:
        if self.thickness_cm <= 0 or self.perimeter_m <= 0:
            return 0.0
        return self.perimeter_m * (self.thickness_cm / 100.0)


@dataclass
class Slab:
    """Doseme plakasi."""
    id: int
    area_m2: float
    thickness_cm: float
    perimeter_m: float = 0.0
    floor: str = "GENEL"
    mark: str = ""
    formwork_factor: float = 1.0

    @property
    def concrete_m3(self) -> float:
        if self.thickness_cm <= 0 or self.area_m2 <= 0:
            return 0.0
        return self.area_m2 * (self.thickness_cm / 100.0)

    @property
    def formwork_m2(self) -> float:
        if self.area_m2 <= 0 or self.formwork_factor <= 0:
            return 0.0
        return self.area_m2 * self.formwork_factor


@dataclass
class RebarItem:
    """
    Demir kalemi.
    weight_kg = adet * boy_m * birim_agirlik (kg/m)
    """
    id: int
    diameter_mm: float
    length_m: float
    count: int = 1
    element_type: str = ""
    element_mark: str = ""
    note: str = ""
    floor: str = "GENEL"

    WEIGHT_KG_PER_M = {
        6: 0.222,
        8: 0.395,
        10: 0.617,
        12: 0.888,
        14: 1.208,
        16: 1.578,
        18: 2.000,
        20: 2.466,
        22: 2.984,
        24: 3.551,
        25: 3.853,
        28: 4.834,
        32: 6.313,
    }

    @property
    def unit_weight(self) -> float:
        d = int(round(self.diameter_mm))
        return self.WEIGHT_KG_PER_M.get(d, (d / 2) ** 2 * 0.006165)

    @property
    def total_length_m(self) -> float:
        return self.length_m * self.count

    @property
    def weight_kg(self) -> float:
        return self.total_length_m * self.unit_weight


@dataclass
class QuantityResult:
    columns: List[Column] = field(default_factory=list)
    beams: List[Beam] = field(default_factory=list)
    shear_walls: List[ShearWall] = field(default_factory=list)
    rafts: List[Raft] = field(default_factory=list)
    slabs: List[Slab] = field(default_factory=list)
    rebars: List[RebarItem] = field(default_factory=list)
    project_name: str = ""

    @property
    def total_column_concrete_m3(self) -> float:
        return sum(c.concrete_m3 for c in self.columns)

    @property
    def total_column_formwork_m2(self) -> float:
        return sum(c.formwork_m2 for c in self.columns)

    @property
    def total_beam_concrete_m3(self) -> float:
        return sum(b.concrete_m3 for b in self.beams)

    @property
    def total_beam_formwork_m2(self) -> float:
        return sum(b.formwork_m2 for b in self.beams)

    @property
    def total_shear_concrete_m3(self) -> float:
        return sum(s.concrete_m3 for s in self.shear_walls)

    @property
    def total_shear_formwork_m2(self) -> float:
        return sum(s.formwork_m2 for s in self.shear_walls)

    def shear_by_kind(self, kind: str) -> List[ShearWall]:
        return [s for s in self.shear_walls if getattr(s, "kind", "kat") == kind]

    def total_shear_kind_concrete_m3(self, kind: str) -> float:
        return sum(s.concrete_m3 for s in self.shear_by_kind(kind))

    def total_shear_kind_formwork_m2(self, kind: str) -> float:
        return sum(s.formwork_m2 for s in self.shear_by_kind(kind))

    @property
    def total_raft_concrete_m3(self) -> float:
        return sum(r.concrete_m3 for r in self.rafts)

    @property
    def total_raft_formwork_m2(self) -> float:
        return sum(r.formwork_m2 for r in self.rafts)

    @property
    def total_slab_concrete_m3(self) -> float:
        return sum(s.concrete_m3 for s in self.slabs)

    @property
    def total_slab_formwork_m2(self) -> float:
        return sum(s.formwork_m2 for s in self.slabs)

    @property
    def total_rebar_kg(self) -> float:
        return sum(r.weight_kg for r in self.rebars)

    @property
    def total_concrete_m3(self) -> float:
        return (
            self.total_column_concrete_m3
            + self.total_beam_concrete_m3
            + self.total_shear_concrete_m3
            + self.total_raft_concrete_m3
            + self.total_slab_concrete_m3
        )

    @property
    def total_formwork_m2(self) -> float:
        return (
            self.total_column_formwork_m2
            + self.total_beam_formwork_m2
            + self.total_shear_formwork_m2
            + self.total_raft_formwork_m2
            + self.total_slab_formwork_m2
        )

    def floors(self) -> List[str]:
        names = set()
        for items in (
            self.columns,
            self.beams,
            self.shear_walls,
            self.rafts,
            self.slabs,
            self.rebars,
        ):
            for it in items:
                names.add(getattr(it, "floor", "GENEL"))
        return sorted(names)
