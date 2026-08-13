# -*- coding: utf-8 -*-
"""
Kolon extractor — DXF birebir, çok katlı.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import List

from SRC.structural.models import Column


class ColumnExtractor:
    SECTION_RE = re.compile(r"(\d+)\s*/\s*(\d+)")
    MARK_RE = re.compile(r"^(SZ\d+|C\d+|S\d+)$", re.I)

    def __init__(self, doc, layer_names=None, default_height_cm=300.0, floor: str = "GENEL"):
        self.doc = doc
        self.msp = doc.modelspace()
        self.layer_names = [n.upper() for n in (layer_names or ["KOLON", "COLUMN"])]
        self.default_height_cm = default_height_cm
        self.floor = floor

    def extract(self) -> List[Column]:
        print()
        print("=" * 55)
        print(f"COLUMN EXTRACTOR  [kat: {self.floor}]")
        print("=" * 55)

        raw = []
        for e in self.msp:
            if e.dxftype() != "INSERT":
                continue
            if e.dxf.layer.upper() not in self.layer_names:
                continue

            section, mark, notes = self._read_block(e.dxf.name)
            if section is None:
                continue

            raw.append({
                "section": section,
                "mark": mark or "",
                "x": e.dxf.insert.x,
                "y": e.dxf.insert.y,
                "block": e.dxf.name,
                "notes": notes,
            })

        print(f"Ham INSERT (kesitli): {len(raw)}")
        unique = self._dedup_by_position(raw, tol=50.0)
        print(f"Unique kolon        : {len(unique)}")

        columns = []
        for i, item in enumerate(unique, start=1):
            columns.append(Column(
                id=i,
                mark=item["mark"],
                section=item["section"],
                x=item["x"],
                y=item["y"],
                height_cm=self.default_height_cm,
                floor=self.floor,
                rebar_notes=item["notes"],
                source_block=item["block"],
            ))

        self._print_summary(columns)
        return columns

    def _read_block(self, block_name: str):
        block = self.doc.blocks.get(block_name)
        if block is None:
            return None, None, []

        section = None
        mark = None
        notes = []

        for e in block:
            text = None
            if e.dxftype() == "TEXT":
                text = e.dxf.text.strip()
            elif e.dxftype() == "MTEXT":
                text = (getattr(e, "text", None) or "").strip()
                text = re.sub(r"\\[A-Za-z][^;]*;", "", text)
                text = re.sub(r"[{}]", "", text).strip()

            if not text:
                continue

            m = self.SECTION_RE.search(text)
            if m and section is None:
                a, b = float(m.group(1)), float(m.group(2))
                if 20 <= a <= 120 and 20 <= b <= 120:
                    section = (a, b)

            if self.MARK_RE.match(text) and mark is None:
                mark = text.upper()

            up = text.upper()
            if "Ø" in text or "ETR" in up or "ÇİROZ" in up or "CIROZ" in up:
                notes.append(text)

        return section, mark, notes

    def _dedup_by_position(self, items, tol=50.0):
        groups = []
        for it in items:
            placed = False
            for g in groups:
                if abs(it["x"] - g["x"]) <= tol and abs(it["y"] - g["y"]) <= tol:
                    g["notes"] = list(set(g.get("notes", []) + it.get("notes", [])))
                    if not g.get("mark") and it.get("mark"):
                        g["mark"] = it["mark"]
                    placed = True
                    break
            if not placed:
                groups.append(dict(it))
        return groups

    def _print_summary(self, columns: List[Column]):
        sec = Counter(c.section for c in columns)
        print("\nKesit dağılımı:")
        for (a, b), n in sec.most_common():
            print(f"  {a:.0f}/{b:.0f}  →  {n} adet")
        print(f"Toplam kolon: {len(columns)}")