# -*- coding: utf-8 -*-
"""
Metraj validator — Taziye ve çok katlı projeler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class ValidationIssue:
    level: str   # ERROR | WARN | INFO
    code: str
    message: str
    floor: str = ""


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self):
        return [i for i in self.issues if i.level == "ERROR"]

    @property
    def warnings(self):
        return [i for i in self.issues if i.level == "WARN"]

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def add(self, level: str, code: str, message: str, floor: str = ""):
        self.issues.append(ValidationIssue(level, code, message, floor))

    def report(self) -> None:
        print()
        print("=" * 55)
        print("VALIDATOR")
        print("=" * 55)
        print(f"Hata  : {len(self.errors)}")
        print(f"Uyarı : {len(self.warnings)}")
        print(f"Sonuç : {'GEÇTİ' if self.ok else 'HATALI'}")
        for i in self.issues:
            tag = {"ERROR": "E", "WARN": "W", "INFO": "I"}.get(i.level, "?")
            loc = f"[{i.floor}] " if i.floor else ""
            print(f"  {tag} {loc}{i.code}: {i.message}")


class MetrajValidator:

    def validate_discovery(self, discovery) -> ValidationReport:
        r = ValidationReport()
        if not discovery.static_floors and not discovery.architectural_dxfs:
            r.add("ERROR", "NO_DXF", "INPUT içinde DXF yok")
        for f in discovery.static_floors:
            if not Path(f.dxf).exists():
                r.add("ERROR", "DXF_MISSING", f"Dosya yok: {f.dxf}", floor=f.name)
            else:
                r.add("INFO", "DXF_OK", Path(f.dxf).name, floor=f.name)
        if not discovery.mahal_files:
            r.add("WARN", "NO_MAHAL", "Mahal listesi yok (opsiyonel)")
        else:
            r.add("INFO", "MAHAL_OK", f"{len(discovery.mahal_files)} dosya")
        return r

    def validate_structural(
        self,
        columns=None,
        beams=None,
        rafts=None,
        rebars=None,
    ) -> ValidationReport:
        r = ValidationReport()
        columns = columns or []
        beams = beams or []
        rafts = rafts or []
        rebars = rebars or []

        if not columns and not beams and not rafts:
            r.add("ERROR", "NO_STRUCT", "Hiç statik eleman yok")

        if columns:
            bad_sec = [c for c in columns if not c.section or c.section[0] <= 0]
            if bad_sec:
                r.add("ERROR", "COL_SEC", f"{len(bad_sec)} kolon kesiti eksik")
            # Taziye: ~9 kolon beklenir
            if 1 <= len(columns) <= 20:
                r.add("INFO", "COL_N", f"Kolon adedi={len(columns)}")
            elif len(columns) > 20:
                r.add("WARN", "COL_MANY", f"Kolon adedi yüksek: {len(columns)}")
        else:
            r.add("WARN", "NO_COL", "Kolon yok")

        if beams:
            zero = [b for b in beams if b.length_m < 0.3]
            if zero:
                r.add("ERROR", "BEAM_L0", f"{len(zero)} kiriş boyu ~0")
            r.add("INFO", "BEAM_N", f"Kiriş adedi={len(beams)}")
        else:
            r.add("WARN", "NO_BEAM", "Kiriş yok")

        if not rebars:
            r.add("WARN", "NO_REBAR", "Demir kalemi yok")
        else:
            r.add("INFO", "REBAR_N", f"Demir kalemi={len(rebars)}")

        r.add(
            "INFO",
            "SUMMARY",
            f"kolon={len(columns)} kiriş={len(beams)} radye={len(rafts)} demir={len(rebars)}",
        )
        return r