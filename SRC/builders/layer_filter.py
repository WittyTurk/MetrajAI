# -*- coding: utf-8 -*-
"""
Katman filtresi — Türkçe karakter toleranslı.

  filter.get("sıva")
  filter.get_any(["sıva", "DUVAR"])
  filter.contains("KAPI")
  filter.auto(["SIVA", "DUVAR"])
"""

from __future__ import annotations

from typing import Iterable, List, Optional


def norm_layer(name: str) -> str:
    return (
        (name or "")
        .upper()
        .replace("İ", "I")
        .replace("Ş", "S")
        .replace("Ğ", "G")
        .replace("Ü", "U")
        .replace("Ö", "O")
        .replace("Ç", "C")
    )


class LayerFilter:

    def __init__(self, modelspace):
        self.msp = modelspace
        self._layer_cache: Optional[dict] = None

    def get(self, layer_name: str) -> list:
        target = norm_layer(layer_name)
        result = []
        for entity in self.msp:
            if norm_layer(entity.dxf.layer) == target:
                result.append(entity)
        return result

    def get_any(self, layer_names: Iterable[str]) -> list:
        targets = {norm_layer(n) for n in layer_names}
        result = []
        for entity in self.msp:
            if norm_layer(entity.dxf.layer) in targets:
                result.append(entity)
        return result

    def contains(self, keyword: str) -> list:
        key = norm_layer(keyword)
        result = []
        for entity in self.msp:
            if key in norm_layer(entity.dxf.layer):
                result.append(entity)
        return result

    def auto(self, keywords: Iterable[str]) -> dict:
        keys = [norm_layer(k) for k in keywords]
        result: dict = {}
        for entity in self.msp:
            nl = norm_layer(entity.dxf.layer)
            for k in keys:
                if k in nl or nl == k:
                    result.setdefault(entity.dxf.layer, []).append(entity)
                    break
        return result

    def layer_names(self) -> List[str]:
        names = set()
        for entity in self.msp:
            names.add(entity.dxf.layer)
        return sorted(names)

    def count_by_layer(self) -> dict:
        from collections import Counter
        return dict(Counter(e.dxf.layer for e in self.msp))