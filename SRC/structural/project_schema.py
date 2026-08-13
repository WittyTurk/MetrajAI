# -*- coding: utf-8 -*-
"""Statik çok katlı proje şeması."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class FloorSpec:
    name: str
    dxf: str
    kind: str = "floor"  # foundation | floor | typical | roof
    column_height_m: float = 3.0
    beam_mode: str = "line"
    include_raft: bool = False
    include_tie_beams: bool = False
    include_slab: bool = True
    include_parapet: bool = False
    repeat: int = 1
    unit: Optional[str] = None
    layer_map: dict = field(default_factory=dict)

    @property
    def height_cm(self) -> float:
        return self.column_height_m * 100.0

    @property
    def unit_to_m(self) -> float:
        u = (self.unit or "cm").lower()
        return {"mm": 0.001, "cm": 0.01, "m": 1.0}.get(u, 0.01)


@dataclass
class StructuralProject:
    name: str
    floors: List[FloorSpec]
    unit: str = "cm"
    default_column_height_m: float = 3.0
    source_path: Optional[str] = None

    @property
    def unit_to_m(self) -> float:
        return {"mm": 0.001, "cm": 0.01, "m": 1.0}.get(self.unit.lower(), 0.01)

    def expanded_floors(self) -> List[FloorSpec]:
        out: List[FloorSpec] = []
        for f in self.floors:
            if f.kind == "typical" and f.repeat > 1:
                for i in range(f.repeat):
                    out.append(FloorSpec(
                        name=f"{f.name}#{i+1}",
                        dxf=f.dxf,
                        kind="floor",
                        column_height_m=f.column_height_m,
                        beam_mode=f.beam_mode,
                        include_raft=False,
                        include_tie_beams=f.include_tie_beams,
                        include_slab=f.include_slab,
                        include_parapet=f.include_parapet,
                        unit=f.unit or self.unit,
                        layer_map=dict(f.layer_map),
                    ))
            else:
                if not f.unit:
                    f.unit = self.unit
                out.append(f)
        return out


def load_structural_project(path: str) -> StructuralProject:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    floors = []
    for raw in data.get("floors", []):
        floors.append(FloorSpec(
            name=raw["name"],
            dxf=raw["dxf"],
            kind=raw.get("kind", "floor"),
            column_height_m=float(
                raw.get("column_height_m", data.get("default_column_height_m", 3.0))
            ),
            beam_mode=raw.get("beam_mode", "line"),
            include_raft=bool(raw.get("include_raft", raw.get("kind") == "foundation")),
            include_tie_beams=bool(
                raw.get("include_tie_beams", raw.get("kind") == "foundation")
            ),
            include_slab=bool(raw.get("include_slab", True)),
            include_parapet=bool(raw.get("include_parapet", False)),
            repeat=int(raw.get("repeat", 1)),
            unit=raw.get("unit"),
            layer_map=dict(raw.get("layer_map") or {}),
        ))
    return StructuralProject(
        name=data.get("name", p.stem),
        floors=floors,
        unit=data.get("unit", "cm"),
        default_column_height_m=float(data.get("default_column_height_m", 3.0)),
        source_path=str(p),
    )
