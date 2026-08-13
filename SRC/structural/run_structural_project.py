# -*- coding: utf-8 -*-
"""Cok katli statik metraj. proje.json axis_grid varsa DXF aks okunmaz."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import ezdxf

from SRC.structural.project_schema import load_structural_project, FloorSpec
from SRC.structural.axis_based_structural import AxisBasedStructural
from SRC.structural.axis_layout_from_dxf import AxisLayoutFromDxf
from SRC.structural.axis_grid import AxisGrid, AxisGridError
from SRC.structural.shear_wall_extractor import ShearWallExtractor
from SRC.structural.raft_extractor import RaftExtractor
from SRC.structural.slab_extractor import SlabExtractor
from SRC.structural.rebar_from_grid import RebarFromGrid
from SRC.structural.raft_rebar import RaftGeometry, RaftRebarSpec, RaftRebarCalculator
from SRC.structural.models import RebarItem, Raft
from SRC.structural.quantity_calculator import QuantityCalculator
from SRC.structural.excel_export import export_to_excel
from SRC.structural.core_walls import cores_from_json, tag_basement_shear
from SRC.structural.axis_audit import audit_axis_grid
from SRC.structural.section_from_dxf import SectionFromDxf
from SRC.structural.slab_rebar_from_dxf import SlabRebarFromDxf

def process_floor(
    spec: FloorSpec,
    project_unit_to_m: float,
    grid_override=None,
    raft_thickness_cm: float = 0.0,
    raft_overhang_m: float = 1.0,
):
    print()
    print("#" * 60)
    print("# KAT:", spec.name, "kind=", spec.kind, "H=", spec.column_height_m, "m")
    print("# DXF:", spec.dxf)
    print("#" * 60)

    path = Path(spec.dxf)
    if not path.exists():
        print("UYARI: DXF yok:", path)
        return [], [], [], [], [], []

    doc = ezdxf.readfile(str(path))
    unit_to_m = spec.unit_to_m if getattr(spec, "unit", None) else project_unit_to_m

    layout = None
    if grid_override is not None:
        grid = grid_override
        print("AKS GRID: proje.json manuel tablo kullanildi")
        print("  X={:.2f} m  Y={:.2f} m".format(grid.total_x_m, grid.total_y_m))
    else:
        print("AKS GRID: DXF okunacak")
        layout = AxisLayoutFromDxf(
            doc, unit_to_m=unit_to_m, source_path=str(path),
        ).build()
        grid = layout.grid

    abs_ = AxisBasedStructural(
        doc,
        height_cm=spec.height_cm if spec.kind != "foundation" else max(spec.height_cm, 1.0),
        floor=spec.name,
        unit_to_m_hint=unit_to_m,
        beam_mode=getattr(spec, "beam_mode", "axis") or "axis",
    )
    abs_.grid_override = grid_override
    columns, beams, grid2 = abs_.build()
    if grid is None or len(getattr(grid, "x_labels", [])) < 2:
        grid = grid2

    if spec.kind == "foundation":
        for c in columns:
            c.height_cm = 0.0

    shear_walls = []
    if spec.kind != "foundation":
        try:
            shear_walls = ShearWallExtractor(
                doc,
                default_height_cm=spec.height_cm,
                unit_to_m=unit_to_m,
                floor=spec.name,
            ).extract()
        except Exception as e:
            print("Perde uyari:", e)

    slabs = []
    if getattr(spec, "include_slab", False) and spec.kind != "foundation":
        try:
            slabs = SlabExtractor(doc, unit_to_m=unit_to_m, floor=spec.name).extract()
        except Exception as e:
            print("Doseme uyari:", e)

    rafts = []
    if spec.kind == "foundation" and getattr(spec, "include_raft", True):
        try:
            rafts = RaftExtractor(doc, unit_to_m=unit_to_m).extract()
            for r in rafts:
                r.floor = "TEMEL"
        except Exception as e:
            print("Radye DXF uyari:", e)

        if not rafts and grid is not None and len(grid.x_labels) >= 2:
            geom = RaftGeometry.from_grid(grid, overhang_m=raft_overhang_m)
            thick_cm = float(raft_thickness_cm) if raft_thickness_cm > 0 else 0.0
            if thick_cm <= 0:
                print("! Radye kalinlik yok - beton 0")
            rafts = [
                Raft(
                    id=1,
                    area_m2=geom.area_m2,
                    thickness_cm=thick_cm,
                    perimeter_m=2.0 * (geom.length_x_m + geom.length_y_m),
                    floor="TEMEL",
                )
            ]
            print("RADYE: {:.2f} m2  t={:.0f} cm".format(geom.area_m2, thick_cm))
            if thick_cm > 0:
                print("  beton ~ {:.2f} m3".format(geom.area_m2 * thick_cm / 100.0))

    if spec.kind != "foundation":
        rafts = []

    rebars = []
    if grid is not None and len(getattr(grid, "x_labels", [])) >= 2:
        try:
            if spec.kind == "foundation":
                rebars.extend(
                    _build_foundation_rebar(
                        grid, columns, beams, layout,
                        raft_thickness_cm=raft_thickness_cm,
                        raft_overhang_m=raft_overhang_m,
                    )
                )
            else:
                try:
                    schedule = RebarFromGrid(
                        grid=grid, columns=columns, beams=beams, floor=spec.name,
                    ).build()
                    items = _to_items(schedule, spec.name)
                    items = [
                        it for it in items
                        if getattr(it, "element_type", "") not in (
                            "radye", "bag_kiris", "zemin_beton",
                        )
                    ]
                    rebars.extend(items)
                except Exception as e:
                    print("Kat demir uyari:", e)
        except Exception as e:
            print("Demir uyari:", e)

    if slabs and spec.kind != "foundation":
        try:
            slab_rb = SlabRebarFromDxf(doc, floor=spec.name).build_for_slabs(slabs)
            rebars = list(rebars or [])
            rebars.extend(slab_rb)
        except Exception as e:
            print("Doseme demir uyari:", e)

    if spec.kind == "foundation":
        return [], [], [], rafts, [], rebars
    return columns, beams, shear_walls, rafts, slabs, rebars


def _build_foundation_rebar(
    grid, columns, beams, layout,
    raft_thickness_cm=0.0, raft_overhang_m=1.0,
):
    items = []
    try:
        n_col = len(columns) if columns else len(grid.x_labels) * len(grid.y_labels)
        secs = [getattr(c, "section", (0, 0)) for c in columns] if columns else []
        geom = RaftGeometry.from_grid(grid, overhang_m=raft_overhang_m)
        spec = RaftRebarSpec(
            thickness_cm=raft_thickness_cm if raft_thickness_cm > 0 else 0.0
        )
        calc = RaftRebarCalculator(
            geom, spec, grid=grid, n_columns=n_col,
            column_sections=secs, floor="TEMEL",
        )
        items.extend(_to_items(calc.build(), "TEMEL"))
    except Exception as e:
        print("Temel demir uyari:", e)
    return items


def _to_items(schedule, floor):
    out = []
    for ln in getattr(schedule, "lines", None) or []:
        out.append(RebarItem(
            id=getattr(ln, "id", 0) or 0,
            diameter_mm=ln.diameter_mm,
            length_m=ln.length_m,
            count=ln.count,
            element_type=ln.element,
            element_mark=getattr(ln, "axis_ref", "") or getattr(ln, "note", ""),
            note=getattr(ln, "note", ""),
            floor=getattr(ln, "floor", None) or floor,
        ))
    return out


def _load_grid_override(project_path):
    try:
        raw = json.loads(Path(project_path).read_text(encoding="utf-8-sig"))
    except Exception as e:
        print("! proje.json okunamadi:", e)
        return None
    ag = raw.get("axis_grid")
    print("axis_grid JSON'da var mi?", ag is not None)
    if not ag:
        return None
    try:
        grid = AxisGrid.from_spacings(
            x_labels=ag["x_labels"],
            y_labels=ag["y_labels"],
            x_spacings_m=ag["x_spacings_m"],
            y_spacings_m=ag["y_spacings_m"],
            source="manuel (proje.json)",
        )
        print("grid_override OK  X={:.2f} m  Y={:.2f} m".format(
            grid.total_x_m, grid.total_y_m
        ))
        return grid
    except Exception as e:
        print("! axis_grid hatasi:", e)
        return None


def main():
    args = sys.argv[1:]
    if not args:
        print("Kullanim: python -m SRC.structural.run_structural_project proje.json --excel out.xlsx")
        sys.exit(1)

    excel_path = "statik_metraj.xlsx"
    project_path = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--excel" and i + 1 < len(args):
            excel_path = args[i + 1]
            i += 2
        elif not a.startswith("--"):
            project_path = a
            i += 1
        else:
            i += 1

    if not project_path:
        print("project.json yolu gerekli")
        sys.exit(1)

    proj = load_structural_project(project_path)
    print("Proje:", proj.name, "| Kat:", len(proj.expanded_floors()))

    all_c, all_b, all_s, all_r, all_sl, all_rb = [], [], [], [], [], []

    grid_override = _load_grid_override(project_path)
    if grid_override is None:
        print("HATA: proje.json icinde gecerli axis_grid yok")
        sys.exit(1)

    raft_thickness_cm = getattr(proj, "raft_thickness_cm", 0) or 0
    raft_overhang_m = getattr(proj, "raft_overhang_m", 1.0) or 1.0
    try:
        raw = json.loads(Path(project_path).read_text(encoding="utf-8-sig"))
        if not raft_thickness_cm:
            raft_thickness_cm = float(raw.get("raft_thickness_cm") or 0)
        if raw.get("raft_overhang_m") is not None:
            raft_overhang_m = float(raw.get("raft_overhang_m"))
    except Exception:
        pass

    for spec in proj.expanded_floors():
        c, b, s, r, sl, rb = process_floor(
            spec, proj.unit_to_m,
            grid_override=grid_override,
            raft_thickness_cm=raft_thickness_cm,
            raft_overhang_m=raft_overhang_m,
        )
        all_c.extend(c); all_b.extend(b); all_s.extend(s)
        all_r.extend(r); all_sl.extend(sl); all_rb.extend(rb)

    try:
        _raw = json.loads(Path(project_path).read_text(encoding="utf-8-sig"))
        all_s.extend(cores_from_json(_raw))
        all_s = tag_basement_shear(all_s)
    except Exception as e:
        print("Core duvar uyari:", e)

    for lst in (all_c, all_b, all_s, all_r, all_sl, all_rb):
        for i, x in enumerate(lst, 1):
            x.id = i
    # DOSEME ZORUNLU — all_sl bos ise
    if not all_sl and grid_override is not None:
        from SRC.structural.models import Slab
        area = float(grid_override.total_x_m) * float(grid_override.total_y_m)
        peri = 2.0 * (float(grid_override.total_x_m) + float(grid_override.total_y_m))
        t_cm = float(getattr(proj, "slab_thickness_cm", 0) or 0) or 20.0
        ff = float(getattr(proj, "slab_formwork_factor", 1.0) or 1.0)
        floor_names = [
            s.name for s in proj.expanded_floors()
            if getattr(s, "kind", "") != "foundation"
            and bool(getattr(s, "include_slab", True))
        ]
        if not floor_names:
            floor_names = ["Zemin"]
        all_sl = []
        for i, fname in enumerate(floor_names, 1):
            all_sl.append(
                Slab(
                    id=i,
                    area_m2=area,
                    thickness_cm=t_cm,
                    perimeter_m=peri,
                    floor=fname,
                    mark="SLAB-GRID",
                    formwork_factor=ff,
                )
            )
        n = len(all_sl)
        print()
        print("=" * 55)
        print("DOSEME ZORUNLU (ozet oncesi)")
        print("=" * 55)
        print("Kat adedi :", n)
        print("Tek kat alan : {:.1f} m2".format(area))
        print("Kalinlik : {:.0f} cm".format(t_cm))
        print("Kalip toplam : {:.1f} m2".format(area * n * ff))
        print("Beton toplam : {:.1f} m3".format(area * (t_cm / 100.0) * n))

    result = QuantityCalculator(
        default_column_height_cm=proj.default_column_height_m * 100
    ).build(
        columns=all_c, 
        beams=all_b, 
        shear_walls=all_s,
        rafts=all_r, 
        slabs=all_sl, 
        rebars=all_rb, 
        project_name=proj.name,
    )
    export_to_excel(result, excel_path)
    print("\nExcel:", excel_path)
    return result

if __name__ == "__main__":
    main()