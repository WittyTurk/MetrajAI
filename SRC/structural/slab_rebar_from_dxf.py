# -*- coding: utf-8 -*-
"""Doseme donatisi — DXF TEXT (Ø12/15). Kalip = alan."""

from __future__ import annotations

import re
from collections import Counter
from typing import List, Tuple, TYPE_CHECKING

from SRC.structural.models import RebarItem, Slab

try:
    from SRC.structural.rebar_models import WEIGHT_KG_PER_M
except Exception:
    WEIGHT_KG_PER_M = RebarItem.WEIGHT_KG_PER_M

if TYPE_CHECKING:
    from ezdxf.document import Drawing

REBAR_PAT = re.compile(
    r"(?:(\d+)\s*)?(?:Ø|ø|fi|Φ|ϕ)?\s*(\d{1,2})\s*/\s*(\d{2,3})",
    re.I,
)


class SlabRebarFromDxf:
    def __init__(self, doc: "Drawing", floor: str = "GENEL"):
        self.doc = doc
        self.msp = doc.modelspace()
        self.floor = floor

    def extract_mesh(self) -> List[Tuple[float, float, str]]:
        found = []
        for raw in self._texts():
            for m in REBAR_PAT.finditer(raw):
                dia = float(m.group(2))
                sp = float(m.group(3))
                if not (6 <= dia <= 32 and 5 <= sp <= 30):
                    continue
                found.append((dia, sp, raw[:50]))
        return found

    def build_for_slabs(self, slabs: List[Slab]) -> List[RebarItem]:
        print()
        print("=" * 55)
        print("DOSEME DONATI + KALIP  [kat: {}]".format(self.floor))
        print("=" * 55)
        if not slabs:
            print("! Doseme yok — demir/kalip 0")
            return []

        area = sum(s.area_m2 for s in slabs)
        formwork = sum(s.formwork_m2 for s in slabs)
        print("Doseme alan  : {:.1f} m2".format(area))
        print("Doseme kalip : {:.1f} m2 (alt)".format(formwork))
        print("Kalinlik     : {:.0f} cm".format(slabs[0].thickness_cm))

        mesh = self.extract_mesh()
        if not mesh:
            print("! Doseme donati isareti yok (Ø12/15) — demir 0")
            return []

        key_counts = Counter((d, s) for d, s, _ in mesh)
        print("Donati isaretleri:")
        for (d, s), n in key_counts.most_common(8):
            print("  Ø{:.0f}/{:.0f} -> {} adet yazi".format(d, s, n))

        (dia, sp_cm), _ = key_counts.most_common(1)[0]
        sp_m = sp_cm / 100.0
        if sp_m <= 0 or area <= 0:
            return []

        total_len = (area / sp_m) * 2 * 2 * 1.10  # x+y, alt+ust, bindirme
        w = WEIGHT_KG_PER_M.get(int(dia), (dia / 2) ** 2 * 0.006165)
        print(
            "Hesap: Ø{:.0f}/{:.0f}  L={:.0f} m  G={:.1f} kg".format(
                dia, sp_cm, total_len, total_len * w
            )
        )
        return [
            RebarItem(
                id=1,
                diameter_mm=dia,
                length_m=total_len,
                count=1,
                element_type="doseme",
                element_mark="SLAB-MESH",
                note="Ø{:.0f}/{:.0f} alt+ust x+y +%10".format(dia, sp_cm),
                floor=self.floor,
            )
        ]

    def _texts(self) -> List[str]:
        out = []
        for e in self.msp:
            if e.dxftype() == "TEXT":
                t = (e.dxf.text or "").strip()
                if t:
                    out.append(t)
            elif e.dxftype() == "MTEXT":
                try:
                    t = e.plain_text() if hasattr(e, "plain_text") else (e.text or "")
                except Exception:
                    t = getattr(e.dxf, "text", "") or ""
                t = re.sub(r"\\[A-Za-z][^;]*;", " ", str(t))
                t = re.sub(r"[{}]", " ", t).strip()
                if t:
                    out.append(t)
        return out