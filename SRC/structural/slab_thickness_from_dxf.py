# -*- coding: utf-8 -*-
"""Doseme kalinligi — DXF TEXT (d=20cm, DA101 d=20cm)."""

from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ezdxf.document import Drawing


class SlabThicknessFromDxf:
    PATTERNS = [
        re.compile(r"\bd\s*=\s*(\d{2,3})\s*cm\b", re.I),
        re.compile(r"\bd\s*=\s*(\d{2,3})\b", re.I),
        re.compile(
            r"(?:d[oö][sş]eme|slab|plak|plate)\s*"
            r"(?:kal[iı]nl[iı][gğ][iı]|kalinlik|thickness)?\s*"
            r"[:=]?\s*(\d{2,3})\s*(?:cm)?",
            re.I,
        ),
        re.compile(
            r"(?:kal[iı]nl[iı][gğ][iı]|kalinlik|thickness)\s*[:=]?\s*(\d{2,3})\s*(?:cm)?",
            re.I,
        ),
        re.compile(r"\b[hHtT]\s*[:=]\s*(\d{2,3})\s*(?:cm)?\b"),
        re.compile(r"(\d{2,3})\s*cm", re.I),
    ]
    CONTEXT = re.compile(
        r"d[oö][sş]eme|slab|plak|plate|kal[iı]n|thickness|\bd\s*=|\bh\s*[:=]|DA\d+",
        re.I,
    )
    EXCLUDE = re.compile(
        r"radye|raft|temel|ba[gğ]\s*kiri[sş]|kiris\s*h|kolon\s*h|perde",
        re.I,
    )

    def __init__(self, doc: "Drawing"):
        self.doc = doc
        self.msp = doc.modelspace()

    def read_cm(self) -> Tuple[Optional[float], List[str]]:
        texts = self._collect_texts()
        candidates: List[float] = []
        hits: List[str] = []
        for raw in texts:
            if self.EXCLUDE.search(raw) and not re.search(
                r"d[oö][sş]eme|slab|plak", raw, re.I
            ):
                continue
            val = self._parse(raw)
            if val is None or not (10 <= val <= 40):
                continue
            has_ctx = bool(self.CONTEXT.search(raw))
            if not has_ctx and not re.search(r"\d{2,3}\s*cm", raw, re.I):
                continue
            weight = 3 if has_ctx else 1
            for _ in range(weight):
                candidates.append(val)
            hits.append("{:.0f} cm ← {}".format(val, raw[:70]))
        if not candidates:
            for raw in self._merge_nearby_context(texts):
                val = self._parse(raw)
                if val is None or not (10 <= val <= 40):
                    continue
                candidates.append(val)
                hits.append("{:.0f} cm ← [birlesik] {}".format(val, raw[:70]))
        if not candidates:
            print("\nDOSEME KALINLIK (DXF): bulunamadi")
            return None, []
        best = Counter(candidates).most_common(1)[0][0]
        print("\n" + "=" * 55)
        print("DOSEME KALINLIK (DXF)")
        print("=" * 55)
        print("Secilen : {:.0f} cm".format(best))
        for h in hits[:12]:
            print("  ", h)
        return best, hits

    def _parse(self, raw: str) -> Optional[float]:
        for pat in self.PATTERNS:
            m = pat.search(raw)
            if m:
                try:
                    return float(m.group(1))
                except (TypeError, ValueError):
                    pass
        return None

    def _merge_nearby_context(self, texts: List[str]) -> List[str]:
        ctx = [t for t in texts if self.CONTEXT.search(t)]
        nums = [t for t in texts if re.search(r"\b\d{2,3}\s*cm\b", t, re.I)]
        return [c + " " + n for c in ctx[:50] for n in nums[:50]]

    def _collect_texts(self) -> List[str]:
        out: List[str] = []

        def add(t: str):
            t = (t or "").strip()
            if not t:
                return
            t = re.sub(r"\\[A-Za-z][^;]*;", " ", t)
            t = re.sub(r"[{}]", " ", t)
            t = re.sub(r"\s+", " ", t).strip()
            if t:
                out.append(t)

        for e in self.msp:
            dt = e.dxftype()
            if dt == "TEXT":
                add(e.dxf.text or "")
            elif dt == "MTEXT":
                try:
                    add(e.plain_text() if hasattr(e, "plain_text") else (e.text or ""))
                except Exception:
                    add(getattr(e.dxf, "text", None) or "")
            elif dt == "INSERT":
                block = self.doc.blocks.get(e.dxf.name)
                if not block:
                    continue
                for be in block:
                    if be.dxftype() == "TEXT":
                        add(be.dxf.text or "")
                    elif be.dxftype() == "MTEXT":
                        try:
                            add(
                                be.plain_text()
                                if hasattr(be, "plain_text")
                                else (getattr(be, "text", "") or "")
                            )
                        except Exception:
                            pass
        return out