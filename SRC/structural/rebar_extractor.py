# -*- coding: utf-8 -*-
"""
Demir (donatı) extractor — TEXT notlarından Ø, boy, adet.

Örnek notlar:
  96Ø8
  48Ø8/19/10/10/13
  4Ø16 L=320
  Etr. L=206
"""

from __future__ import annotations

import re
from typing import List

from SRC.structural.models import RebarItem, Column, Beam


class RebarExtractor:
    COUNT_DIA = re.compile(r"(\d+)\s*[ØøФф]\s*(\d+)", re.I)
    LEN_RE = re.compile(r"L\s*=\s*(\d+(?:[.,]\d+)?)", re.I)
    COMPLEX = re.compile(r"(\d+)\s*[Øø]\s*(\d+)(?:/[\d]+)*", re.I)

    def __init__(self, floor: str = "GENEL", default_length_m: float = 1.0):
        self.floor = floor
        self.default_length_m = default_length_m

    def extract_from_columns(self, columns: List[Column]) -> List[RebarItem]:
        items = []
        rid = 1
        for col in columns:
            for note in col.rebar_notes:
                parsed = self._parse_note(note)
                for dia, count, length in parsed:
                    items.append(RebarItem(
                        id=rid,
                        diameter_mm=dia,
                        length_m=length,
                        count=count,
                        element_type="kolon",
                        element_mark=col.mark or f"C{col.id}",
                        note=note,
                        floor=col.floor or self.floor,
                    ))
                    rid += 1
        return items

    def extract_from_beams(self, beams: List[Beam]) -> List[RebarItem]:
        items = []
        rid = 1
        for beam in beams:
            for note in beam.rebar_notes:
                parsed = self._parse_note(note)
                for dia, count, length in parsed:
                    if length <= 0:
                        length = beam.length_m
                    items.append(RebarItem(
                        id=rid,
                        diameter_mm=dia,
                        length_m=length,
                        count=count,
                        element_type="kiriş",
                        element_mark=beam.mark or f"B{beam.id}",
                        note=note,
                        floor=beam.floor or self.floor,
                    ))
                    rid += 1
        return items

    def extract_from_texts(self, notes: List[str], element_type: str = "genel") -> List[RebarItem]:
        items = []
        rid = 1
        for note in notes:
            for dia, count, length in self._parse_note(note):
                items.append(RebarItem(
                    id=rid,
                    diameter_mm=dia,
                    length_m=length if length > 0 else self.default_length_m,
                    count=count,
                    element_type=element_type,
                    note=note,
                    floor=self.floor,
                ))
                rid += 1
        return items

    def _parse_note(self, note: str):
        results = []
        length = 0.0
        mlen = self.LEN_RE.search(note)
        if mlen:
            val = float(mlen.group(1).replace(",", "."))
            length = val / 100.0 if val > 50 else val

        for m in self.COUNT_DIA.finditer(note):
            count = int(m.group(1))
            dia = float(m.group(2))
            if dia < 6 or dia > 40:
                continue
            if count > 500:
                continue
            results.append((dia, count, length if length > 0 else self.default_length_m))

        return results