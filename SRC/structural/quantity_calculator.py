# -*- coding: utf-8 -*-
from collections import defaultdict
from SRC.structural.models import QuantityResult


class QuantityCalculator:
    def __init__(self, default_column_height_cm=300.0):
        self.default_column_height_cm = default_column_height_cm

    def build(
        self,
        columns=None,
        beams=None,
        shear_walls=None,
        rafts=None,
        slabs=None,
        rebars=None,
        project_name="",
    ) -> QuantityResult:
        columns = columns or []
        beams = beams or []
        shear_walls = shear_walls or []
        rafts = rafts or []
        slabs = slabs or []
        rebars = rebars or []

        for c in columns:
            if c.height_cm <= 0:
                c.height_cm = self.default_column_height_cm

        result = QuantityResult(
            columns=columns,
            beams=beams,
            shear_walls=shear_walls,
            rafts=rafts,
            slabs=slabs,
            rebars=rebars,
            project_name=project_name,
        )

        print()
        print("=" * 55)
        print("STATİK METRAJ ÖZETİ" + (f" — {project_name}" if project_name else ""))
        print("=" * 55)
        print(f"Kolon adedi              : {len(columns)}")
        print(f"Kolon beton              : {result.total_column_concrete_m3:.2f} m³")
        print(f"Kolon kalıp              : {result.total_column_formwork_m2:.2f} m²")
        print(f"Kiriş adedi              : {len(beams)}")
        print(f"Kiriş beton              : {result.total_beam_concrete_m3:.2f} m³")
        print(f"Kiriş kalıp              : {result.total_beam_formwork_m2:.2f} m²")
        print(f"Perde adedi              : {len(shear_walls)}")
        print(f"Perde beton              : {result.total_shear_concrete_m3:.2f} m³")
        print(f"Perde kalıp              : {result.total_shear_formwork_m2:.2f} m²")
        print(f"Döşeme adedi             : {len(slabs)}")
        print(f"Döşeme beton             : {result.total_slab_concrete_m3:.2f} m³")
        print(f"Döşeme kalıp (alt)       : {result.total_slab_formwork_m2:.2f} m²")
        print(f"Radye adedi              : {len(rafts)}")
        print(f"Radye beton              : {result.total_raft_concrete_m3:.2f} m³")
        print(f"Radye kalıp (yan)        : {result.total_raft_formwork_m2:.2f} m²")
        print(f"Demir kalemi             : {len(rebars)}")
        print(f"Demir toplam             : {result.total_rebar_kg:.1f} kg  ({result.total_rebar_kg/1000:.2f} ton)")
        print("-" * 55)
        print(f"TOPLAM BETON             : {result.total_concrete_m3:.2f} m³")
        print(f"TOPLAM KALIP             : {result.total_formwork_m2:.2f} m²")
        print(f"TOPLAM DEMİR             : {result.total_rebar_kg:.1f} kg")

        if rebars:
            by_dia = defaultdict(float)
            for r in rebars:
                by_dia[r.diameter_mm] += r.weight_kg
            print("\nDemir çapa göre:")
            for d in sorted(by_dia.keys()):
                print(f"  Ø{d:.0f}  →  {by_dia[d]:.1f} kg")

        floors = result.floors()
        if len(floors) > 1 or (floors and floors[0] not in ("GENEL",)):
            print("\nKAT BAZLI:")
            by_floor = defaultdict(lambda: {"c": 0.0, "k": 0.0, "d": 0.0})
            for c in columns:
                by_floor[c.floor]["c"] += c.concrete_m3
                by_floor[c.floor]["k"] += c.formwork_m2
            for b in beams:
                by_floor[b.floor]["c"] += b.concrete_m3
                by_floor[b.floor]["k"] += b.formwork_m2
            for s in shear_walls:
                by_floor[s.floor]["c"] += s.concrete_m3
                by_floor[s.floor]["k"] += s.formwork_m2
            for s in slabs:
                by_floor[s.floor]["c"] += s.concrete_m3
                by_floor[s.floor]["k"] += s.formwork_m2
            for r in rafts:
                by_floor[r.floor]["c"] += r.concrete_m3
                by_floor[r.floor]["k"] += r.formwork_m2
            for r in rebars:
                by_floor[r.floor]["d"] += r.weight_kg
            for fl in sorted(by_floor.keys()):
                d = by_floor[fl]
                print(f"  {fl:12}  beton={d['c']:.2f} m³  kalıp={d['k']:.2f} m²  demir={d['d']:.1f} kg")

        return result