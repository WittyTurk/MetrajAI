import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [payloadPath, outputPath, previewDir] = process.argv.slice(2);
if (!payloadPath || !outputPath) {
  throw new Error("Usage: build_report.mjs payload.json output.xlsx [preview-dir]");
}
const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
const workbook = Workbook.create();
const sheets = Object.fromEntries(
  [
    "Özet", "Kaynaklar", "Elemanlar", "Metraj", "Varsayımlar", "Uyarılar",
    "Poz Eşleştirme", "Birim Fiyatlar", "Teklif Senaryosu", "Teklif Özeti",
  ].map(
    (name) => [name, workbook.worksheets.add(name)],
  ),
);
const colors = {
  ink: "#172023", slate: "#394447", line: "#D9DEDB", accent: "#EDA34A",
  white: "#FFFFFF",
};
const headers = {
  fill: colors.ink,
  font: { bold: true, color: colors.white, size: 10 },
  verticalAlignment: "center",
};

function addTitle(sheet, title, subtitle, lastColumn) {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastColumn}1`).merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange(`A1:${lastColumn}1`).format = {
    fill: colors.ink, font: { bold: true, color: colors.white, size: 20 },
    verticalAlignment: "center",
  };
  sheet.getRange(`A2:${lastColumn}2`).merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A2:${lastColumn}2`).format = {
    fill: colors.slate,
    font: { color: "#DCE3E1", italic: true, size: 9 },
    verticalAlignment: "center",
  };
  sheet.getRange("1:1").format.rowHeight = 34;
  sheet.getRange("2:2").format.rowHeight = 22;
}

function addTable(sheet, headerRow, headerValues, bodyValues, lastColumn) {
  sheet.getRange(`A${headerRow}:${lastColumn}${headerRow}`).values = [headerValues];
  sheet.getRange(`A${headerRow}:${lastColumn}${headerRow}`).format = headers;
  sheet.getRange(`${headerRow}:${headerRow}`).format.rowHeight = 24;
  if (bodyValues.length) {
    sheet.getRangeByIndexes(headerRow, 0, bodyValues.length, headerValues.length).values =
      bodyValues;
    const endRow = headerRow + bodyValues.length;
    sheet.getRange(`A${headerRow + 1}:${lastColumn}${endRow}`).format = {
      fill: colors.white,
      font: { color: colors.ink, size: 9 },
      borders: { preset: "inside", style: "thin", color: colors.line },
      verticalAlignment: "center",
    };
  }
  sheet.freezePanes.freezeRows(headerRow);
}

const {
  sources, elements, quantities, assumptions, warnings, project,
  price_catalogs: priceCatalogs = [], price_items: priceItems = [],
  price_mappings: priceMappings = [], offers = [], validation_gates: validationGates = [],
} = payload;

{
  const sheet = sheets.Kaynaklar;
  addTitle(sheet, "KAYNAKLAR", "Değiştirilmeyen dosyalar ve SHA-256 kimlikleri", "M");
  const rows = sources.map((item) => [
    item.id, item.original_name, item.discipline, item.role, item.floor, item.revision,
    item.drawing_unit, item.detected_unit, item.unit_confirmed, item.sha256,
    item.size_bytes, item.stored_path, item.created_at,
  ]);
  addTable(sheet, 4, ["Kaynak ID", "Dosya", "Disiplin", "Pafta Rolü", "Kat", "Revizyon", "Onaylı Birim", "Algılanan Birim", "Birim Onayı", "SHA-256", "Bayt", "Proje İçi Yol", "Eklenme Zamanı"], rows, "M");
  [20, 28, 15, 15, 11, 11, 13, 15, 12, 44, 13, 30, 23].forEach(
    (width, index) => sheet.getRangeByIndexes(0, index, Math.max(rows.length + 4, 5), 1).format.columnWidth = width,
  );
  if (rows.length) sheet.getRange(`K5:K${rows.length + 4}`).format.numberFormat = "#,##0";
  if (rows.length) sheet.getRange(`M5:M${rows.length + 4}`).format.numberFormat = "yyyy-mm-dd hh:mm";
}

const elementRows = new Map();
{
  const sheet = sheets.Elemanlar;
  addTitle(sheet, "ELEMANLAR", "DXF geometrisi, ölçüler, güven ve mühendis kararı", "U");
  const rows = elements.map((item, index) => {
    elementRows.set(item.id, index + 5);
    const m = item.measurements;
    return [
      item.id, item.source_id, item.discipline, item.floor, item.element_type, item.layer,
      item.block_name, item.source_handle, item.confidence, item.review_status,
      m.width_m ?? null, m.depth_m ?? null, m.height_m ?? null, m.length_m ?? null,
      m.thickness_m ?? null, m.area_m2 ?? null, m.perimeter_m ?? null, m.count ?? null,
      m.diameter_mm ?? null, item.issues.join("; "), JSON.stringify(item.geometry.points),
    ];
  });
  addTable(sheet, 4, ["Eleman ID", "Kaynak ID", "Disiplin", "Kat", "Eleman Türü", "Katman", "Blok", "Handle", "Güven", "Onay Durumu", "Genişlik m", "Derinlik m", "Yükseklik m", "Uzunluk m", "Kalınlık m", "Alan m²", "Çevre m", "Adet", "Çap mm", "Sorunlar", "Geometri Noktaları"], rows, "U");
  [22, 22, 14, 10, 15, 18, 16, 11, 10, 14, 12, 12, 12, 12, 12, 12, 12, 10, 11, 30, 42].forEach(
    (width, index) => sheet.getRangeByIndexes(0, index, Math.max(rows.length + 4, 5), 1).format.columnWidth = width,
  );
  if (rows.length) {
    sheet.getRange(`I5:I${rows.length + 4}`).format.numberFormat = "0%";
    sheet.getRange(`K5:S${rows.length + 4}`).format.numberFormat = "0.000";
    sheet.getRange(`T5:U${rows.length + 4}`).format.wrapText = true;
  }
}

const assumptionRows = new Map();
{
  const sheet = sheets.Varsayımlar;
  addTitle(sheet, "VARSAYIMLAR", "Açık, sürümlü ve mühendis onaylı politikalar", "H");
  const rows = assumptions.map((item, index) => {
    assumptionRows.set(item.key, index + 5);
    return [item.id, item.key, item.value, item.unit, item.description, item.version, item.approved, item.created_at];
  });
  addTable(sheet, 4, ["Varsayım ID", "Anahtar", "Değer", "Birim", "Açıklama", "Sürüm", "Onay", "Zaman"], rows, "H");
  [22, 24, 15, 11, 45, 10, 10, 24].forEach(
    (width, index) => sheet.getRangeByIndexes(0, index, Math.max(rows.length + 4, 5), 1).format.columnWidth = width,
  );
  if (rows.length) sheet.getRange(`H5:H${rows.length + 4}`).format.numberFormat = "yyyy-mm-dd hh:mm";
}

const quantityRows = new Map();
{
  const sheet = sheets.Metraj;
  addTitle(sheet, "METRAJ", "Yalnız onaylı elemanlar; sarı sütunlar hücre formülüdür", "V");
  const header = ["Metraj ID", "Disiplin", "Kat", "Kategori", "Açıklama", "Birim", "Eleman ID", "Kaynak ID", "Genişlik", "Derinlik", "Yükseklik", "Uzunluk", "Kalınlık", "Alan", "Çevre", "Adet", "Çap", "Net Donatı", "İlave %", "Miktar", "Formül Açıklaması", "Onay"];
  addTable(sheet, 4, header, quantities.map((item, index) => {
    quantityRows.set(item.id, index + 5);
    return [item.id, item.discipline, item.floor, item.category, item.description, item.unit, item.element_id, item.source_id, null, null, null, null, null, null, null, null, null, null, null, null, item.formula, item.review_status];
  }), "V");
  const endRow = quantities.length + 4;
  quantities.forEach((item, index) => {
    const row = index + 5;
    const sourceRow = elementRows.get(item.element_id);
    if (!sourceRow) throw new Error(`Missing source element for ${item.id}`);
    sheet.getRange(`I${row}:Q${row}`).formulas = [[
      `='Elemanlar'!K${sourceRow}`, `='Elemanlar'!L${sourceRow}`,
      `='Elemanlar'!M${sourceRow}`, `='Elemanlar'!N${sourceRow}`,
      `='Elemanlar'!O${sourceRow}`, `='Elemanlar'!P${sourceRow}`,
      `='Elemanlar'!Q${sourceRow}`, `='Elemanlar'!R${sourceRow}`,
      `='Elemanlar'!S${sourceRow}`,
    ]];
    let formula;
    if (item.formula_key === "column:0") formula = `=I${row}*J${row}*K${row}`;
    else if (item.formula_key === "column:1") formula = `=2*(I${row}+J${row})*K${row}`;
    else if (item.formula_key === "beam:0") formula = `=I${row}*K${row}*L${row}`;
    else if (item.formula_key === "beam:1") formula = `=${Number(item.variables.formwork_area_m2)}`;
    else if (item.formula_key === "shear_wall:0") formula = `=M${row}*L${row}*K${row}`;
    else if (item.formula_key === "shear_wall:1") formula = `=2*L${row}*K${row}`;
    else if (["slab:0", "raft:0", "foundation:0"].includes(item.formula_key)) formula = `=N${row}*M${row}`;
    else if (item.formula_key === "slab:1") formula = `=N${row}`;
    else if (["raft:1", "foundation:1"].includes(item.formula_key)) formula = `=O${row}*M${row}`;
    else if (item.formula_key === "stair:0") formula = `=${Number(item.variables.plan_area_m2)}*SQRT(1+(${Number(item.variables.total_rise_m)}/${Number(item.variables.horizontal_run_m)})^2)*${Number(item.variables.waist_thickness_m)}`;
    else if (item.formula_key === "stair:6") formula = `=${Number(item.variables.plan_area_m2)}*SQRT(1+(${Number(item.variables.total_rise_m)}/${Number(item.variables.horizontal_run_m)})^2)`;
    else if (["stair:1", "stair:2", "stair:3", "stair:4", "stair:5"].includes(item.formula_key)) formula = `=${Number(item.quantity)}`;
    else if (item.formula_key === "rebar:0") formula = `=L${row}*P${row}*Q${row}^2/162`;
    else if (["rebar:1", "rebar:2", "rebar:3"].includes(item.formula_key)) {
      const assumptionKey = Object.keys(item.variables).find((key) => key.endsWith("_percent"));
      const assumptionRow = assumptionRows.get(assumptionKey);
      if (!assumptionRow) throw new Error(`Missing approved assumption ${assumptionKey}`);
      sheet.getRange(`R${row}`).formulas = [[`=SUMIFS($T$5:$T$${endRow},$G$5:$G$${endRow},G${row},$E$5:$E$${endRow},"Net donatı")`]];
      sheet.getRange(`S${row}`).formulas = [[`='Varsayımlar'!C${assumptionRow}`]];
      formula = `=R${row}*S${row}/100`;
    } else if (["wall:0", "landscape_linear:0", "pipe:0", "duct:0", "cable:0", "cable_tray:0"].includes(item.formula_key)) formula = `=L${row}`;
    else if (item.formula_key === "wall:1") formula = `=L${row}*K${row}`;
    else if (["room:0", "room:1", "landscape_area:0", "finish_area:0"].includes(item.formula_key)) formula = `=N${row}`;
    else if (item.formula_key === "room:2") formula = `=O${row}`;
    else formula = `=${Number(item.quantity)}`;
    sheet.getRange(`T${row}`).formulas = [[formula]];
  });
  [20, 13, 10, 13, 23, 9, 22, 22, 11, 11, 11, 11, 11, 11, 11, 9, 9, 13, 11, 14, 38, 12].forEach(
    (width, index) => sheet.getRangeByIndexes(0, index, Math.max(endRow, 5), 1).format.columnWidth = width,
  );
  if (quantities.length) {
    sheet.getRange(`I5:T${endRow}`).format.numberFormat = "#,##0.000";
    sheet.getRange(`T5:T${endRow}`).format = {
      fill: "#FFF0D9", font: { bold: true, color: colors.ink },
      numberFormat: "#,##0.000",
      borders: { preset: "all", style: "thin", color: "#E7C590" },
    };
  }
}

{
  const sheet = sheets.Uyarılar;
  addTitle(sheet, "UYARILAR", "Kesin sonuca girmeyen eksikler ve analiz tanıları", "G");
  const rows = warnings.map((item) => [item.severity, item.code, item.message, item.source_id, item.element_id, item.id, project.updated_at]);
  addTable(sheet, 4, ["Seviye", "Kod", "Açıklama", "Kaynak ID", "Eleman ID", "Uyarı ID", "Proje Zamanı"], rows, "G");
  [12, 27, 70, 22, 22, 22, 24].forEach(
    (width, index) => sheet.getRangeByIndexes(0, index, Math.max(rows.length + 4, 5), 1).format.columnWidth = width,
  );
  if (rows.length) sheet.getRange(`C5:C${rows.length + 4}`).format.wrapText = true;
  if (rows.length) sheet.getRange(`G5:G${rows.length + 4}`).format.numberFormat = "yyyy-mm-dd hh:mm";
}

const catalogById = new Map(priceCatalogs.map((item) => [item.id, item]));
const priceItemRows = new Map();
{
  const sheet = sheets["Birim Fiyatlar"];
  addTitle(sheet, "BİRİM FİYATLAR", "Resmî ve özel katalogların sürümlü yerel kopyaları", "K");
  const rows = priceItems.map((item, index) => {
    priceItemRows.set(item.id, index + 5);
    const catalog = catalogById.get(item.catalog_id) ?? {};
    return [
      item.id, item.catalog_id, catalog.name ?? "", catalog.year ?? "", item.code,
      item.description, item.unit, Number(item.unit_price), item.currency,
      catalog.sha256 ?? "", catalog.source_url ?? "",
    ];
  });
  addTable(sheet, 4, ["Fiyat ID", "Katalog ID", "Katalog", "Yıl", "Poz", "Açıklama", "Birim", "Birim Fiyat", "Para Birimi", "Kaynak SHA-256", "Kaynak URL"], rows, "K");
  [22, 22, 25, 9, 16, 60, 10, 16, 12, 44, 42].forEach(
    (width, index) => sheet.getRangeByIndexes(0, index, Math.max(rows.length + 4, 5), 1).format.columnWidth = width,
  );
  if (rows.length) sheet.getRange(`H5:H${rows.length + 4}`).format.numberFormat = "#,##0.00";
}

const mappingRows = new Map();
{
  const sheet = sheets["Poz Eşleştirme"];
  addTitle(sheet, "POZ EŞLEŞTİRME", "Mühendis onayı olmayan öneriler teklif toplamına girmez", "N");
  const rows = priceMappings.map((item, index) => {
    mappingRows.set(item.id, index + 5);
    const price = priceItems.find((candidate) => candidate.id === item.price_item_id) ?? {};
    return [
      item.id, item.quantity_line_id, item.price_item_id, price.code ?? "", item.status,
      item.confidence, item.reviewer, item.reason, null, null, null, null, null, null,
    ];
  });
  addTable(sheet, 4, ["Eşleşme ID", "Metraj ID", "Fiyat ID", "Poz", "Durum", "Güven", "Onaylayan", "Gerekçe", "Miktar", "Metraj Birimi", "Birim Fiyat", "Fiyat Birimi", "Para Birimi", "Doğrudan Tutar"], rows, "N");
  priceMappings.forEach((item, index) => {
    const row = index + 5;
    const quantityRow = quantityRows.get(item.quantity_line_id);
    const priceRow = priceItemRows.get(item.price_item_id);
    if (!quantityRow || !priceRow) return;
    sheet.getRange(`I${row}`).formulas = [[`='Metraj'!T${quantityRow}`]];
    sheet.getRange(`J${row}`).formulas = [[`='Metraj'!F${quantityRow}`]];
    sheet.getRange(`K${row}`).formulas = [[`='Birim Fiyatlar'!H${priceRow}`]];
    sheet.getRange(`L${row}`).formulas = [[`='Birim Fiyatlar'!G${priceRow}`]];
    sheet.getRange(`M${row}`).formulas = [[`='Birim Fiyatlar'!I${priceRow}`]];
    sheet.getRange(`N${row}`).formulas = [[`=IF(E${row}="approved",I${row}*K${row},0)`]];
  });
  [22, 22, 22, 16, 12, 10, 16, 40, 14, 13, 16, 13, 12, 18].forEach(
    (width, index) => sheet.getRangeByIndexes(0, index, Math.max(rows.length + 4, 5), 1).format.columnWidth = width,
  );
  if (rows.length) {
    sheet.getRange(`F5:F${rows.length + 4}`).format.numberFormat = "0%";
    sheet.getRange(`I5:I${rows.length + 4}`).format.numberFormat = "#,##0.000";
    sheet.getRange(`K5:K${rows.length + 4}`).format.numberFormat = "#,##0.00";
    sheet.getRange(`N5:N${rows.length + 4}`).format = {
      fill: "#FFF0D9", font: { bold: true, color: colors.ink }, numberFormat: "#,##0.00",
    };
  }
}

const scenarioAdjustmentRows = new Map();
{
  const sheet = sheets["Teklif Senaryosu"];
  addTitle(sheet, "TEKLİF SENARYOSU", "Oran, sabit tutar ve endeks kalemleri açık sıra ile uygulanır", "O");
  const rows = [];
  for (const offer of offers) {
    const scenario = offer.scenario;
    for (const adjustment of [...scenario.adjustments].sort((a, b) => a.order - b.order)) {
      const row = rows.length + 5;
      scenarioAdjustmentRows.set(`${scenario.id}|${adjustment.id}`, row);
      rows.push([
        scenario.id, scenario.name, scenario.currency, Number(scenario.exchange_rate),
        adjustment.order, adjustment.label, adjustment.kind, adjustment.base,
        Number(adjustment.value), adjustment.applicable, adjustment.source,
        adjustment.source_date, null, null, null,
      ]);
    }
  }
  addTable(sheet, 4, ["Senaryo ID", "Senaryo", "Para Birimi", "Kur", "Sıra", "Kalem", "Tür", "Matrah", "Değer", "Uygulanır", "Kaynak", "Kaynak Tarihi", "Matrah Tutarı", "Ayarlama", "Yürüyen Toplam"], rows, "O");
  rows.forEach((_, index) => {
    const row = index + 5;
    const direct = `SUM('Poz Eşleştirme'!$N$5:$N$${Math.max(priceMappings.length + 4, 5)})*D${row}`;
    const samePrevious = row > 5 ? `A${row - 1}=A${row}` : "FALSE";
    const previousAdjustment = row > 5 ? `N${row - 1}` : "0";
    const previousRunning = row > 5 ? `O${row - 1}` : direct;
    sheet.getRange(`M${row}`).formulas = [[`=IF(H${row}="direct_cost",${direct},IF(H${row}="previous_adjustment",IF(${samePrevious},${previousAdjustment},0),IF(${samePrevious},${previousRunning},${direct})))`]];
    sheet.getRange(`N${row}`).formulas = [[`=IF(J${row}<>TRUE,0,IF(G${row}="percent",M${row}*I${row}/100,IF(G${row}="index",M${row}*(I${row}-1),I${row})))`]];
    sheet.getRange(`O${row}`).formulas = [[`=IF(${samePrevious},${previousRunning}+N${row},${direct}+N${row})`]];
  });
  [22, 24, 12, 11, 9, 25, 12, 20, 13, 12, 35, 15, 17, 17, 19].forEach(
    (width, index) => sheet.getRangeByIndexes(0, index, Math.max(rows.length + 4, 5), 1).format.columnWidth = width,
  );
  if (rows.length) sheet.getRange(`D5:O${rows.length + 4}`).format.numberFormat = "#,##0.00";
}

{
  const sheet = sheets["Teklif Özeti"];
  addTitle(sheet, "TEKLİF ÖZETİ", "Metraj, onaylı pozlar ve açık ticari ayarlamalar", "H");
  const rows = offers.map((offer) => [
    offer.scenario.id, offer.scenario.name, offer.scenario.currency,
    Number(offer.scenario.exchange_rate), null, null, null,
    offer.scenario.approved ? "Onaylı" : "Taslak",
  ]);
  addTable(sheet, 4, ["Senaryo ID", "Senaryo", "Para Birimi", "Kur", "Doğrudan Maliyet", "Ayarlamalar", "Genel Toplam", "Durum"], rows, "H");
  offers.forEach((offer, index) => {
    const row = index + 5;
    const direct = `SUM('Poz Eşleştirme'!$N$5:$N$${Math.max(priceMappings.length + 4, 5)})*D${row}`;
    const adjustmentRows = [...offer.scenario.adjustments]
      .map((item) => scenarioAdjustmentRows.get(`${offer.scenario.id}|${item.id}`))
      .filter(Boolean);
    sheet.getRange(`E${row}`).formulas = [[`=${direct}`]];
    sheet.getRange(`F${row}`).formulas = [[adjustmentRows.length ? `=SUM('Teklif Senaryosu'!N${Math.min(...adjustmentRows)}:N${Math.max(...adjustmentRows)})` : "=0"]];
    sheet.getRange(`G${row}`).formulas = [[`=E${row}+F${row}`]];
  });
  [22, 28, 13, 11, 20, 18, 20, 12].forEach(
    (width, index) => sheet.getRangeByIndexes(0, index, Math.max(rows.length + 4, 5), 1).format.columnWidth = width,
  );
  if (rows.length) sheet.getRange(`D5:G${rows.length + 4}`).format.numberFormat = "#,##0.00";
  const gateStart = Math.max(rows.length + 7, 10);
  sheet.getRange(`A${gateStart}:D${gateStart}`).values = [["DİSİPLİN GÜVEN KAPILARI", "DURUM", "KÜÇÜK PROJE", "KARMAŞIK PROJE"]];
  sheet.getRange(`A${gateStart}:D${gateStart}`).format = headers;
  if (validationGates.length) {
    sheet.getRangeByIndexes(gateStart, 0, validationGates.length, 4).values = validationGates.map((gate) => [gate.discipline, gate.state, gate.small_project_approved, gate.complex_project_approved]);
  }
}

{
  const sheet = sheets.Özet;
  addTitle(sheet, "METRAJAI · KESİN METRAJ ÖZETİ", `${project.name} · yalnız onaylı elemanlar`, "F");
  sheet.getRange("A4:F4").values = [["Disiplin", "Kategori", "Birim", "Kesin Miktar", "Kaynak Satır", "Durum"]];
  sheet.getRange("A4:F4").format = headers;
  const combos = [...new Map(quantities.map((item) => [`${item.discipline}|${item.category}|${item.unit}`, [item.discipline, item.category, item.unit]])).values()];
  const metrajEnd = Math.max(quantities.length + 4, 5);
  combos.forEach((combo, index) => {
    const row = index + 5;
    sheet.getRange(`A${row}:C${row}`).values = [[...combo]];
    sheet.getRange(`D${row}`).formulas = [[`=SUMIFS('Metraj'!$T$5:$T$${metrajEnd},'Metraj'!$B$5:$B$${metrajEnd},A${row},'Metraj'!$D$5:$D$${metrajEnd},B${row},'Metraj'!$F$5:$F$${metrajEnd},C${row})`]];
    sheet.getRange(`E${row}`).formulas = [[`=COUNTIFS('Metraj'!$B$5:$B$${metrajEnd},A${row},'Metraj'!$D$5:$D$${metrajEnd},B${row},'Metraj'!$F$5:$F$${metrajEnd},C${row})`]];
    sheet.getRange(`F${row}`).values = [["Mühendis onaylı"]];
  });
  const comboEnd = Math.max(combos.length + 4, 5);
  if (combos.length) {
    sheet.getRange(`A5:F${comboEnd}`).format = {
      fill: colors.white, font: { color: colors.ink, size: 10 },
      borders: { preset: "inside", style: "thin", color: colors.line },
    };
    sheet.getRange(`D5:D${comboEnd}`).format = {
      fill: "#FFF0D9", font: { bold: true, color: colors.ink },
      numberFormat: "#,##0.000",
    };
  }
  const elementEnd = Math.max(elements.length + 4, 5);
  sheet.getRange("A12:B12").values = [["KONTROL NOKTALARI", "DEĞER"]];
  sheet.getRange("A12:B12").format = headers;
  sheet.getRange("A13:A17").values = [["Kaynak dosya"], ["Tespit edilen eleman"], ["Onaylı eleman"], ["Karar bekleyen"], ["Hariç tutulan"]];
  sheet.getRange("B13").formulas = [[`=COUNTA('Kaynaklar'!$A$5:$A$${Math.max(sources.length + 4, 5)})`]];
  sheet.getRange("B14").formulas = [[`=COUNTA('Elemanlar'!$A$5:$A$${elementEnd})`]];
  sheet.getRange("B15").formulas = [[`=COUNTIF('Elemanlar'!$J$5:$J$${elementEnd},"accepted")`]];
  sheet.getRange("B16").formulas = [[`=COUNTIF('Elemanlar'!$J$5:$J$${elementEnd},"pending")+COUNTIF('Elemanlar'!$J$5:$J$${elementEnd},"needs_review")`]];
  sheet.getRange("B17").formulas = [[`=COUNTIF('Elemanlar'!$J$5:$J$${elementEnd},"rejected")`]];
  sheet.getRange("A13:B17").format = {
    fill: colors.white, font: { color: colors.ink, size: 10 },
    borders: { preset: "all", style: "thin", color: colors.line },
  };
  sheet.getRange("D12:F12").merge();
  sheet.getRange("D12").values = [["HESAP GÜVENLİĞİ"]];
  sheet.getRange("D12:F12").format = headers;
  sheet.getRange("D13:F17").merge();
  sheet.getRange("D13").values = [["Eksik birim, kalınlık, kat yüksekliği veya donatı bilgisi kesin toplama sessizce girmez. Metraj sayfasındaki sarı hücreler kaynak eleman ölçülerine bağlı Excel formülleridir."]];
  sheet.getRange("D13:F17").format = {
    fill: "#E7F2EC", font: { color: "#285D47", bold: true, size: 10 },
    wrapText: true, verticalAlignment: "center", horizontalAlignment: "left",
  };
  [20, 20, 11, 18, 14, 19].forEach(
    (width, index) => sheet.getRangeByIndexes(0, index, 18, 1).format.columnWidth = width,
  );
  sheet.freezePanes.freezeRows(4);
}

for (const sheet of Object.values(sheets)) {
  const used = sheet.getUsedRange();
  if (used) used.format.autofitRows();
}

if (previewDir) {
  await fs.mkdir(previewDir, { recursive: true });
  for (const name of Object.keys(sheets)) {
    const preview = await workbook.render({
      sheetName: name, autoCrop: "all", scale: 1.4, format: "png",
    });
    await fs.writeFile(
      path.join(previewDir, `${name}.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }
  const check = await workbook.inspect({
    kind: "table", range: "Özet!A1:F17", include: "values,formulas",
    tableMaxRows: 20, tableMaxCols: 8, maxChars: 6000,
  });
  console.log(check.ndjson);
  const errors = await workbook.inspect({
    kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "final formula error scan",
  });
  console.log(errors.ndjson);
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ output: outputPath, sheets: Object.keys(sheets) }));
