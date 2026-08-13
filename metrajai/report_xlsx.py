from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .workspace import ProjectWorkspace

INK = "172023"
SLATE = "394447"
ACCENT = "FFF0D9"
WHITE = "FFFFFF"


def _title(sheet, title: str, subtitle: str, columns: int) -> None:
    sheet.sheet_view.showGridLines = False
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=columns)
    sheet.cell(1, 1, title)
    sheet.cell(1, 1).font = Font(bold=True, color=WHITE, size=18)
    sheet.cell(1, 1).fill = PatternFill("solid", fgColor=INK)
    sheet.cell(1, 1).alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 32
    sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=columns)
    sheet.cell(2, 1, subtitle)
    sheet.cell(2, 1).font = Font(italic=True, color="DCE3E1", size=9)
    sheet.cell(2, 1).fill = PatternFill("solid", fgColor=SLATE)
    sheet.row_dimensions[2].height = 22


def _table(sheet, headers: list[str], rows: list[list[Any]]) -> None:
    for column, value in enumerate(headers, start=1):
        cell = sheet.cell(4, column, value)
        cell.font = Font(bold=True, color=WHITE, size=9)
        cell.fill = PatternFill("solid", fgColor=INK)
        cell.alignment = Alignment(vertical="center")
    for row_index, values in enumerate(rows, start=5):
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row_index, column, value)
            cell.alignment = Alignment(vertical="center", wrap_text=column > 8)
    sheet.freeze_panes = "A5"
    sheet.auto_filter.ref = f"A4:{get_column_letter(len(headers))}{max(4, len(rows) + 4)}"


def _fit(sheet, minimum: int = 10, maximum: int = 48) -> None:
    for column_cells in sheet.columns:
        values = [
            str(cell.value or "")
            for cell in column_cells
            if cell.coordinate not in sheet.merged_cells
        ]
        width = max((len(value) for value in values), default=minimum) + 2
        sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = min(
            maximum, max(minimum, width)
        )


def _quantity_formula(line, row: int, assumption_rows: dict[str, int], end_row: int) -> str:
    key = line.formula_key
    values = line.variables
    if key == "column:0":
        return f"=I{row}*J{row}*K{row}"
    if key == "column:1":
        return f"=2*(I{row}+J{row})*K{row}"
    if key == "beam:0":
        return f"=I{row}*K{row}*L{row}"
    if key == "beam:1":
        return f"={values['formwork_area_m2']}"
    if key == "shear_wall:0":
        return f"=M{row}*L{row}*K{row}"
    if key == "shear_wall:1":
        return f"=2*L{row}*K{row}"
    if key in {"slab:0", "raft:0", "foundation:0"}:
        return f"=N{row}*M{row}"
    if key == "slab:1":
        return f"=N{row}"
    if key in {"raft:1", "foundation:1"}:
        return f"=O{row}*M{row}"
    if key == "stair:0":
        return (
            f"={values['plan_area_m2']}*SQRT(1+"
            f"({values['total_rise_m']}/{values['horizontal_run_m']})^2)"
            f"*{values['waist_thickness_m']}"
        )
    if key == "stair:6":
        return (
            f"={values['plan_area_m2']}*SQRT(1+"
            f"({values['total_rise_m']}/{values['horizontal_run_m']})^2)"
        )
    if key == "rebar:0":
        return f"=L{row}*P{row}*Q{row}^2/162"
    if key in {"rebar:1", "rebar:2", "rebar:3"}:
        assumption_key = next(name for name in values if name.endswith("_percent"))
        assumption_row = assumption_rows[assumption_key]
        return (
            f"=SUMIFS($T$5:$T${end_row},$G$5:$G${end_row},G{row},"
            f"$E$5:$E${end_row},\"Net donatı\")*'Varsayımlar'!C{assumption_row}/100"
        )
    if key in {
        "wall:0",
        "landscape_linear:0",
        "pipe:0",
        "duct:0",
        "cable:0",
        "cable_tray:0",
    }:
        return f"=L{row}"
    if key == "wall:1":
        return f"={values['net_area_m2']}"
    if key == "wall:2":
        return f"=L{row}*K{row}*M{row}"
    if key == "finish_area:0":
        return f"={values['net_area_m2']}"
    if key in {"room:0", "room:1", "landscape_area:0"}:
        return f"=N{row}"
    if key == "room:2":
        return f"=O{row}"
    return f"={line.quantity}"


def export_openpyxl_report(workspace: ProjectWorkspace, target: Path) -> Path:
    item: Any
    sources = workspace.list_sources()
    elements = workspace.list_elements()
    quantities = workspace.list_quantities()
    assumptions = workspace.list_assumptions()
    warnings = workspace.list_warnings()
    catalogs = workspace.list_price_catalogs()
    prices = workspace.list_price_items()
    mappings = workspace.list_price_mappings()
    offers = workspace.list_offer_scenarios()
    reviews = workspace.list_reviews()
    evidence = workspace.list_element_evidence()
    overrides = workspace.list_manual_overrides()
    architectural_assignments = workspace.list_architectural_assignments()
    review_by_element = {item.element_id: item for item in reviews}
    evidence_by_element: dict[str, list[Any]] = {}
    for item in evidence:
        evidence_by_element.setdefault(item.element_id, []).append(item)
    override_by_element: dict[str, list[Any]] = {}
    for item in overrides:
        override_by_element.setdefault(item.element_id, []).append(item)

    workbook = Workbook()
    workbook.remove(workbook.active)
    names = [
        "Özet",
        "Kaynaklar",
        "Elemanlar",
        "Metraj",
        "Varsayımlar",
        "Uyarılar",
        "Poz Eşleştirme",
        "Birim Fiyatlar",
        "Teklif Senaryosu",
        "Teklif Özeti",
        "Mimari Kırılım",
    ]
    sheets = {name: workbook.create_sheet(name) for name in names}

    source_rows = [
        [
            item.id,
            item.original_name,
            item.source_format.value,
            item.discipline.value,
            item.role,
            item.floor,
            item.floor_kind.value,
            item.sheet_kind.value,
            item.revision,
            item.drawing_unit.value,
            item.detected_unit.value,
            item.unit_confirmed,
            item.calibration_status.value,
            item.sha256,
            item.stored_path,
        ]
        for item in sources
    ]
    source_headers = [
        "Kaynak ID",
        "Dosya",
        "Biçim",
        "Disiplin",
        "Rol",
        "Kat",
        "Kat Türü",
        "Pafta Türü",
        "Revizyon",
        "Birim",
        "Algılanan Birim",
        "Birim Onayı",
        "Kalibrasyon",
        "SHA-256",
        "Proje İçi Yol",
    ]
    _title(
        sheets["Kaynaklar"],
        "KAYNAKLAR",
        "Değiştirilmeyen kaynaklar ve kimlikleri",
        len(source_headers),
    )
    _table(sheets["Kaynaklar"], source_headers, source_rows)

    element_rows: dict[str, int] = {}
    element_values = []
    for index, item in enumerate(elements, start=5):
        element_rows[item.id] = index
        measurement = item.measurements
        review = review_by_element.get(item.id)
        traces = evidence_by_element.get(item.id, [])
        manual = override_by_element.get(item.id, [])
        element_values.append(
            [
                item.id,
                item.source_id,
                item.discipline.value,
                item.floor,
                item.element_type,
                item.layer,
                item.block_name,
                item.source_handle,
                item.confidence,
                item.review_status.value,
                measurement.get("width_m"),
                measurement.get("depth_m"),
                measurement.get("height_m"),
                measurement.get("length_m"),
                measurement.get("thickness_m"),
                measurement.get("area_m2"),
                measurement.get("perimeter_m"),
                measurement.get("count"),
                measurement.get("diameter_mm"),
                "; ".join(item.issues),
                review.reviewer if review else "",
                review.reason if review else "",
                json.dumps([value.model_dump(mode="json") for value in traces], ensure_ascii=False),
                json.dumps([value.model_dump(mode="json") for value in manual], ensure_ascii=False),
            ]
        )
    element_headers = [
        "Eleman ID",
        "Kaynak ID",
        "Disiplin",
        "Kat",
        "Eleman Türü",
        "Katman",
        "Blok",
        "Handle/Sayfa",
        "Güven",
        "Karar",
        "Genişlik",
        "Derinlik",
        "Yükseklik",
        "Uzunluk",
        "Kalınlık",
        "Alan",
        "Çevre",
        "Adet",
        "Çap",
        "Sorunlar",
        "Onaylayan",
        "Gerekçe",
        "Kanıt",
        "Manuel Değişiklik",
    ]
    _title(
        sheets["Elemanlar"],
        "ELEMANLAR",
        "Geometri, ölçü, kanıt ve mühendis kararı",
        len(element_headers),
    )
    _table(sheets["Elemanlar"], element_headers, element_values)

    assignments_by_subject: dict[str, list[Any]] = {}
    for item in architectural_assignments:
        assignments_by_subject.setdefault(item.subject_element_id, []).append(item)
    architectural_values: list[list[Any]] = []
    architectural_elements = [
        item
        for item in elements
        if item.discipline.value == "architectural"
        and item.element_type in {"room", "wall", "door", "window", "finish_area"}
    ]
    for row, item in enumerate(architectural_elements, start=5):
        measurement = item.measurements
        properties = item.properties
        gross = measurement.get(
            "gross_area_m2",
            measurement.get("opening_area_m2", measurement.get("area_m2")),
        )
        opening = measurement.get("opening_area_m2", 0.0)
        architectural_values.append(
            [
                item.id,
                item.element_type,
                item.floor,
                properties.get("room_code", ""),
                properties.get("room_name", ""),
                properties.get("surface_type", ""),
                properties.get("material", properties.get("opening_material", "")),
                gross,
                opening,
                None,
                "m²" if gross is not None else "adet",
                properties.get("host_wall_id", ""),
                "; ".join(str(value) for value in properties.get("adjacent_room_ids", [])),
                item.source_id,
                item.source_handle,
                item.review_status.value,
                properties.get("calculation_policy", ""),
                json.dumps(
                    [
                        value.model_dump(mode="json")
                        for value in assignments_by_subject.get(item.id, [])
                    ],
                    ensure_ascii=False,
                ),
            ]
        )
        if gross is not None:
            architectural_values[-1][9] = f"=MAX(0,H{row}-I{row})"
    architectural_headers = [
        "Eleman ID",
        "Tür",
        "Kat",
        "Mahal Kodu",
        "Mahal Adı",
        "Yüzey",
        "Malzeme/Tip",
        "Brüt Alan",
        "Açıklık Alanı",
        "Net Alan",
        "Birim",
        "Duvar ID",
        "Komşu Mahaller",
        "Kaynak ID",
        "Handle/Satır",
        "Onay",
        "Hesap Politikası",
        "İlişki Kararları",
    ]
    _title(
        sheets["Mimari Kırılım"],
        "MİMARİ KIRILIM",
        "Mahal ve malzeme bazında brüt alan − doğrulanmış açıklık = net alan",
        len(architectural_headers),
    )
    _table(sheets["Mimari Kırılım"], architectural_headers, architectural_values)
    for row in range(5, 5 + len(architectural_values)):
        sheets["Mimari Kırılım"].cell(row, 10).fill = PatternFill("solid", fgColor=ACCENT)

    assumption_rows: dict[str, int] = {}
    assumption_values = []
    for index, item in enumerate(assumptions, start=5):
        assumption_rows[item.key] = index
        assumption_values.append(
            [
                item.id,
                item.key,
                item.value,
                item.unit,
                item.description,
                item.version,
                item.approved,
            ]
        )
    assumption_headers = ["ID", "Anahtar", "Değer", "Birim", "Açıklama", "Sürüm", "Onay"]
    _title(
        sheets["Varsayımlar"],
        "VARSAYIMLAR",
        "Açık ve sürümlü hesap politikaları",
        len(assumption_headers),
    )
    _table(sheets["Varsayımlar"], assumption_headers, assumption_values)

    quantity_headers = [
        "Metraj ID",
        "Disiplin",
        "Kat",
        "Kategori",
        "Açıklama",
        "Birim",
        "Eleman ID",
        "Kaynak ID",
        "Genişlik",
        "Derinlik",
        "Yükseklik",
        "Uzunluk",
        "Kalınlık",
        "Alan",
        "Çevre",
        "Adet",
        "Çap",
        "Net Donatı",
        "İlave %",
        "Miktar",
        "Formül Açıklaması",
        "Onay",
    ]
    quantity_values = []
    for item in quantities:
        quantity_values.append(
            [
                item.id,
                item.discipline.value,
                item.floor,
                item.category,
                item.description,
                item.unit,
                item.element_id,
                item.source_id,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                item.formula,
                item.review_status.value,
            ]
        )
    _title(
        sheets["Metraj"],
        "METRAJ",
        "Yalnız onaylı elemanlar; sarı hücreler formüldür",
        len(quantity_headers),
    )
    _table(sheets["Metraj"], quantity_headers, quantity_values)
    end_row = max(5, len(quantities) + 4)
    quantity_rows: dict[str, int] = {}
    for row, item in enumerate(quantities, start=5):
        quantity_rows[item.id] = row
        source_row = element_rows[item.element_id]
        for column, source_column in zip(range(9, 18), range(11, 20), strict=True):
            sheets["Metraj"].cell(
                row, column, f"='Elemanlar'!{get_column_letter(source_column)}{source_row}"
            )
        amount = sheets["Metraj"].cell(
            row, 20, _quantity_formula(item, row, assumption_rows, end_row)
        )
        amount.fill = PatternFill("solid", fgColor=ACCENT)
        amount.font = Font(bold=True, color=INK)

    warning_headers = ["Seviye", "Kod", "Açıklama", "Kaynak ID", "Eleman ID", "Uyarı ID"]
    _title(sheets["Uyarılar"], "UYARILAR", "Eksikler ve analiz tanıları", len(warning_headers))
    _table(
        sheets["Uyarılar"],
        warning_headers,
        [
            [item.severity, item.code, item.message, item.source_id, item.element_id, item.id]
            for item in warnings
        ],
    )

    catalog_by_id = {item.id: item for item in catalogs}
    price_rows: dict[str, int] = {}
    price_values = []
    for index, item in enumerate(prices, start=5):
        price_rows[item.id] = index
        catalog = catalog_by_id[item.catalog_id]
        price_values.append(
            [
                item.id,
                item.catalog_id,
                catalog.name,
                catalog.year,
                item.code,
                item.description,
                item.unit,
                float(item.unit_price),
                item.currency,
                catalog.sha256,
                catalog.source_url,
            ]
        )
    price_headers = [
        "Fiyat ID",
        "Katalog ID",
        "Katalog",
        "Yıl",
        "Poz",
        "Açıklama",
        "Birim",
        "Birim Fiyat",
        "Para Birimi",
        "Kaynak SHA-256",
        "Kaynak URL",
    ]
    _title(
        sheets["Birim Fiyatlar"],
        "BİRİM FİYATLAR",
        "Sürümlü resmî ve özel kataloglar",
        len(price_headers),
    )
    _table(sheets["Birim Fiyatlar"], price_headers, price_values)

    mapping_headers = [
        "Eşleşme ID",
        "Metraj ID",
        "Fiyat ID",
        "Poz",
        "Durum",
        "Güven",
        "Onaylayan",
        "Gerekçe",
        "Miktar",
        "Metraj Birimi",
        "Birim Fiyat",
        "Fiyat Birimi",
        "Para Birimi",
        "Doğrudan Tutar",
    ]
    mapping_values = []
    for item in mappings:
        price = next(value for value in prices if value.id == item.price_item_id)
        mapping_values.append(
            [
                item.id,
                item.quantity_line_id,
                item.price_item_id,
                price.code,
                item.status.value,
                item.confidence,
                item.reviewer,
                item.reason,
                None,
                None,
                None,
                None,
                None,
                None,
            ]
        )
    _title(
        sheets["Poz Eşleştirme"],
        "POZ EŞLEŞTİRME",
        "Yalnız onaylı eşleşmeler teklife girer",
        len(mapping_headers),
    )
    _table(sheets["Poz Eşleştirme"], mapping_headers, mapping_values)
    for row, item in enumerate(mappings, start=5):
        quantity_row = quantity_rows.get(item.quantity_line_id)
        price_row = price_rows.get(item.price_item_id)
        if quantity_row is None or price_row is None:
            continue
        sheets["Poz Eşleştirme"].cell(row, 9, f"='Metraj'!T{quantity_row}")
        sheets["Poz Eşleştirme"].cell(row, 10, f"='Metraj'!F{quantity_row}")
        sheets["Poz Eşleştirme"].cell(row, 11, f"='Birim Fiyatlar'!H{price_row}")
        sheets["Poz Eşleştirme"].cell(row, 12, f"='Birim Fiyatlar'!G{price_row}")
        sheets["Poz Eşleştirme"].cell(row, 13, f"='Birim Fiyatlar'!I{price_row}")
        sheets["Poz Eşleştirme"].cell(row, 14, f'=IF(E{row}="approved",I{row}*K{row},0)')

    scenario_headers = [
        "Senaryo ID",
        "Senaryo",
        "Para Birimi",
        "Kur",
        "Sıra",
        "Kalem",
        "Tür",
        "Matrah",
        "Değer",
        "Uygulanır",
        "Kaynak",
        "Kaynak Tarihi",
        "Matrah Tutarı",
        "Ayarlama",
        "Yürüyen Toplam",
    ]
    scenario_values: list[list[Any]] = []
    scenario_row_ranges: dict[str, tuple[int, int]] = {}
    for scenario in offers:
        start = len(scenario_values) + 5
        for item in sorted(scenario.adjustments, key=lambda value: value.order):
            scenario_values.append(
                [
                    scenario.id,
                    scenario.name,
                    scenario.currency,
                    float(scenario.exchange_rate),
                    item.order,
                    item.label,
                    item.kind.value,
                    item.base.value,
                    float(item.value),
                    item.applicable,
                    item.source,
                    item.source_date,
                    None,
                    None,
                    None,
                ]
            )
        if scenario.adjustments:
            scenario_row_ranges[scenario.id] = (start, len(scenario_values) + 4)
    _title(
        sheets["Teklif Senaryosu"],
        "TEKLİF SENARYOSU",
        "Sıralı ticari ayarlamalar",
        len(scenario_headers),
    )
    _table(sheets["Teklif Senaryosu"], scenario_headers, scenario_values)
    mapping_end = max(5, len(mappings) + 4)
    for row in range(5, len(scenario_values) + 5):
        direct = f"SUM('Poz Eşleştirme'!$N$5:$N${mapping_end})*D{row}"
        same = f"A{row - 1}=A{row}" if row > 5 else "FALSE"
        previous_adjustment = f"N{row - 1}" if row > 5 else "0"
        previous_running = f"O{row - 1}" if row > 5 else direct
        sheets["Teklif Senaryosu"].cell(
            row,
            13,
            f'=IF(H{row}="direct_cost",{direct},IF(H{row}="previous_adjustment",IF({same},{previous_adjustment},0),IF({same},{previous_running},{direct})))',
        )
        sheets["Teklif Senaryosu"].cell(
            row,
            14,
            f'=IF(J{row}<>TRUE,0,IF(G{row}="percent",M{row}*I{row}/100,IF(G{row}="index",M{row}*(I{row}-1),I{row})))',
        )
        sheets["Teklif Senaryosu"].cell(
            row, 15, f"=IF({same},{previous_running}+N{row},{direct}+N{row})"
        )

    offer_headers = [
        "Senaryo ID",
        "Senaryo",
        "Para Birimi",
        "Kur",
        "Doğrudan Maliyet",
        "Ayarlamalar",
        "Genel Toplam",
        "Durum",
    ]
    offer_values = [
        [
            item.id,
            item.name,
            item.currency,
            float(item.exchange_rate),
            None,
            None,
            None,
            "Onaylı" if item.approved else "Taslak",
        ]
        for item in offers
    ]
    _title(
        sheets["Teklif Özeti"],
        "TEKLİF ÖZETİ",
        "Onaylı poz ve açık ticari ayarlamalar",
        len(offer_headers),
    )
    _table(sheets["Teklif Özeti"], offer_headers, offer_values)
    for row, scenario in enumerate(offers, start=5):
        direct = f"SUM('Poz Eşleştirme'!$N$5:$N${mapping_end})*D{row}"
        sheets["Teklif Özeti"].cell(row, 5, f"={direct}")
        row_range = scenario_row_ranges.get(scenario.id)
        sheets["Teklif Özeti"].cell(
            row,
            6,
            f"=SUM('Teklif Senaryosu'!N{row_range[0]}:N{row_range[1]})" if row_range else "=0",
        )
        sheets["Teklif Özeti"].cell(row, 7, f"=E{row}+F{row}")

    totals: dict[tuple[str, str, str], list[int]] = {}
    for row, item in enumerate(quantities, start=5):
        totals.setdefault((item.discipline.value, item.category, item.unit), []).append(row)
    summary_headers = ["Disiplin", "Kategori", "Birim", "Kesin Miktar", "Kaynak Satır", "Durum"]
    summary_values = [[*key, None, len(rows), "Mühendis onaylı"] for key, rows in totals.items()]
    _title(
        sheets["Özet"],
        "METRAJAI · KESİN METRAJ ÖZETİ",
        f"{workspace.manifest.name} · yalnız onaylı elemanlar",
        len(summary_headers),
    )
    _table(sheets["Özet"], summary_headers, summary_values)
    for row in range(5, len(summary_values) + 5):
        sheets["Özet"].cell(
            row,
            4,
            f"=SUMIFS('Metraj'!$T$5:$T${end_row},'Metraj'!$B$5:$B${end_row},A{row},'Metraj'!$D$5:$D${end_row},B{row},'Metraj'!$F$5:$F${end_row},C{row})",
        )

    for sheet in sheets.values():
        _fit(sheet)
    target.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(target)
    workbook.close()
    return target
