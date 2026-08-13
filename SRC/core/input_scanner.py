# -*- coding: utf-8 -*-
"""
INPUT klasörünü tara — Taziye ve çok katlı projeler.

  INPUT/statik/*.dxf  → kat adı dosya adından
  INPUT/mahal/*.xlsx  → mahal listesi
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class DiscoveredFloor:
    name: str
    dxf: str
    kind: str = "floor"  # foundation | floor | typical


@dataclass
class DiscoveryResult:
    root: Path
    project_name: str
    static_floors: List[DiscoveredFloor] = field(default_factory=list)
    architectural_dxfs: List[str] = field(default_factory=list)
    mahal_files: List[str] = field(default_factory=list)
    door_schedules: List[str] = field(default_factory=list)
    window_schedules: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def report(self) -> None:
        print()
        print("=" * 55)
        print("INPUT KEŞİF")
        print("=" * 55)
        print(f"Kök       : {self.root}")
        print(f"Proje     : {self.project_name}")
        print(f"Statik    : {len(self.static_floors)}")
        for f in self.static_floors:
            print(f"  [{f.kind:11}] {f.name:12} ← {Path(f.dxf).name}")
        print(f"Mahal     : {len(self.mahal_files)}")
        for w in self.warnings:
            print(f"  ! {w}")


class InputScanner:
    FOUNDATION_RE = re.compile(r"temel|radye|foundation", re.I)
    GROUND_RE = re.compile(r"zemin|ground|taziye|statik", re.I)
    FLOOR_RE = re.compile(r"(\d+)\s*[.\-_]?\s*kat", re.I)
    MAHAL_RE = re.compile(r"mahal|room|oda", re.I)
    DOOR_RE = re.compile(r"kapi|kapı|door", re.I)
    WINDOW_RE = re.compile(r"pencere|window", re.I)

    def __init__(self, input_root: str = "INPUT"):
        self.root = Path(input_root)

    def scan(self) -> DiscoveryResult:
        if not self.root.exists():
            raise FileNotFoundError(f"INPUT yok: {self.root.resolve()}")

        result = DiscoveryResult(
            root=self.root.resolve(),
            project_name=self.root.resolve().parent.name,
        )

        statik_dir = self.root / "statik"
        mahal_dir = self.root / "mahal"
        detay_dir = self.root / "detay"

        # Statik DXF: önce statik/, yoksa INPUT kökü
        dxf_folder = statik_dir if statik_dir.exists() else self.root
        for p in sorted(dxf_folder.glob("*.dxf")):
            result.static_floors.append(self._classify(p))

        # Mahal
        folder = mahal_dir if mahal_dir.exists() else self.root
        for p in sorted(folder.glob("*.xlsx")) + sorted(folder.glob("*.csv")):
            if self.MAHAL_RE.search(p.name) or folder == mahal_dir:
                result.mahal_files.append(str(p))

        # Detay tabloları
        folder = detay_dir if detay_dir.exists() else self.root
        for p in list(folder.glob("*.xlsx")) + list(folder.glob("*.csv")):
            if self.DOOR_RE.search(p.name):
                result.door_schedules.append(str(p))
            elif self.WINDOW_RE.search(p.name):
                result.window_schedules.append(str(p))

        if not result.static_floors:
            result.warnings.append("Statik DXF yok — INPUT/statik/ klasörüne koyun")
        if result.static_floors:
            result.project_name = Path(result.static_floors[0].dxf).stem

        result.report()
        return result

    def _classify(self, path: Path) -> DiscoveredFloor:
        name = path.stem
        if self.FOUNDATION_RE.search(name):
            return DiscoveredFloor("TEMEL", str(path), "foundation")
        if self.FLOOR_RE.search(name):
            m = self.FLOOR_RE.search(name)
            return DiscoveredFloor(f"{m.group(1)}.Kat", str(path), "floor")
        # Taziye tek pafta → Zemin say
        if self.GROUND_RE.search(name):
            return DiscoveredFloor("Zemin", str(path), "floor")
        return DiscoveredFloor(name[:24], str(path), "floor")
