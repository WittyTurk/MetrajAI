from __future__ import annotations

import logging
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import ezdxf
from ezdxf import bbox


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).upper()
    return " ".join(value.split())


def entity_text(entity) -> str:
    if entity.dxftype() == "TEXT":
        return str(entity.dxf.text).strip()
    if entity.dxftype() == "MTEXT":
        return str(entity.plain_text()).strip()
    return ""


def entity_box(entity):
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


def main() -> None:
    logging.getLogger("ezdxf").setLevel(logging.ERROR)
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "INPUT2/statik/sutculer_32.dxf")
    document = ezdxf.readfile(path)
    entities = list(document.modelspace())
    boxed_entities = [
        (entity, box) for entity in entities if (box := entity_box(entity)) is not None
    ]

    title_rows = []
    for entity in entities:
        text = entity_text(entity)
        key = normalize(text)
        if "PLAN" not in key or not any(
            token in key for token in ("KALIP", "DONATI", "APLIKASYON", "TEMEL", "MERDIVEN")
        ):
            continue
        point = entity.dxf.insert
        title_rows.append((float(point.x), float(point.y), text.replace("\n", " / ")))

    print("TITLES")
    for x, y, text in sorted(title_rows):
        print(f"{x:10.2f} {y:10.2f}  {text}")

    primary = [
        row
        for row in sorted(title_rows)
        if any(
            token in normalize(row[2])
            for token in ("KALIP PLANI", "DONATI PLANI", "APLIKASYON PLANI")
        )
        and "MERDIVEN" not in normalize(row[2])
    ]
    if not primary:
        return

    print("\nREGIONS")
    xs = [row[0] for row in primary]
    boundaries = [float("-inf")]
    boundaries.extend((xs[index] + xs[index + 1]) / 2 for index in range(len(xs) - 1))
    boundaries.append(float("inf"))

    for index, (x, _y, title) in enumerate(primary):
        title_filter = normalize(sys.argv[2]) if len(sys.argv) > 2 else ""
        if title_filter and title_filter not in normalize(title):
            continue
        left, right = boundaries[index], boundaries[index + 1]
        counts = Counter()
        layer_counts = Counter()
        insert_names = Counter()
        texts = []
        spans = []
        for entity, box in boxed_entities:
            center_x = (box[0] + box[2]) / 2
            if not (left <= center_x < right):
                continue
            counts[entity.dxftype()] += 1
            layer_counts[(entity.dxftype(), normalize(entity.dxf.layer))] += 1
            if entity.dxftype() == "INSERT":
                insert_names[normalize(entity.dxf.name)] += 1
            text = entity_text(entity)
            if text and (
                re.search(r"[KPDCT]\s*\d", normalize(text))
                or "/" in text
                or "CM" in normalize(text)
                or "DOSEME" in normalize(text)
            ):
                texts.append((box[0], box[1], text.replace("\n", " / ")))
            spans.append((box[0], box[1], box[2], box[3]))

        print(f"\n[{index:02}] x={x:.1f} interval=({left:.1f},{right:.1f}) {title}")
        print("types", counts.most_common(10))
        print("layers", layer_counts.most_common(18))
        print("blocks", insert_names.most_common(14))
        print("texts", sorted(texts, key=lambda row: (-row[1], row[0]))[:20])
        if spans:
            print(
                "extent",
                (
                    min(b[0] for b in spans),
                    min(b[1] for b in spans),
                    max(b[2] for b in spans),
                    max(b[3] for b in spans),
                ),
            )


if __name__ == "__main__":
    main()
