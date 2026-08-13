from __future__ import annotations

import hashlib
import math
import unicodedata
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .contracts import (
    AdjustmentBase,
    AdjustmentKind,
    CostLine,
    MappingStatus,
    OfferScenario,
    PriceCatalog,
    PriceItem,
    PriceMapping,
    QuantityLine,
)

MONEY = Decimal("0.01")


class CatalogImportError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.replace("ı", "i")
    return " ".join(text.casefold().replace("_", " ").split())


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return Decimal(str(value))
    text = str(value).strip().replace("₺", "").replace("TL", "").strip()
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except Exception as exc:  # Decimal raises several concrete parse errors.
        raise CatalogImportError(f"Geçersiz birim fiyat: {value}") from exc


def _read_rows(path: Path) -> list[list[Any]]:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise CatalogImportError("XLSX desteği için openpyxl paketlenmemiş") from exc
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook[workbook.sheetnames[0]]
            return [list(row) for row in sheet.iter_rows(values_only=True)]
        finally:
            workbook.close()
    if suffix == ".xls":
        try:
            import xlrd
        except ImportError as exc:
            raise CatalogImportError("Eski XLS desteği için xlrd paketlenmemiş") from exc
        workbook = xlrd.open_workbook(path, on_demand=True)
        try:
            sheet = workbook.sheet_by_index(0)
            return [sheet.row_values(index) for index in range(sheet.nrows)]
        finally:
            workbook.release_resources()
    raise CatalogImportError("Fiyat kataloğu XLSX veya XLS olmalıdır")


def read_spreadsheet_rows(path: str | Path) -> list[list[Any]]:
    return _read_rows(Path(path).expanduser().resolve())


HEADER_ALIASES = {
    "code": {"poz", "poz no", "poz numarasi", "code", "item code"},
    "description": {
        "imalat",
        "aciklama",
        "poz aciklamasi",
        "tanim",
        "description",
    },
    "unit": {"birim", "unit"},
    "price": {"birim fiyat", "birim fiyati", "fiyat", "unit price", "price"},
}


def _header_mapping(rows: list[list[Any]]) -> tuple[int, dict[str, int]]:
    best: tuple[int, dict[str, int]] | None = None
    for row_index, row in enumerate(rows[:30]):
        mapping: dict[str, int] = {}
        for column, value in enumerate(row):
            normalized = _normalize(value)
            for key, aliases in HEADER_ALIASES.items():
                if normalized in aliases:
                    mapping.setdefault(key, column)
        if {"code", "description", "unit", "price"}.issubset(mapping):
            return row_index, mapping
        if best is None or len(mapping) > len(best[1]):
            best = row_index, mapping
    found = ", ".join(sorted(best[1])) if best else "yok"
    raise CatalogImportError(
        "Poz, açıklama, birim ve birim fiyat sütunları bulunamadı; bulunan alanlar: " + found
    )


def import_price_catalog_file(
    path: str | Path,
    *,
    project_id: str,
    name: str,
    year: int,
    version: str,
    currency: str = "TRY",
    is_official: bool = False,
    source_url: str = "",
) -> tuple[PriceCatalog, list[PriceItem]]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    rows = _read_rows(source)
    header_row, columns = _header_mapping(rows)
    catalog = PriceCatalog(
        project_id=project_id,
        name=name.strip() or source.stem,
        year=year,
        version=version.strip() or "1",
        currency=currency.upper(),
        source_name=source.name,
        source_url=source_url,
        sha256=_sha256(source),
        is_official=is_official,
    )
    items: list[PriceItem] = []
    seen: set[str] = set()
    for row_number, row in enumerate(rows[header_row + 1 :], start=header_row + 2):
        def cell(key: str, current_row: list[Any] = row) -> Any:
            index = columns[key]
            return current_row[index] if index < len(current_row) else None

        code = str(cell("code") or "").strip()
        description = str(cell("description") or "").strip()
        unit = str(cell("unit") or "").strip()
        if not code or not description or not unit:
            continue
        normalized_code = _normalize(code)
        if normalized_code in seen:
            raise CatalogImportError(f"Tekrarlanan poz kodu {code} (satır {row_number})")
        price = _decimal(cell("price"))
        if price < 0:
            raise CatalogImportError(f"Negatif birim fiyat {code} (satır {row_number})")
        seen.add(normalized_code)
        items.append(
            PriceItem(
                catalog_id=catalog.id,
                code=code,
                description=description,
                unit=unit,
                unit_price=price,
                currency=catalog.currency,
                metadata={"source_row": row_number},
            )
        )
    if not items:
        raise CatalogImportError("Katalogda kullanılabilir fiyat satırı bulunamadı")
    return catalog, items


def suggest_price_mappings(
    project_id: str,
    quantities: Iterable[QuantityLine],
    items: Iterable[PriceItem],
    *,
    minimum_confidence: float = 0.55,
) -> list[PriceMapping]:
    price_items = list(items)
    suggestions: list[PriceMapping] = []
    for quantity in quantities:
        candidates: list[tuple[float, PriceItem]] = []
        quantity_text = _normalize(f"{quantity.category} {quantity.description}")
        for item in price_items:
            if _normalize(item.unit) != _normalize(quantity.unit):
                continue
            score = SequenceMatcher(None, quantity_text, _normalize(item.description)).ratio()
            candidates.append((score, item))
        if not candidates:
            continue
        score, best = max(candidates, key=lambda pair: pair[0])
        if score < minimum_confidence:
            continue
        suggestions.append(
            PriceMapping(
                project_id=project_id,
                quantity_line_id=quantity.id,
                price_item_id=best.id,
                status=MappingStatus.SUGGESTED,
                confidence=round(score, 4),
                reason="Açıklama ve birim benzerliği; mühendis onayı bekleniyor",
            )
        )
    return suggestions


def calculate_offer(
    scenario: OfferScenario,
    quantities: Iterable[QuantityLine],
    mappings: Iterable[PriceMapping],
    price_items: Iterable[PriceItem],
) -> tuple[list[CostLine], dict[str, object]]:
    quantity_by_id = {item.id: item for item in quantities}
    item_by_id = {item.id: item for item in price_items}
    approved = [item for item in mappings if item.status == MappingStatus.APPROVED]
    lines: list[CostLine] = []
    for mapping in approved:
        quantity = quantity_by_id.get(mapping.quantity_line_id)
        price = item_by_id.get(mapping.price_item_id)
        if quantity is None or price is None:
            continue
        if _normalize(quantity.unit) != _normalize(price.unit):
            raise ValueError(f"Birim uyuşmazlığı: {quantity.id} / {price.code}")
        rate = Decimal("1")
        if price.currency != scenario.currency:
            if scenario.exchange_rate <= 0 or not scenario.exchange_rate_source:
                raise ValueError("Para birimi dönüşümü için onaylı kur ve kaynak gerekir")
            rate = scenario.exchange_rate
        quantity_value = Decimal(str(quantity.quantity))
        amount = (quantity_value * price.unit_price * rate).quantize(
            MONEY, rounding=ROUND_HALF_UP
        )
        lines.append(
            CostLine(
                scenario_id=scenario.id,
                quantity_line_id=quantity.id,
                price_item_id=price.id,
                quantity=quantity_value,
                unit=quantity.unit,
                unit_price=price.unit_price,
                currency=scenario.currency,
                amount=amount,
                mapping_id=mapping.id,
            )
        )

    direct = sum((line.amount for line in lines), Decimal("0.00"))
    running = direct
    previous = Decimal("0.00")
    adjustment_rows: list[dict[str, str]] = []
    for adjustment in sorted(scenario.adjustments, key=lambda item: item.order):
        if adjustment.applicable is not True:
            adjustment_rows.append(
                {"label": adjustment.label, "amount": "0.00", "status": "not_applicable"}
            )
            continue
        if adjustment.base == AdjustmentBase.DIRECT_COST:
            base = direct
        elif adjustment.base == AdjustmentBase.PREVIOUS_ADJUSTMENT:
            base = previous
        else:
            base = running
        if adjustment.kind == AdjustmentKind.PERCENT:
            amount = base * adjustment.value / Decimal("100")
        elif adjustment.kind == AdjustmentKind.INDEX:
            amount = base * (adjustment.value - Decimal("1"))
        else:
            amount = adjustment.value
        previous = amount.quantize(MONEY, rounding=ROUND_HALF_UP)
        running += previous
        adjustment_rows.append(
            {"label": adjustment.label, "amount": str(previous), "status": "applied"}
        )
    return lines, {
        "direct_cost": direct.quantize(MONEY, rounding=ROUND_HALF_UP),
        "adjustments": adjustment_rows,
        "grand_total": running.quantize(MONEY, rounding=ROUND_HALF_UP),
        "currency": scenario.currency,
    }
