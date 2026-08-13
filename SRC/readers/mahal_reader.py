# -*- coding: utf-8 -*-
"""
Mahal okuyucu — iki kaynak:
1) Excel/CSV mahal listesi
2) DXF mimari çizim (liste yoksa poligon + TEXT)

  mr = MahalReader()
  mahaller = mr.read("mahal.xlsx")
  mahaller = mr.read_from_dxf(dxf_reader)
  mahaller = mr.load(list_path="mahal.xlsx", dxf_reader=dxf)
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from SRC.models.mahal import Mahal

if TYPE_CHECKING:
    from SRC.readers.dxf_reader import DXFReader


class MahalReader:

    SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}

    MAHAL_NO_RE = re.compile(
        r"^(?:MH|M|ODA)?\s*[-_]?\s*(\d{1,4}[A-Za-z]?)$",
        re.I,
    )

    def read(self, path: str) -> list[Mahal]:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Mahal dosyası bulunamadı: {file_path}")

        extension = file_path.suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(self.SUPPORTED_EXTENSIONS))
            raise ValueError(
                f"Desteklenmeyen uzantı: '{extension}'. Desteklenen: {supported}"
            )
        if extension == ".xls":
            raise ValueError("Sadece '.xlsx' destekleniyor.")
        if extension == ".csv":
            return self._read_csv(file_path)
        return self._read_excel(file_path)

    def read_from_dxf(
        self,
        reader: "DXFReader",
        layer_names: Optional[List[str]] = None,
        min_area_m2: float = 0.5,
        max_area_m2: float = 5000.0,
        level_name: Optional[str] = None,
    ) -> list[Mahal]:
        if layer_names is None:
            layer_names = reader.layers_for_discipline("architectural")
            extra = []
            for layer in reader.layer_statistics().keys():
                lu = layer.upper().replace("İ", "I").replace("Ş", "S")
                if any(k in lu for k in ("MAHAL", "ODA", "ROOM", "ALAN", "SPACE")):
                    if layer not in layer_names:
                        extra.append(layer)
            layer_names = list(layer_names) + extra

        polys = reader.polylines_on_layer(layer_names, closed_only=True)
        texts = reader.texts_on_layer(layer_names)
        if not texts:
            texts = reader.texts_on_layer(None)

        items: list[Mahal] = []
        for pl in polys:
            area = pl.get("area_m2") or 0.0
            if area < min_area_m2 or area > max_area_m2:
                continue

            cx = sum(p[0] for p in pl["points"]) / len(pl["points"])
            cy = sum(p[1] for p in pl["points"]) / len(pl["points"])
            mahal_no, mahal_name = self._nearest_label(texts, cx, cy, reader.unit_to_m)

            if not mahal_no:
                mahal_no = f"DXF-{len(items) + 1}"
            if not mahal_name:
                mahal_name = mahal_no

            items.append(Mahal(
                id=len(items) + 1,
                mahal_no=mahal_no,
                mahal_name=mahal_name,
                measured_area=round(area, 2),
                level_name=level_name,
                source="dxf",
                layer=pl.get("layer", ""),
                properties={"centroid": (cx, cy)},
            ))

        print(f"[MahalReader] DXF'ten {len(items)} mahal")
        return items

    def merge(self, from_list: list[Mahal], from_dxf: list[Mahal]) -> list[Mahal]:
        by_key: dict[str, Mahal] = {}

        for m in from_list:
            key = (m.mahal_no or "").strip().upper() or f"LIST-{m.id}"
            by_key[key] = Mahal(
                id=m.id,
                mahal_no=m.mahal_no,
                mahal_name=m.mahal_name,
                expected_area=m.expected_area,
                level_name=m.level_name,
                building_name=m.building_name,
                floor_finish=m.floor_finish,
                wall_finish=m.wall_finish,
                ceiling_finish=m.ceiling_finish,
                skirting=m.skirting,
                source="list",
                properties=dict(m.properties),
            )

        next_id = max((m.id for m in by_key.values()), default=0) + 1

        for m in from_dxf:
            key = (m.mahal_no or "").strip().upper()
            if key in by_key:
                existing = by_key[key]
                existing.measured_area = m.measured_area
                existing.source = "merged"
                if not existing.mahal_name and m.mahal_name:
                    existing.mahal_name = m.mahal_name
                if m.layer:
                    existing.layer = m.layer
            else:
                by_key[key or f"DXF-{next_id}"] = Mahal(
                    id=next_id,
                    mahal_no=m.mahal_no,
                    mahal_name=m.mahal_name,
                    measured_area=m.measured_area,
                    level_name=m.level_name,
                    source="dxf",
                    layer=m.layer,
                    properties=dict(m.properties),
                )
                next_id += 1

        result = list(by_key.values())
        for i, m in enumerate(result, start=1):
            m.id = i
        print(f"[MahalReader] Birleşik: {len(result)} mahal")
        return result

    def load(
        self,
        list_path: Optional[str] = None,
        dxf_reader: Optional["DXFReader"] = None,
        level_name: Optional[str] = None,
    ) -> list[Mahal]:
        from_list: list[Mahal] = []
        from_dxf: list[Mahal] = []
        if list_path:
            from_list = self.read(list_path)
            print(f"[MahalReader] Liste: {len(from_list)} mahal")
        if dxf_reader is not None:
            from_dxf = self.read_from_dxf(dxf_reader, level_name=level_name)
        if from_list and from_dxf:
            return self.merge(from_list, from_dxf)
        if from_list:
            return from_list
        if from_dxf:
            return from_dxf
        return []

    def _read_excel(self, file_path: Path) -> list[Mahal]:
        from openpyxl import load_workbook

        workbook = load_workbook(filename=file_path, data_only=True)
        worksheet = workbook.worksheets[0]
        rows = worksheet.iter_rows(values_only=True)
        header_row = next(rows, None)
        if header_row is None:
            return []

        header_index: dict[str, int] = {}
        for index, value in enumerate(header_row):
            if value is None:
                continue
            name = str(value).strip()
            if name:
                header_index[name] = index

        aliases = {
            "mahal_no": ["mahal_no", "mahal no", "no", "kod", "mahal_kodu"],
            "mahal_name": ["mahal_name", "mahal adı", "mahal adi", "ad", "name", "isim"],
            "expected_area": ["expected_area", "alan", "area", "m2", "m²", "net_alan"],
            "level_name": ["level_name", "kat", "level", "floor"],
            "building_name": ["building_name", "bina", "building"],
            "floor_finish": ["floor_finish", "döşeme", "doseme", "zemin"],
            "wall_finish": ["wall_finish", "duvar", "wall"],
            "ceiling_finish": ["ceiling_finish", "tavan", "ceiling"],
            "skirting": ["skirting", "süpürgelik", "supurgelik"],
        }

        def resolve(field: str) -> Optional[str]:
            for alias in aliases.get(field, [field]):
                for h in header_index:
                    if h.lower().strip() == alias.lower():
                        return h
            return field if field in header_index else None

        resolved = {f: resolve(f) for f in aliases}
        items: list[Mahal] = []

        for row in rows:
            if self._is_empty_row(row):
                continue

            def cell(field: str):
                h = resolved.get(field)
                if not h:
                    return None
                return self._cell_value(row, header_index, h)

            mahal_no = self._to_text(cell("mahal_no")) or ""
            mahal_name = self._to_text(cell("mahal_name")) or mahal_no
            if not mahal_no and not mahal_name:
                continue

            items.append(Mahal(
                id=len(items) + 1,
                mahal_no=mahal_no or f"L-{len(items)+1}",
                mahal_name=mahal_name or mahal_no,
                expected_area=self._to_optional_float(cell("expected_area")),
                level_name=self._to_text(cell("level_name")),
                building_name=self._to_text(cell("building_name")),
                floor_finish=self._to_text(cell("floor_finish")),
                wall_finish=self._to_text(cell("wall_finish")),
                ceiling_finish=self._to_text(cell("ceiling_finish")),
                skirting=self._to_text(cell("skirting")),
                source="list",
            ))
        return items

    def _read_csv(self, file_path: Path) -> list[Mahal]:
        items: list[Mahal] = []
        with open(file_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return []
            for row in reader:
                def get(*keys):
                    for k in keys:
                        for rk, rv in row.items():
                            if rk and rk.strip().lower() == k.lower():
                                return rv
                    return None

                mahal_no = self._to_text(get("mahal_no", "mahal no", "no", "kod")) or ""
                mahal_name = self._to_text(get("mahal_name", "mahal adı", "ad", "name")) or mahal_no
                if not mahal_no and not mahal_name:
                    continue
                items.append(Mahal(
                    id=len(items) + 1,
                    mahal_no=mahal_no or f"L-{len(items)+1}",
                    mahal_name=mahal_name or mahal_no,
                    expected_area=self._to_optional_float(get("expected_area", "alan", "area", "m2")),
                    level_name=self._to_text(get("level_name", "kat", "level")),
                    building_name=self._to_text(get("building_name", "bina")),
                    floor_finish=self._to_text(get("floor_finish", "döşeme", "doseme")),
                    wall_finish=self._to_text(get("wall_finish", "duvar")),
                    ceiling_finish=self._to_text(get("ceiling_finish", "tavan")),
                    skirting=self._to_text(get("skirting", "süpürgelik")),
                    source="list",
                ))
        return items

    def _nearest_label(self, texts, cx, cy, unit_to_m, max_dist_m=5.0):
        max_dist_u = max_dist_m / unit_to_m if unit_to_m > 0 else max_dist_m * 100
        best, best_d = None, max_dist_u
        for t in texts:
            d = ((t["x"] - cx) ** 2 + (t["y"] - cy) ** 2) ** 0.5
            if d < best_d:
                best_d = d
                best = t["text"]
        if not best:
            return "", ""
        parts = best.strip().split(None, 1)
        no = parts[0]
        name = parts[1] if len(parts) > 1 else parts[0]
        m = self.MAHAL_NO_RE.match(no)
        if m:
            no = m.group(1)
        return no, name

    @staticmethod
    def _cell_value(row, header_index, name):
        index = header_index.get(name)
        if index is None or index >= len(row):
            return None
        return row[index]

    @staticmethod
    def _is_empty_row(row) -> bool:
        for value in row:
            if value is not None and str(value).strip() != "":
                return False
        return True

    @staticmethod
    def _to_text(value):
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    @staticmethod
    def _to_optional_float(value):
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None