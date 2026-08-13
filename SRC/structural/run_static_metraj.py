# -*- coding: utf-8 -*-
"""
Statik metraj — beton + kalıp + demir + döşeme (çok katlı).

  python -m SRC.structural.run_static_metraj INPUT/statik.dxf --floor Zemin --excel metraj.xlsx
  python -m SRC.structural.run_static_metraj --multi Zemin=z.dxf 1Kat=1.dxf --excel metraj.xlsx
"""

from __future__ import annotations

import sys
from pathlib import Path

import ezdxf

from SRC.structural.axis_based_structural import AxisBasedStructural
from SRC.structural.shear_wall_extractor import ShearWallExtractor
from SRC.structural.raft_extractor import RaftExtractor
from SRC.structural.slab_extractor import SlabExtractor
from SRC.structural.rebar_extractor import RebarExtractor
from SRC.structural.quantity_calculator import QuantityCalculator
from SRC.structural.excel_export import export_to_excel


def process_one(
    dxf_path: str,
    floor: str = "GENEL",
    height_cm: float = 300.0,
    unit_to_m: float = 0.01,
):
    print(f"\n>>> Dosya: {dxf_path}  |  Kat: {floor}")
    doc = ezdxf.readfile(dxf_path)

    # Aks grid: 9 kolon + 6 kiriş (adet ve boy grid'den, kesit DXF'ten)
    abs_ = AxisBasedStructural(
        doc,
        height_cm=height_cm,
        floor=floor,
        unit_to_m_hint=unit_to_m,
        beam_mode="line",
    )
    columns, beams, _grid = abs_.build()

    shear_walls = ShearWallExtractor(
        doc, default_height_cm=height_cm, unit_to_m=unit_to_m, floor=floor
    ).extract()
    slabs = SlabExtractor(doc, unit_to_m=unit_to_m, floor=floor).extract()
    rafts = RaftExtractor(doc, unit_to_m=unit_to_m).extract()
    for r in rafts:
        r.floor = "TEMEL" if floor == "GENEL" else floor

    rebar_ex = RebarExtractor(floor=floor)
    rebars = rebar_ex.extract_from_columns(columns) + rebar_ex.extract_from_beams(beams)

    return columns, beams, shear_walls, rafts, slabs, rebars


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    excel_path = "statik_metraj.xlsx"
    height_cm = 300.0
    unit_to_m = 0.01
    floor = "GENEL"
    multi = []
    single = None

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--excel" and i + 1 < len(args):
            excel_path = args[i + 1]
            i += 2
        elif a == "--floor" and i + 1 < len(args):
            floor = args[i + 1]
            i += 2
        elif a == "--height" and i + 1 < len(args):
            height_cm = float(args[i + 1])
            i += 2
        elif a == "--unit" and i + 1 < len(args):
            unit_to_m = 0.01 if args[i + 1] == "cm" else 0.001
            i += 2
        elif a == "--multi":
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                if "=" in args[i]:
                    fl, p = args[i].split("=", 1)
                    multi.append((fl, p))
                i += 1
        elif not a.startswith("--"):
            single = a
            i += 1
        else:
            i += 1

    all_c, all_b, all_s, all_r, all_sl, all_rb = [], [], [], [], [], []

    if multi:
        for fl, path in multi:
            c, b, s, r, sl, rb = process_one(
                path, floor=fl, height_cm=height_cm, unit_to_m=unit_to_m
            )
            all_c.extend(c)
            all_b.extend(b)
            all_s.extend(s)
            all_r.extend(r)
            all_sl.extend(sl)
            all_rb.extend(rb)
        for i, x in enumerate(all_c, 1):
            x.id = i
        for i, x in enumerate(all_b, 1):
            x.id = i
        for i, x in enumerate(all_s, 1):
            x.id = i
        for i, x in enumerate(all_r, 1):
            x.id = i
        for i, x in enumerate(all_sl, 1):
            x.id = i
        for i, x in enumerate(all_rb, 1):
            x.id = i
    elif single:
        all_c, all_b, all_s, all_r, all_sl, all_rb = process_one(
            single, floor=floor, height_cm=height_cm, unit_to_m=unit_to_m
        )
    else:
        print("DXF yolu gerekli.")
        sys.exit(1)

    result = QuantityCalculator(default_column_height_cm=height_cm).build(
        columns=all_c,
        beams=all_b,
        shear_walls=all_s,
        rafts=all_r,
        slabs=all_sl,
        rebars=all_rb,
        project_name=Path(single or multi[0][1]).stem,
    )
    export_to_excel(result, excel_path)
    return result


if __name__ == "__main__":
    main()