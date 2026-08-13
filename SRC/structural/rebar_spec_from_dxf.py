# -*- coding: utf-8 -*-
"""
Donatı çap / aralık / bindirme — yalnızca DXF TEXT/MTEXT.

Örnek metinler:
  Ø14/15
  φ12/20
  14/15 alt
  ust Ø12/20
  bindirme 40Ø
  40d
  kolon 8Ø16
  8φ16

Bulunamayan alan 0 kalır → metrajda o kalem atlanır, uyarı basılır.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Tuple, TYPE_CHECKING

from SRC.structural.raft_rebar import RaftRebarSpec

if TYPE_CHECKING:
    from ezdxf.document import Drawing


@dataclass
class ParsedRebarNote:
    raw: str
    dia: Optional[float] = None
    spacing_cm: Optional[float] = None
    count: Optional[int] = None
    layer: str = ""
    context: str = ""  # alt | ust | kolon | perde | bag | radye | genel


class RebarSpecFromDxf:
    """
    Statik DXF'ten RaftRebarSpec çıkar.
    Kural: DXF'te yoksa uydurma yok.
    """

    DIA_SPACING = re.compile(
        r"(?:[ØøφΦ]\s*)?(\d{1,2})\s*[/\-]\s*(\d{1,3})(?:\s*cm)?",
        re.I,
    )
    COUNT_DIA = re.compile(
        r"(\d{1,2})\s*[xX×]?\s*[ØøφΦ]\s*(\d{1,2})",
        re.I,
    )
    DIA_ONLY = re.compile(r"[ØøφΦ]\s*(\d{1,2})\b")
    LAP = re.compile(r"(?:bindirme|bind|lap)?\s*(\d{2,3})\s*[ØøφΦdD]\b", re.I)

    ALT_KW = re.compile(r"\b(alt|bottom|bot|asagi|aşağı)\b", re.I)
    UST_KW = re.compile(r"\b(ust|üst|top|yukari|yukarı)\b", re.I)
    KOLON_KW = re.compile(r"\b(kolon|column|filiz)\b", re.I)
    PERDE_KW = re.compile(r"\b(perde|shear|wall)\b", re.I)
    BAG_KW = re.compile(r"\b(bag|bağ|tie|etriye|stirrup)\b", re.I)
    RADYE_KW = re.compile(r"\b(radye|raft|temel|plak|doseme|döşeme)\b", re.I)

    def __init__(self, doc: "Drawing", layer_hints: Optional[List[str]] = None):
        self.doc = doc
        self.msp = doc.modelspace()
        self.layer_hints = layer_hints or [
            "DONATI", "REBAR", "DEMIR", "DEMİR",
            "YAZI", "TEXT", "NOT", "ACIKLAMA", "RADYE", "TEMEL",
        ]
        self.notes: List[ParsedRebarNote] = []
        self.warnings: List[str] = []

    def parse(self) -> List[ParsedRebarNote]:
        texts = self._collect_texts()
        self.notes = []
        for raw, layer in texts:
            note = self._parse_one(raw, layer)
            if note and (note.dia or note.spacing_cm or note.count):
                self.notes.append(note)

        print()
        print("=" * 55)
        print("DONATI NOTLARI (DXF)")
        print("=" * 55)
        print(f"Metin taranan : {len(texts)}")
        print(f"Donatı notu   : {len(self.notes)}")
        for n in self.notes[:30]:
            print(
                f"  Ø{str(n.dia or '-'):>4} / {str(n.spacing_cm or '-'):>4}  "
                f"n={str(n.count or '-'):>3}  [{n.context:7}]  {n.raw[:50]}"
            )
        if len(self.notes) > 30:
            print(f"  ... +{len(self.notes) - 30}")
        return self.notes

    def build_raft_spec(self) -> Tuple[RaftRebarSpec, List[str]]:
        if not self.notes:
            self.parse()

        spec = RaftRebarSpec(
            bot_x_dia=0, bot_x_spacing_cm=0,
            bot_y_dia=0, bot_y_spacing_cm=0,
            top_x_dia=0, top_x_spacing_cm=0,
            top_y_dia=0, top_y_spacing_cm=0,
            lap_factor=0,
            col_starter_dia=0, col_starter_count=0,
            wall_starter_dia=0, wall_starter_spacing_cm=0,
            tie_long_dia=0, tie_long_count=0,
            tie_stirrup_dia=0, tie_stirrup_spacing_cm=0,
        )
        warnings: List[str] = []

        alt = [n for n in self.notes if n.context == "alt"]
        ust = [n for n in self.notes if n.context == "ust"]
        kolon = [n for n in self.notes if n.context == "kolon"]
        bag = [n for n in self.notes if n.context == "bag"]
        genel = [n for n in self.notes if n.context in ("genel", "radye")]

        def pick_dia_sp(pool: List[ParsedRebarNote]):
            dias = [n.dia for n in pool if n.dia]
            sps = [n.spacing_cm for n in pool if n.spacing_cm]
            dia = Counter(dias).most_common(1)[0][0] if dias else None
            sp = Counter(sps).most_common(1)[0][0] if sps else None
            return dia, sp

        d, sp = pick_dia_sp(alt or genel)
        if d and sp:
            spec.bot_x_dia = spec.bot_y_dia = d
            spec.bot_x_spacing_cm = spec.bot_y_spacing_cm = sp
        else:
            warnings.append("DXF: alt donatı çap/aralık bulunamadı")

        d, sp = pick_dia_sp(ust or genel)
        if d and sp:
            spec.top_x_dia = spec.top_y_dia = d
            spec.top_x_spacing_cm = spec.top_y_spacing_cm = sp
        else:
            warnings.append("DXF: üst donatı çap/aralık bulunamadı")

        laps = []
        for n in self.notes:
            m = self.LAP.search(n.raw)
            if m:
                laps.append(float(m.group(1)))
        if laps:
            spec.lap_factor = Counter(laps).most_common(1)[0][0]
        else:
            warnings.append("DXF: bindirme (örn. 40Ø) bulunamadı")

        for n in kolon:
            if n.count and n.dia:
                spec.col_starter_count = int(n.count)
                spec.col_starter_dia = n.dia
                break
        if spec.col_starter_dia <= 0:
            for n in self.notes:
                if n.count and n.dia and n.context in ("kolon", "genel", "radye"):
                    spec.col_starter_count = int(n.count)
                    spec.col_starter_dia = n.dia
                    break
        if spec.col_starter_dia <= 0:
            warnings.append("DXF: kolon filiz (8Ø16) bulunamadı")

        for n in bag:
            low = n.raw.lower()
            if n.dia and n.spacing_cm and "etriye" in low:
                spec.tie_stirrup_dia = n.dia
                spec.tie_stirrup_spacing_cm = n.spacing_cm
            elif n.count and n.dia:
                spec.tie_long_count = int(n.count)
                spec.tie_long_dia = n.dia
            elif n.dia and n.spacing_cm:
                if spec.tie_long_dia <= 0:
                    spec.tie_long_dia = n.dia
        if spec.tie_long_dia <= 0:
            warnings.append("DXF: bağ kiriş boyuna bulunamadı")
        if spec.tie_stirrup_dia <= 0:
            warnings.append("DXF: bağ etriye bulunamadı")

        print()
        print("RADYE SPEC (DXF):")
        print(f"  alt  Ø{spec.bot_x_dia}/{spec.bot_x_spacing_cm}")
        print(f"  üst  Ø{spec.top_x_dia}/{spec.top_x_spacing_cm}")
        print(f"  bindirme {spec.lap_factor}Ø")
        print(f"  kolon filiz {spec.col_starter_count}Ø{spec.col_starter_dia}")
        print(
            f"  bağ  {spec.tie_long_count}Ø{spec.tie_long_dia}  "
            f"etriye Ø{spec.tie_stirrup_dia}/{spec.tie_stirrup_spacing_cm}"
        )
        for w in warnings:
            print(f"  ! {w}")

        self.warnings = warnings
        return spec, warnings

    def _collect_texts(self) -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        for e in self.msp:
            if e.dxftype() not in ("TEXT", "MTEXT"):
                continue
            layer = e.dxf.layer
            if e.dxftype() == "TEXT":
                t = (e.dxf.text or "").strip()
            else:
                t = (getattr(e, "text", None) or getattr(e.dxf, "text", None) or "")
                t = re.sub(r"\\[A-Za-z][^;]*;", "", str(t))
                t = re.sub(r"[{}]", "", t).strip()
            if not t or len(t) > 200:
                continue
            out.append((t, layer))

        for e in self.msp:
            if e.dxftype() != "INSERT":
                continue
            block = self.doc.blocks.get(e.dxf.name)
            if not block:
                continue
            for be in block:
                if be.dxftype() == "TEXT":
                    t = (be.dxf.text or "").strip()
                    if t:
                        out.append((t, e.dxf.layer))
                elif be.dxftype() == "MTEXT":
                    t = (getattr(be, "text", "") or "").strip()
                    if t:
                        out.append((t, e.dxf.layer))
        return out

    def _parse_one(self, raw: str, layer: str) -> Optional[ParsedRebarNote]:
        context = "genel"
        if self.ALT_KW.search(raw):
            context = "alt"
        elif self.UST_KW.search(raw):
            context = "ust"
        elif self.KOLON_KW.search(raw):
            context = "kolon"
        elif self.PERDE_KW.search(raw):
            context = "perde"
        elif self.BAG_KW.search(raw):
            context = "bag"
        elif self.RADYE_KW.search(raw):
            context = "radye"

        note = ParsedRebarNote(raw=raw, layer=layer, context=context)

        m = self.COUNT_DIA.search(raw)
        if m:
            note.count = int(m.group(1))
            note.dia = float(m.group(2))
            if 6 <= note.dia <= 40:
                return note

        m = self.DIA_SPACING.search(raw)
        if m:
            note.dia = float(m.group(1))
            note.spacing_cm = float(m.group(2))
            if 6 <= note.dia <= 40 and 5 <= note.spacing_cm <= 50:
                return note
            note.dia = None
            note.spacing_cm = None

        m = self.DIA_ONLY.search(raw)
        if m:
            note.dia = float(m.group(1))
            if 6 <= note.dia <= 40:
                return note

        if note.dia is None and note.count is None:
            return None
        return note