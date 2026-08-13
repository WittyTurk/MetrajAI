# -*- coding: utf-8 -*-
"""
Tek tuş metraj — Taziye ve çok katlı.

  python -m SRC.core.run_all
  python -m SRC.core.run_all --input INPUT
"""

from __future__ import annotations

import sys
from pathlib import Path

from SRC.core.input_scanner import InputScanner
from SRC.core.validator import MetrajValidator


def main():
    args = sys.argv[1:]
    input_root = "INPUT"
    excel_path = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--input" and i + 1 < len(args):
            input_root = args[i + 1]
            i += 2
        elif a == "--excel" and i + 1 < len(args):
            excel_path = args[i + 1]
            i += 2
        else:
            i += 1

    print()
    print("*" * 60)
    print("*  MetrajAI — TEK TUŞ METRAJ")
    print("*" * 60)

    discovery = InputScanner(input_root).scan()
    out_dir = Path(input_root) / "cikti"
    out_dir.mkdir(parents=True, exist_ok=True)
    if excel_path is None:
        excel_path = str(out_dir / f"{discovery.project_name}_metraj.xlsx")

    v = MetrajValidator()
    pre = v.validate_discovery(discovery)
    pre.report()
    if not pre.ok:
        print("Keşif hatalı — durduruldu.")
        sys.exit(2)

    all_c, all_b, all_s, all_r, all_sl, all_rb = [], [], [], [], [], []

    if discovery.static_floors:
        from SRC.structural.project_schema import FloorSpec
        from SRC.structural.run_structural_project import process_floor
        from SRC.structural.quantity_calculator import QuantityCalculator
        from SRC.structural.excel_export import export_to_excel

        unit = 0.01  # cm — Taziye
        for d in discovery.static_floors:
            is_foundation = d.kind == "foundation"
            spec = FloorSpec(
                name=d.name,
                dxf=d.dxf,
                kind=d.kind if d.kind != "typical" else "floor",
                column_height_m=0.0 if is_foundation else 3.0,
                include_raft=is_foundation,
                include_tie_beams=is_foundation,
                include_slab=not is_foundation,
                unit="cm",
            )
            c, b, s, r, sl, rb = process_floor(spec, unit)
            all_c.extend(c)
            all_b.extend(b)
            all_s.extend(s)
            all_r.extend(r)
            all_sl.extend(sl)
            all_rb.extend(rb)

        for lst in (all_c, all_b, all_s, all_r, all_sl, all_rb):
            for i, x in enumerate(lst, 1):
                x.id = i

        result = QuantityCalculator(default_column_height_cm=300.0).build(
            columns=all_c,
            beams=all_b,
            shear_walls=all_s,
            rafts=all_r,
            slabs=all_sl,
            rebars=all_rb,
            project_name=discovery.project_name,
        )
        export_to_excel(result, excel_path)
        print(f"\nExcel: {excel_path}")
    else:
        print("Statik DXF yok.")

    if discovery.mahal_files:
        try:
            from SRC.readers.mahal_reader import MahalReader
            mr = MahalReader()
            for mf in discovery.mahal_files:
                mahals = mr.read(mf)
                print(f"Mahal: {Path(mf).name} → {len(mahals)} kayıt")
        except Exception as e:
            print(f"Mahal uyarı: {e}")

    report = v.validate_structural(
        columns=all_c, beams=all_b, rafts=all_r, rebars=all_rb
    )
    report.report()

    log_path = out_dir / f"{discovery.project_name}_validator.txt"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"OK={report.ok}\n")
        for issue in report.issues:
            f.write(f"{issue.level}\t{issue.code}\t{issue.floor}\t{issue.message}\n")
    print(f"Validator log: {log_path}")
    sys.exit(0 if report.ok else 1)


if __name__ == "__main__":
    main()