# -*- coding: utf-8 -*-
"""Merdiven kova + asansor shaft + bodrum perde (proje.json cores)."""

from __future__ import annotations
from typing import List
from SRC.structural.models import ShearWall

TYPE_TO_KIND = {
    "stair": "stair_core",
    "merdiven": "stair_core",
    "elevator": "elevator",
    "asansor": "elevator",
    "asansör": "elevator",
    "bodrum": "bodrum",
    "basement": "bodrum",
}


def cores_from_json(project_data: dict) -> List[ShearWall]:
    out: List[ShearWall] = []
    cores = project_data.get("cores") or []
    wid = 9000
    for raw in cores:
        typ = str(raw.get("type") or raw.get("kind") or "").lower().strip()
        kind = TYPE_TO_KIND.get(
            typ, typ if typ in ("stair_core", "elevator", "bodrum", "kat") else "kat"
        )
        mark = str(raw.get("mark") or kind)
        thick = float(raw.get("thickness_cm") or 0)
        peri = float(raw.get("perimeter_m") or raw.get("length_m") or 0)
        height_m = float(raw.get("height_m") or 0)
        floors = raw.get("floors") or [str(raw.get("floor") or "GENEL")]
        if thick <= 0 or peri <= 0 or height_m <= 0:
            print(f"! Core {mark} ({kind}): olcu eksik → 0 (uydurma yok)")
            continue
        for fl in floors:
            wid += 1
            out.append(
                ShearWall(
                    id=wid,
                    thickness_cm=thick,
                    length_m=peri,
                    height_cm=height_m * 100.0,
                    mark=mark,
                    floor=str(fl),
                    kind=kind,
                )
            )
    if out:
        print()
        print("=" * 55)
        print("CORE / BODRUM DUVAR (proje.json)")
        print("=" * 55)
        for w in out:
            print(
                f"  {w.kind:12} {w.mark:10} kat={w.floor:12} "
                f"L={w.length_m:.2f}m t={w.thickness_cm:.0f}cm "
                f"H={w.height_cm/100:.2f}m beton={w.concrete_m3:.2f}m3 "
                f"kalip={w.formwork_m2:.2f}m2"
            )
    return out


def tag_basement_shear(walls: List[ShearWall], basement_floors=None) -> List[ShearWall]:
    basement_floors = set(basement_floors or ["BODRUM", "Bodrum", "TEMEL", "bodrum"])
    for w in walls:
        if w.floor in basement_floors or str(w.floor).upper().startswith("BOD"):
            w.kind = "bodrum"
    return walls