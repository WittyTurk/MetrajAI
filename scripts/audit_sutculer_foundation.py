from __future__ import annotations

import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.math import area as polygon_area
from ezdxf.path import from_hatch, make_path

from metrajai.analyzers.multiview_structural import discover_structural_plan_views


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(text.upper().split())


def text_value(entity) -> str:
    if entity.dxftype() == "TEXT":
        return str(entity.dxf.text).strip()
    if entity.dxftype() == "MTEXT":
        return str(entity.plain_text()).strip()
    return ""


def raw_box(entity):
    try:
        value = bbox.extents([entity], fast=True)
    except Exception:
        return None
    if not value.has_data:
        return None
    return (
        float(value.extmin.x),
        float(value.extmin.y),
        float(value.extmax.x),
        float(value.extmax.y),
    )


def lwpolyline_area(entity) -> float:
    try:
        vertices = list(make_path(entity).flattening(distance=0.1))
        return abs(float(polygon_area(vertices)))
    except Exception:
        points = [(float(point[0]), float(point[1])) for point in entity.get_points("xy")]
        return abs(
            sum(
                first[0] * second[1] - second[0] * first[1]
                for first, second in zip(points, points[1:] + points[:1], strict=True)
            )
            / 2
        )


def hatch_metrics(entity) -> tuple[float, int]:
    total = 0.0
    paths = list(from_hatch(entity))
    for path in paths:
        vertices = list(path.flattening(distance=0.1))
        total += abs(float(polygon_area(vertices)))
    return total, len(paths)


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "INPUT2/statik/sutculer_32.dxf")
    document = ezdxf.readfile(path)
    entities = list(document.modelspace())
    left, right = -20000.0, 8655.0
    scale = 0.01

    rows = []
    for entity in entities:
        box = raw_box(entity)
        if box is None or not left <= (box[0] + box[2]) / 2 < right:
            continue
        if entity.dxftype() == "LWPOLYLINE" and bool(getattr(entity, "closed", False)):
            area = lwpolyline_area(entity)
            paths = 1
        elif entity.dxftype() == "HATCH":
            area, paths = hatch_metrics(entity)
        else:
            continue
        width = abs(box[2] - box[0]) * scale
        height = abs(box[3] - box[1]) * scale
        rows.append(
            (
                area * scale * scale,
                entity.dxftype(),
                str(entity.dxf.handle),
                normalize(entity.dxf.layer),
                width,
                height,
                tuple(round(value * scale, 3) for value in box),
                paths,
            )
        )

    print("LARGE CLOSED/HATCH GEOMETRIES")
    for row in sorted(rows, reverse=True)[:160]:
        print(
            f"area={row[0]:9.3f} type={row[1]:10} handle={row[2]:8} "
            f"layer={row[3]:24} size={row[4]:7.2f}x{row[5]:7.2f} "
            f"box={row[6]} paths={row[7]}"
        )

    tokens = ("RADYE", "TEMEL", "80CM", "80 CM", "KALIN", "PLAK", "BOSLUK", "SAFT", "ASANSOR")
    text_rows = []
    for entity in entities:
        value = text_value(entity)
        if not value:
            continue
        point = entity.dxf.insert
        if not left <= float(point.x) < right:
            continue
        key = normalize(value)
        if any(token in key for token in tokens):
            text_rows.append(
                (
                    float(point.x) * scale,
                    float(point.y) * scale,
                    str(entity.dxf.handle),
                    normalize(entity.dxf.layer),
                    value.replace("\n", " / "),
                )
            )
    print("\nFOUNDATION TEXT EVIDENCE")
    for row in sorted(text_rows, key=lambda item: (-item[1], item[0])):
        print(row)

    print("\nLARGE ENTITY LAYERS")
    print(Counter((row[1], row[3]) for row in rows if row[0] >= 1).most_common(80))

    print("\nOPENING-LIKE TEXTS IN ALL FORMWORK REGIONS")
    for entity in entities:
        value = text_value(entity)
        if not value:
            continue
        key = normalize(value)
        if not any(token in key for token in ("BOSLUK", "SAFT", "ASANSOR", "MERDIVEN")):
            continue
        point = entity.dxf.insert
        print(
            round(float(point.x) * scale, 3),
            round(float(point.y) * scale, 3),
            str(entity.dxf.handle),
            normalize(entity.dxf.layer),
            value.replace("\n", " / "),
        )

    print("\nOPENING-LIKE LAYERS")
    layer_counts = Counter()
    for entity in entities:
        layer = normalize(entity.dxf.layer)
        if any(token in layer for token in ("BOSLUK", "SAFT", "ASANSOR", "MERDIVEN")):
            layer_counts[(entity.dxftype(), layer)] += 1
    print(layer_counts.most_common())

    print("\nPAIR DISTANCES FOR LARGE OUTLINES")
    large = [row for row in rows if row[0] > 50]
    for index, first in enumerate(large):
        for second in large[index + 1 :]:
            if first[3] != second[3]:
                continue
            box_a, box_b = first[6], second[6]
            distance = math.dist(
                ((box_a[0] + box_a[2]) / 2, (box_a[1] + box_a[3]) / 2),
                ((box_b[0] + box_b[2]) / 2, (box_b[1] + box_b[3]) / 2),
            )
            if distance < 3:
                print(first[2], second[2], first[3], round(distance, 3), first[0], second[0])

    print("\nDISCOVERED PLAN VIEWS")
    views = discover_structural_plan_views(document)
    for view in views:
        print(
            view.kind,
            view.floor,
            round(view.raw_x_min * scale, 3),
            round(view.raw_x_max * scale, 3),
            round(view.origin[0] * scale, 3),
            view.title,
        )

    print("\nFOUNDATION OUTLINE GROUP LABELS")
    foundation_outlines = [row for row in rows if row[3] == "PENC3" and row[0] > 1000]
    for outline in sorted(foundation_outlines, key=lambda row: row[6][0]):
        box = outline[6]
        labels = []
        structural_text = []
        for entity in entities:
            value = text_value(entity)
            if not value:
                continue
            point = entity.dxf.insert
            x, y = float(point.x) * scale, float(point.y) * scale
            if box[0] <= x <= box[2] and box[1] <= y <= box[3]:
                key = normalize(value)
                if (
                    "H=80" in key
                    or "RADYE" in key
                    or "TEMEL USTU" in key
                    or re.fullmatch(r"P[A-Z]\d+", key)
                ):
                    labels.append((round(x, 3), round(y, 3), str(entity.dxf.handle), value))
                layer = normalize(entity.dxf.layer)
                if any(
                    token in layer
                    for token in ("DOSEME ADI", "KIRIS YAZI", "KOLON YAZI", "TEMEL")
                ):
                    structural_text.append((layer, key))
        print(outline[2], box, "labels=", labels[:100])
        print("  structural_text=", Counter(structural_text).most_common(100))

    print("\nFOUNDATION OUTLINE VERTEX SIGNATURES")
    for outline in sorted(foundation_outlines, key=lambda row: row[6][0]):
        entity = next(item for item in entities if str(item.dxf.handle) == outline[2])
        points = [(float(point[0]) * scale, float(point[1]) * scale) for point in entity.get_points("xy")]
        min_x = min(point[0] for point in points)
        min_y = min(point[1] for point in points)
        signature = [(round(x - min_x, 3), round(y - min_y, 3)) for x, y in points]
        print(outline[2], "count=", len(points), "signature=", signature[:120])

    print("\nOPENING GEOMETRIES PER FORMWORK VIEW")
    for view in views:
        if view.kind not in {"formwork", "foundation"}:
            continue
        candidates = []
        for entity in entities:
            layer = normalize(entity.dxf.layer)
            if not any(token in layer for token in ("BOSLUK", "SAFT", "ASANSOR", "MERDIVEN")):
                continue
            box = raw_box(entity)
            if box is None or not view.contains_raw_x((box[0] + box[2]) / 2):
                continue
            candidates.append(
                (
                    entity.dxftype(),
                    str(entity.dxf.handle),
                    layer,
                    tuple(round(value * scale, 3) for value in box),
                )
            )
        print(view.floor, view.title, len(candidates), candidates[:40])


if __name__ == "__main__":
    main()
