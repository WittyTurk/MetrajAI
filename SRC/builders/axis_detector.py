# -*- coding: utf-8 -*-

from collections import defaultdict
import re
import math


class AxisDetector:
    """
    Statik / mimari plandan aks etiketlerini okur.
    Büyük projeler için optimize edilmiştir.

    Destekler:
    - TEXT ve MTEXT
    - Tekrarlayan pafta/detay kopyaları
    - 1,2,3... ve A,B,C... etiketleri
    - Otomatik birim tahmini (mm / cm)
    - En tutarlı grid grubunu seçme
    """

    # Aynı gruba ait sayılma toleransı (çizim biriminde)
    GROUP_TOLERANCE = 5000.0

    def __init__(self, project):
        self.project = project

    # -------------------------------------------------

    def detect(self):
        print()
        print("=" * 55)
        print("AXIS DETECTOR (Optimize - Büyük Proje)")
        print("=" * 55)

        labels = self._collect_labels()
        print(f"Toplam aks etiketi : {len(labels)}")

        if not labels:
            print("Aks etiketi bulunamadı.")
            self.project.x_axes = []
            self.project.y_axes = []
            return [], []

        groups = self._group_labels(labels)
        print(f"Grid grubu sayısı  : {len(groups)}")

        best = self._select_best_group(groups)
        if best is None:
            print("Uygun grid grubu seçilemedi.")
            self.project.x_axes = []
            self.project.y_axes = []
            return [], []

        x_axes, y_axes, unit = self._build_axes_from_group(best)

        print()
        print("=" * 55)
        print("SONUÇ")
        print("=" * 55)
        print(f"Birim tahmini      : {unit}")
        print(f"XX Axis Count      : {len(x_axes)}")
        print(f"YY Axis Count      : {len(y_axes)}")

        print("\nXX POSITIONS:")
        for i, x in enumerate(x_axes, 1):
            print(f"  {i:>2} : {x:.1f}")

        print("\nYY POSITIONS:")
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for i, y in enumerate(y_axes):
            print(f"  {letters[i]:>2} : {y:.1f}")

        # Aralık raporu
        self._print_spacings(x_axes, y_axes, unit)

        self.project.x_axes = x_axes
        self.project.y_axes = y_axes
        self.project.axis_unit = unit

        return x_axes, y_axes

    # -------------------------------------------------

    def _collect_labels(self):
        """TEXT + MTEXT etiketlerini topla"""
        labels = []  # {text, x, y, is_numeric}

        for e in self.project.modelspace:
            layer = e.dxf.layer.upper().replace("İ", "I").replace("Ş", "S")
            if "AKS" not in layer and "EKSEN" not in layer and "AXIS" not in layer:
                continue

            text = None
            x = y = None

            if e.dxftype() == "TEXT":
                text = e.dxf.text.strip().upper()
                x = e.dxf.insert.x
                y = e.dxf.insert.y
            elif e.dxftype() == "MTEXT":
                raw = e.text if hasattr(e, "text") else e.dxf.text
                # MTEXT format kodlarını temizle
                text = re.sub(r"\\[A-Za-z].*;", "", raw).strip().upper()
                text = re.sub(r"[{}]", "", text).strip()
                x = e.dxf.insert.x
                y = e.dxf.insert.y

            if not text or x is None:
                continue

            # Sadece tek rakam veya tek harf
            if re.match(r"^[1-9]$", text):
                labels.append({"text": text, "x": x, "y": y, "is_numeric": True})
            elif re.match(r"^[A-Z]$", text):
                labels.append({"text": text, "x": x, "y": y, "is_numeric": False})

        return labels

    # -------------------------------------------------

    def _group_labels(self, labels):
        """
        Yakın etiketleri aynı grid grubuna topla.
        Büyük projelerde aynı 1-2-3 / A-B-C seti birden fazla kez çizilmiş olabilir.
        """
        if not labels:
            return []

        # Basit spatial clustering (merkeze göre)
        groups = []

        for lab in labels:
            placed = False
            for g in groups:
                # Grubun mevcut merkezine uzaklık
                cx = sum(i["x"] for i in g) / len(g)
                cy = sum(i["y"] for i in g) / len(g)
                dist = math.hypot(lab["x"] - cx, lab["y"] - cy)
                if dist <= self.GROUP_TOLERANCE:
                    g.append(lab)
                    placed = True
                    break
            if not placed:
                groups.append([lab])

        return groups

    # -------------------------------------------------

    def _select_best_group(self, groups):
        """
        En iyi grid grubunu seç:
        - Hem rakam hem harf içeren
        - En fazla etiket içeren
        """
        scored = []
        for g in groups:
            nums = [i for i in g if i["is_numeric"]]
            lets = [i for i in g if not i["is_numeric"]]
            if not nums or not lets:
                continue
            score = len(nums) + len(lets)
            scored.append((score, g))

        if not scored:
            # Sadece rakam veya sadece harf varsa en büyüğü al
            scored = [(len(g), g) for g in groups]

        if not scored:
            return None

        scored.sort(key=lambda t: -t[0])
        best = scored[0][1]
        print(f"Seçilen grup etiket sayısı : {len(best)}")
        return best

    # -------------------------------------------------

    def _build_axes_from_group(self, group):
        """
        Gruptan X ve Y aks listesi çıkar.
        Aynı etiketin birden fazla kopyası varsa ortalama al.
        """
        x_map = defaultdict(list)  # "1" → [x1, x2, ...]
        y_map = defaultdict(list)  # "A" → [y1, y2, ...]

        for lab in group:
            if lab["is_numeric"]:
                x_map[lab["text"]].append(lab["x"])
            else:
                y_map[lab["text"]].append(lab["y"])

        x_axes = []
        for key in sorted(x_map.keys(), key=lambda t: int(t)):
            vals = x_map[key]
            x_axes.append(sum(vals) / len(vals))

        y_axes = []
        for key in sorted(y_map.keys()):
            vals = y_map[key]
            y_axes.append(sum(vals) / len(vals))

        unit = self._guess_unit(x_axes, y_axes)
        return x_axes, y_axes, unit

    # -------------------------------------------------

    def _guess_unit(self, x_axes, y_axes):
        """
        Aralık büyüklüğüne bakarak birim tahmin et.
        8.50 m beklenen aralık:
          - mm çizimde ≈ 8500
          - cm çizimde ≈ 850
        """
        gaps = []
        for axes in (x_axes, y_axes):
            for i in range(len(axes) - 1):
                gaps.append(abs(axes[i + 1] - axes[i]))

        if not gaps:
            return "mm"

        avg_gap = sum(gaps) / len(gaps)

        # 500–2000 arası → büyük ihtimalle cm (850 cm = 8.50 m)
        if 400 <= avg_gap <= 2500:
            return "cm"
        return "mm"

    # -------------------------------------------------

    def _print_spacings(self, x_axes, y_axes, unit):
        divisor = 100.0 if unit == "cm" else 1000.0
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        print("\n" + "=" * 55)
        print("AKS ARALIKLARI")
        print("=" * 55)

        print("\nXX Aralıkları:")
        if len(x_axes) >= 2:
            for i in range(len(x_axes) - 1):
                dist = abs(x_axes[i + 1] - x_axes[i])
                print(f"  {i+1} → {i+2} : {dist/divisor:.2f} m  ({dist:.1f} {unit})")
        else:
            print("  Yeterli X aksı yok")

        print("\nYY Aralıkları:")
        if len(y_axes) >= 2:
            for i in range(len(y_axes) - 1):
                dist = abs(y_axes[i + 1] - y_axes[i])
                print(f"  {letters[i]} → {letters[i+1]} : {dist/divisor:.2f} m  ({dist:.1f} {unit})")
        else:
            print("  Yeterli Y aksı yok")