# -*- coding: utf-8 -*-
"""
Aks omurga denetimi — her X/Y aksı tek tek.
Gecmezse metraj baslamaz.
"""

from __future__ import annotations

from typing import List

from SRC.structural.axis_grid import AxisGrid, AxisGridError


class AxisAuditResult:
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.ok: bool = False

    def report(self) -> bool:
        print()
        print("=" * 55)
        print("AKS AUDIT (tek tek)")
        print("=" * 55)
        for w in self.warnings:
            print("  !", w)
        for e in self.errors:
            print("  X", e)
        if self.ok:
            print("Sonuc: GECTI")
        else:
            print("Sonuc: KALDI — metraj durduruldu")
        return self.ok


def audit_axis_grid(
    grid: AxisGrid, min_y_m: float = 5.0, max_x_m: float = 250.0
) -> AxisAuditResult:
    res = AxisAuditResult()
    if grid is None:
        res.errors.append("Grid None")
        res.report()
        raise AxisGridError("Aks audit KALDI: Grid None")

    print()
    print("=" * 55)
    print("AKS LISTE (X)")
    print("=" * 55)
    xl = list(getattr(grid, "x_labels", []) or [])
    xs = list(getattr(grid, "x_spacings_m", []) or [])
    if len(xl) < 2:
        res.errors.append("X aks sayisi < 2")
    for i, lab in enumerate(xl):
        print("  [{:2d}] X={} ".format(i + 1, lab), end="")
        if i < len(xs):
            flag = ""
            if xs[i] < 0.5:
                flag = " [DILATASYON/SUPHE]"
                if xs[i] <= 0:
                    res.errors.append(
                        "X aralik <=0: {}→{}".format(
                            lab, xl[i + 1] if i + 1 < len(xl) else "?"
                        )
                    )
            print(
                "→ {}  L={:.2f} m{}".format(
                    xl[i + 1] if i + 1 < len(xl) else "-", xs[i], flag
                )
            )
        else:
            print()

    print()
    print("=" * 55)
    print("AKS LISTE (Y)")
    print("=" * 55)
    yl = list(getattr(grid, "y_labels", []) or [])
    ys = list(getattr(grid, "y_spacings_m", []) or [])
    if len(yl) < 2:
        res.errors.append("Y aks sayisi < 2")
    for i, lab in enumerate(yl):
        print("  [{:2d}] Y={} ".format(i + 1, lab), end="")
        if i < len(ys):
            flag = ""
            if ys[i] < 0.5:
                flag = " [SUPHE]"
            print(
                "→ {}  L={:.2f} m{}".format(
                    yl[i + 1] if i + 1 < len(yl) else "-", ys[i], flag
                )
            )
        else:
            print()

    tx = float(getattr(grid, "total_x_m", 0) or 0)
    ty = float(getattr(grid, "total_y_m", 0) or 0)
    print()
    print(
        "Toplam X={:.2f} m  Y={:.2f} m  kesisim={}".format(
            tx, ty, len(xl) * len(yl)
        )
    )

    if ty < min_y_m:
        res.errors.append(
            "Toplam Y={:.2f} m < {:.1f} m (cok pafta/yanlis birim?)".format(
                ty, min_y_m
            )
        )
    if tx > max_x_m:
        res.warnings.append(
            "Toplam X={:.2f} m > {:.0f} m — kontrol edin".format(tx, max_x_m)
        )
    if tx <= 0 or ty <= 0:
        res.errors.append("Toplam aciklik sifir")
    if len(xl) != len(set(xl)):
        res.warnings.append("X etiketlerinde tekrar var")
    if len(yl) != len(set(yl)):
        res.warnings.append("Y etiketlerinde tekrar var")

    res.ok = len(res.errors) == 0
    res.report()
    if not res.ok:
        raise AxisGridError("Aks audit KALDI: " + "; ".join(res.errors))
    return res