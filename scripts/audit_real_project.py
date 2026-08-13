from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from metrajai.analyzers import DxfAnalyzer
from metrajai.contracts import Discipline, DrawingUnit, SourceFile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--unit", choices=("mm", "cm", "m"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    content = args.path.read_bytes()
    unit = DrawingUnit(args.unit) if args.unit else DrawingUnit.UNKNOWN
    source = SourceFile(
        project_id="prj_audit",
        original_name=args.path.name,
        stored_path=str(args.path),
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        discipline=Discipline.STRUCTURAL,
        role="audit",
        drawing_unit=unit,
        unit_confirmed=args.unit is not None,
    )
    elements, warnings, detected_unit = DxfAnalyzer().analyze(source, args.path)
    by_type = Counter(element.element_type for element in elements)
    by_floor: dict[str, Counter[str]] = defaultdict(Counter)
    for element in elements:
        by_floor[element.floor][element.element_type] += 1
    summary = {
        "source": args.path.name,
        "detected_unit": detected_unit.value,
        "chosen_unit": (unit if args.unit else detected_unit).value,
        "element_count": len(elements),
        "by_type": dict(sorted(by_type.items())),
        "by_floor": {
            floor: dict(sorted(counts.items())) for floor, counts in sorted(by_floor.items())
        },
        "warnings": [warning.model_dump(mode="json") for warning in warnings],
        "elements": [element.model_dump(mode="json") for element in elements],
    }
    print(
        json.dumps(
            {key: value for key, value in summary.items() if key != "elements"},
            indent=2,
            ensure_ascii=False,
        )
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
