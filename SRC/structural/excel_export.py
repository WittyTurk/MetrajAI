# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from SRC.structural.models import QuantityResult


def export_to_excel(result: QuantityResult, path: str) -> str:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        return _export_csv(result, path)

    wb = Workbook()
    bold = Font(bold=True)

    ws = wb.active
    ws.title = "Özet"
    ws.append(["Eleman", "Adet", "Beton (m³)", "Kalıp (m²)", "Demir (kg)"])
    for cell in ws[1]:
        cell.font = bold
    ws.append(["Kolon", len(result.columns), round(result.total_column_concrete_m3, 2), round(result.total_column_formwork_m2, 2), ""])
    ws.append(["Kiriş", len(result.beams), round(result.total_beam_concrete_m3, 2), round(result.total_beam_formwork_m2, 2), ""])
    ws.append(["Perde", len(result.shear_walls), round(result.total_shear_concrete_m3, 2), round(result.total_shear_formwork_m2, 2), ""])
    ws.append(["Döşeme", len(result.slabs), round(result.total_slab_concrete_m3, 2), round(result.total_slab_formwork_m2, 2), ""])
    ws.append(["Radye", len(result.rafts), round(result.total_raft_concrete_m3, 2), round(result.total_raft_formwork_m2, 2), ""])
    ws.append(["Demir", len(result.rebars), "", "", round(result.total_rebar_kg, 1)])
    ws.append(["TOPLAM", "", round(result.total_concrete_m3, 2), round(result.total_formwork_m2, 2), round(result.total_rebar_kg, 1)])

    ws2 = wb.create_sheet("Kolonlar")
    ws2.append(["ID", "Kat", "Marka", "Kesit", "H cm", "Beton m³", "Kalıp m²"])
    for c in result.columns:
        ws2.append([c.id, c.floor, c.mark or "", f"{c.section[0]:.0f}/{c.section[1]:.0f}",
                    c.height_cm, round(c.concrete_m3, 3), round(c.formwork_m2, 2)])

    ws3 = wb.create_sheet("Kirişler")
    ws3.append(["ID", "Kat", "Marka", "Kesit", "L m", "Beton m³", "Kalıp m²"])
    for b in result.beams:
        ws3.append([b.id, b.floor, b.mark or "", f"{b.section[0]:.0f}/{b.section[1]:.0f}",
                    round(b.length_m, 2), round(b.concrete_m3, 3), round(b.formwork_m2, 2)])

    ws4 = wb.create_sheet("Perdeler")
    ws4.append(["ID", "Kat", "t cm", "L m", "H cm", "Beton m³", "Kalıp m²"])
    for s in result.shear_walls:
        ws4.append([s.id, s.floor, s.thickness_cm, round(s.length_m, 2), s.height_cm,
                    round(s.concrete_m3, 3), round(s.formwork_m2, 2)])

    ws5 = wb.create_sheet("Döşemeler")
    ws5.append(["ID", "Kat", "Alan m²", "t cm", "Beton m³", "Kalıp m²"])
    for s in result.slabs:
        ws5.append([s.id, s.floor, round(s.area_m2, 2), s.thickness_cm,
                    round(s.concrete_m3, 3), round(s.formwork_m2, 2)])

    ws6 = wb.create_sheet("Radye")
    ws6.append(["ID", "Kat", "Alan m²", "t cm", "Beton m³", "Kalıp m²"])
    for r in result.rafts:
        ws6.append([r.id, r.floor, round(r.area_m2, 2), r.thickness_cm,
                    round(r.concrete_m3, 3), round(r.formwork_m2, 2)])

    ws7 = wb.create_sheet("Demir")
    ws7.append(["ID", "Kat", "Eleman", "Marka", "Ø mm", "Boy m", "Adet", "Toplam m", "kg", "Not"])
    for r in result.rebars:
        ws7.append([r.id, r.floor, r.element_type, r.element_mark, r.diameter_mm,
                    round(r.length_m, 2), r.count, round(r.total_length_m, 2),
                    round(r.weight_kg, 2), r.note])

    out = Path(path)
    if out.suffix.lower() != ".xlsx":
        out = out.with_suffix(".xlsx")
    wb.save(out)
    print(f"\nExcel kaydedildi: {out}")
    return str(out)


def _export_csv(result: QuantityResult, path: str) -> str:
    import csv
    out = Path(path).with_suffix(".csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Eleman", "Adet", "Beton_m3", "Kalip_m2", "Demir_kg"])
        w.writerow(["Kolon", len(result.columns), round(result.total_column_concrete_m3, 2), round(result.total_column_formwork_m2, 2), ""])
        w.writerow(["Kiriş", len(result.beams), round(result.total_beam_concrete_m3, 2), round(result.total_beam_formwork_m2, 2), ""])
        w.writerow(["Perde", len(result.shear_walls), round(result.total_shear_concrete_m3, 2), round(result.total_shear_formwork_m2, 2), ""])
        w.writerow(["Döşeme", len(result.slabs), round(result.total_slab_concrete_m3, 2), round(result.total_slab_formwork_m2, 2), ""])
        w.writerow(["Radye", len(result.rafts), round(result.total_raft_concrete_m3, 2), round(result.total_raft_formwork_m2, 2), ""])
        w.writerow(["Demir", len(result.rebars), "", "", round(result.total_rebar_kg, 1)])
        w.writerow(["TOPLAM", "", round(result.total_concrete_m3, 2), round(result.total_formwork_m2, 2), round(result.total_rebar_kg, 1)])
    print(f"\nCSV: {out}")
    return str(out)