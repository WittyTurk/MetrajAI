from __future__ import annotations

import math
import re
import sys
import unicodedata
from collections import Counter

import ezdxf


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).upper()
    return " ".join(value.split())


def text_value(entity) -> str:
    if entity.dxftype() == "TEXT":
        return str(entity.dxf.text).strip()
    if entity.dxftype() == "MTEXT":
        return str(entity.plain_text()).strip()
    return ""


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "INPUT2/statik/sutculer_32.dxf"
    left = float(sys.argv[2]) if len(sys.argv) > 2 else 83576.7
    right = float(sys.argv[3]) if len(sys.argv) > 3 else 91947.1
    document = ezdxf.readfile(path)
    entities = list(document.modelspace())

    lines = []
    for entity in entities:
        if entity.dxftype() != "LINE" or normalize(entity.dxf.layer) != "KIRIS":
            continue
        start = (float(entity.dxf.start.x), float(entity.dxf.start.y))
        end = (float(entity.dxf.end.x), float(entity.dxf.end.y))
        center = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        if not left <= center[0] < right:
            continue
        length = math.dist(start, end)
        lines.append((entity, start, end, center, length))

    print("line_count", len(lines))
    print("length_bins_cm", Counter(round(row[4] / 10) * 10 for row in lines).most_common(30))
    print("long_lines")
    for entity, start, end, _center, length in sorted(lines, key=lambda row: -row[4])[:40]:
        print(
            entity.dxf.handle,
            tuple(round(v, 1) for v in start),
            tuple(round(v, 1) for v in end),
            round(length, 2),
        )

    label_pattern = re.compile(
        r"(?P<label>[A-Z]{1,4}\d+[A-Z0-9-]*)\s*\(\s*(?P<width>\d+)\s*/\s*(?P<height>\d+)\s*\)",
        re.IGNORECASE,
    )
    print("\nlabels")
    for entity in entities:
        if entity.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        value = text_value(entity)
        match = label_pattern.search(normalize(value))
        if not match:
            continue
        point = entity.dxf.insert
        location = (float(point.x), float(point.y))
        if not left <= location[0] < right:
            continue
        nearest = sorted(
            [
                (
                    min(
                        math.dist(location, row[1]),
                        math.dist(location, row[2]),
                        math.dist(location, row[3]),
                    ),
                    row,
                )
                for row in lines
            ],
            key=lambda item: item[0],
        )[:6]
        print(
            entity.dxf.handle,
            normalize(value),
            tuple(round(v, 1) for v in location),
            [
                (
                    round(distance, 1),
                    row[0].dxf.handle,
                    tuple(round(v, 1) for v in row[1]),
                    tuple(round(v, 1) for v in row[2]),
                    round(row[4], 1),
                )
                for distance, row in nearest
            ],
        )

    print("\nslab_texts")
    for entity in entities:
        if entity.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        layer = normalize(entity.dxf.layer)
        if layer not in {"DOSEME ADI", "KA_KOT"}:
            continue
        point = entity.dxf.insert
        location = (float(point.x), float(point.y))
        if left <= location[0] < right:
            print(
                entity.dxf.handle,
                layer,
                normalize(text_value(entity)),
                tuple(round(v, 1) for v in location),
                round(float(entity.dxf.get("rotation", 0.0)), 1),
            )


if __name__ == "__main__":
    main()
