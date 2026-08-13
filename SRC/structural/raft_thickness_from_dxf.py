# -*- coding: utf-8 -*-
"""
Radye kalınlığı — yalnızca DXF TEXT/MTEXT.

Örnek metinler:
  h=40 cm
  kalınlık 40
  radye 40cm
  t=40
  40 cm plak
  H:40

Bulunamazsa None → uydurma yok.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ezdxf.document import Drawing


class RaftThicknessFromDxf:
    PATTERNS = [
        re.compile(r"(?:kalinli[kğ]|kalınlık|thickness)\s*[:=]?\s*(\d{2,3})\s*(?:cm)?", re.I),
        re.compile(r"(?:radye|raft|plak|temel)[^\d]{0,20}(\d{2,3})\s*cm", re.I),
        re.compile(r"\b[hHtT]\s*[:=]\s*(\d{2,3})\s*(?:cm)?\b"),
        re.compile(r"\b(\d{2,3})\s*cm\b"),
    ]
    CONTEXT = re.compile(r"radye|raft|temel|plak|kalin|kalın|thickness|doseme|döşeme", re.I)

    def __init__(self, doc: "Drawing"):
        self.doc = doc
        self.msp = doc.modelspace()

    def read_cm(self) -> Tuple[Optional[float], List[str]]:
        texts = self._collect_texts()
        candidates: List[float] = []
        hits: List[str] = []

        for raw in texts:
            val = self._parse(raw)
            if val is None:
                continue
            if not self.CONTEXT.search(raw) and not re.search(r"[hHtT]\s*[:=]", raw):
                if not re.search(r"kalin|kalın|thickness", raw, re.I):
                    continue
            candidates.append(val)
            hits.append(f"{val:.0f} cm ← {raw[:60]}")

        if not candidates:
            print()
            print("RADYE KALINLIK (DXF): bulunamadı")
            return None, []

        best = Counter(candidates).most_common(1)[0][0]
        print()
        print("=" * 55)
        print("RADYE KALINLIK (DXF)")
        print("=" * 55)
        print(f"Seçilen : {best:.0f} cm")
        for h in hits[:10]:
            print(f"  {h}")
        return best, hits

    def _parse(self, raw: str) -> Optional[float]:
        for pat in self.PATTERNS:
            m = pat.search(raw)
            if not m:
                continue
            try:
                v = float(m.group(1))
            except (TypeError, ValueError):
                continue
            if 20 <= v <= 120:
                return v
        return None

    def _collect_texts(self) -> List[str]:
        out: List[str] = []
        for e in self.msp:
            if e.dxftype() == "TEXT":
                t = (e.dxf.text or "").strip()
                if t:
                    out.append(t)
            elif e.dxftype() == "MTEXT":
                t = getattr(e, "text", None) or getattr(e.dxf, "text", None) or ""
                t = re.sub(r"\\[A-Za-z][^;]*;", "", str(t))
                t = re.sub(r"[{}]", "", t).strip()
                if t:
                    out.append(t)
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
                        out.append(t)
                elif be.dxftype() == "MTEXT":
                    t = (getattr(be, "text", "") or "").strip()
                    if t:
                        out.append(t)
        return out