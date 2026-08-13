# -*- coding: utf-8 -*-
"""
DXF Wall Builder — tüm boy/kalınlık DXF'ten.

  1) Kapalı LWPOLYLINE → uzun kenar = boy, kısa kenar = kalınlık
  2) LINE / açık LWPOLYLINE → boy DXF'ten, kalınlık = 0 (yoksa uydurma)
  3) Çok kısa segment elenir
"""

from __future__ import annotations

import math
from SRC.builders.layer_filter import LayerFilter
from SRC.models.point import Point
from SRC.models.wall import Wall


def _norm(s: str) -> str:
    return (
        s.upper()
        .replace("İ", "I").replace("Ş", "S").replace("Ğ", "G")
        .replace("Ü", "U").replace("Ö", "O").replace("Ç", "C")
    )


class WallBuilder:
    DEFAULT_WALL_LAYERS = [
        "sıva", "SIVA", "DUVAR", "Duvar", "gör", "GÖR", "WALL",
    ]
    MIN_SEGMENT_LENGTH = 50.0

    def __init__(self, project, wall_layers=None, min_length=None):
        self.project = project
        self.msp = project.modelspace
        self.filter = LayerFilter(project.modelspace)
        self.wall_layers = wall_layers or self.DEFAULT_WALL_LAYERS
        self.min_length = min_length if min_length is not None else self.MIN_SEGMENT_LENGTH

    def build(self):
        print()
        print("=" * 55)
        print("WALL BUILDER (DXF birebir)")
        print("=" * 55)

        entities_by_layer = self._collect_entities()
        self.project.walls.clear()

        wall_id = 1
        stats = {"polygon": 0, "line": 0, "polyline_seg": 0, "skipped_short": 0}

        for layer, entities in entities_by_layer.items():
            for entity in entities:
                for w in self._entity_to_walls(entity, wall_id, stats):
                    self.project.walls.append(w)
                    wall_id += 1

        self._print_summary(stats)
        return self.project.walls

    def _collect_entities(self):
        result = {}
        print("\nKatman taraması:")
        for layer in self.wall_layers:
            found = self._get_layer(layer)
            if found:
                result[layer] = found
                print(f"  {layer:20} → {len(found)} entity")
        if not result:
            # DXF'te isim farklıysa otomatik tara
            result = self._auto_layers()
        if not result:
            print("  Hiç duvar katmanı bulunamadı.")
        return result

    def _get_layer(self, layer_name: str):
        target = _norm(layer_name)
        out = []
        for e in self.msp:
            if _norm(e.dxf.layer) == target:
                out.append(e)
        return out

    def _auto_layers(self):
        keys = ("SIVA", "DUVAR", "WALL", "GOR")
        result = {}
        for e in self.msp:
            nl = _norm(e.dxf.layer)
            if any(k in nl for k in keys):
                result.setdefault(e.dxf.layer, []).append(e)
        for layer, ents in result.items():
            print(f"  {layer:20} → {len(ents)} entity (otomatik)")
        return result

    def _entity_to_walls(self, entity, start_id, stats):
        walls = []
        dxftype = entity.dxftype()

        if dxftype == "LINE":
            w = self._line_to_wall(entity, start_id)
            if w:
                walls.append(w)
                stats["line"] += 1
            else:
                stats["skipped_short"] += 1

        elif dxftype == "LWPOLYLINE":
            pts = list(entity.get_points())
            if entity.closed and len(pts) >= 4:
                w = self._closed_polygon_to_wall(entity, start_id)
                if w:
                    walls.append(w)
                    stats["polygon"] += 1
                else:
                    stats["skipped_short"] += 1
            else:
                segs = self._polyline_to_walls(entity, start_id)
                walls.extend(segs)
                stats["polyline_seg"] += len(segs)
                if not segs:
                    stats["skipped_short"] += 1

        return walls

    def _line_to_wall(self, entity, wall_id):
        start = Point(entity.dxf.start.x, entity.dxf.start.y)
        end = Point(entity.dxf.end.x, entity.dxf.end.y)
        if start.distance_to(end) < self.min_length:
            return None
        return Wall(
            id=wall_id,
            start=start,
            end=end,
            layer=entity.dxf.layer,
            entity_type="LINE",
            source_handle=entity.dxf.handle,
            thickness=0.0,  # DXF'te kalınlık yok → uydurma yok
        )

    def _polyline_to_walls(self, entity, start_id):
        points = list(entity.get_points())
        if len(points) < 2:
            return []
        walls = []
        wid = start_id
        for i in range(len(points) - 1):
            start = Point(float(points[i][0]), float(points[i][1]))
            end = Point(float(points[i + 1][0]), float(points[i + 1][1]))
            if start.distance_to(end) < self.min_length:
                continue
            walls.append(Wall(
                id=wid,
                start=start,
                end=end,
                layer=entity.dxf.layer,
                entity_type="LWPOLYLINE",
                source_handle=entity.dxf.handle,
                thickness=0.0,
            ))
            wid += 1
        return walls

    def _closed_polygon_to_wall(self, entity, wall_id):
        """Uzun kenar = boy, kısa kenar = kalınlık (ikisi de DXF)."""
        pts = [(float(p[0]), float(p[1])) for p in entity.get_points()]
        n = len(pts)
        if n < 4:
            return None

        edges = []
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            edges.append({
                "length": math.hypot(x2 - x1, y2 - y1),
                "start": (x1, y1),
                "end": (x2, y2),
            })

        edges_sorted = sorted(edges, key=lambda e: e["length"])
        thickness = edges_sorted[0]["length"]
        long_edges = [e for e in edges if e["length"] > thickness * 1.5]
        if not long_edges:
            long_edges = [edges_sorted[-1]]

        main = max(long_edges, key=lambda e: e["length"])
        if main["length"] < self.min_length:
            return None

        # İki uzun kenar varsa merkez eksen (DXF geometrisi)
        if len(long_edges) >= 2:
            e1, e2 = long_edges[0], long_edges[1]
            s1, t1 = e1["start"], e1["end"]
            s2, t2 = e2["start"], e2["end"]
            if math.hypot(s1[0] - s2[0], s1[1] - s2[1]) > math.hypot(
                s1[0] - t2[0], s1[1] - t2[1]
            ):
                s2, t2 = t2, s2
            start = Point((s1[0] + s2[0]) / 2, (s1[1] + s2[1]) / 2)
            end = Point((t1[0] + t2[0]) / 2, (t1[1] + t2[1]) / 2)
        else:
            start = Point(main["start"][0], main["start"][1])
            end = Point(main["end"][0], main["end"][1])

        return Wall(
            id=wall_id,
            start=start,
            end=end,
            layer=entity.dxf.layer,
            entity_type="LWPOLYLINE",
            source_handle=entity.dxf.handle,
            thickness=thickness,
        )

    def _print_summary(self, stats):
        walls = self.project.walls
        print()
        print(f"Poligon (boy+kalınlık DXF): {stats['polygon']}")
        print(f"LINE (sadece boy DXF)     : {stats['line']}")
        print(f"Polyline segment          : {stats['polyline_seg']}")
        print(f"Atlanan (kısa)            : {stats['skipped_short']}")
        print(f"TOPLAM WALL               : {len(walls)}")

        if not walls:
            return

        lengths = [w.length for w in walls]
        total = sum(lengths)
        with_t = [w for w in walls if w.thickness > 0]
        without_t = len(walls) - len(with_t)

        print()
        print(f"Toplam uzunluk : {total:.1f} (çizim birimi)")
        print(f"Kalınlığı DXF'ten gelen : {len(with_t)}")
        print(f"Kalınlığı DXF'te yok    : {without_t}  (T=0, uydurulmadı)")
        if with_t:
            ts = [w.thickness for w in with_t]
            print(f"Ort. kalınlık  : {sum(ts)/len(ts):.1f}")

        print()
        print("İlk 15 duvar:")
        for w in walls[:15]:
            print(
                f"  Wall {w.id:3d}  L={w.length:8.1f}  T={w.thickness:6.1f}  "
                f"[{w.layer}]"
            )
        if len(walls) > 15:
            print(f"  ... ve {len(walls) - 15} duvar daha")