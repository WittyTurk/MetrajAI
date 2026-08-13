from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from metrajai.analyzers import DxfAnalyzer
from metrajai.contracts import (
    Discipline,
    DrawingUnit,
    FloorKind,
    SheetKind,
    SourceFile,
)
from metrajai.service import EngineService
from metrajai.workspace import ProjectWorkspace

ROOT = Path(__file__).resolve().parents[1]


def source_for(path: Path, *, unit: DrawingUnit = DrawingUnit.UNKNOWN) -> SourceFile:
    content = path.read_bytes()
    return SourceFile(
        project_id="prj_pilot_validation",
        original_name=path.name,
        stored_path=str(path),
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        discipline=Discipline.STRUCTURAL,
        role="pilot_validation",
        drawing_unit=unit,
        unit_confirmed=unit != DrawingUnit.UNKNOWN,
    )


def type_counts(elements) -> dict[str, int]:
    return dict(sorted(Counter(item.element_type for item in elements).items()))


def main() -> None:
    paths = {
        "taziye": ROOT / "INPUT/statik/TAZIYE-EVLERI_STATIK.dxf",
        "defter_plan": ROOT / "INPUT/SU.01 KALIP VE DONATI (DEFTERDARLIK).dxf",
        "defter_columns": ROOT / "INPUT/SU.02 KOLON APLİKASYON (DEFTERDARLIK).dxf",
        "sutculer": ROOT / "INPUT2/statik/sutculer_32.dxf",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise SystemExit("Pilot kaynakları eksik: " + ", ".join(missing))

    analyzer = DxfAnalyzer()
    taziye, _, _ = analyzer.analyze(source_for(paths["taziye"]), paths["taziye"])
    sutculer, sutculer_warnings, _ = analyzer.analyze(
        source_for(paths["sutculer"], unit=DrawingUnit.CM),
        paths["sutculer"],
    )

    with TemporaryDirectory(prefix="metrajai-defter-pilot-") as temporary:
        workspace = ProjectWorkspace.create(Path(temporary) / "defter.metrajai", "Defter Pilot")
        workspace.add_source(
            paths["defter_plan"],
            discipline=Discipline.STRUCTURAL,
            role="kalip",
            floor="GENEL",
            floor_kind=FloorKind.GENERAL,
            sheet_kind=SheetKind.PLAN,
            drawing_unit=DrawingUnit.CM,
        )
        workspace.add_source(
            paths["defter_columns"],
            discipline=Discipline.STRUCTURAL,
            role="kolon aplikasyon",
            floor="GENEL",
            floor_kind=FloorKind.GENERAL,
            sheet_kind=SheetKind.COLUMN_APPLICATION,
            drawing_unit=DrawingUnit.CM,
        )
        run = EngineService(workspace).analyze()
        if run.status.value != "completed":
            raise SystemExit(f"Defter pilot analizi başarısız: {run.message}")
        defter = workspace.list_elements()

    snapshots = {
        "taziye": {"count": len(taziye), "by_type": type_counts(taziye)},
        "defter": {"count": len(defter), "by_type": type_counts(defter)},
        "sutculer": {"count": len(sutculer), "by_type": type_counts(sutculer)},
    }
    expected = {
        "taziye": {
            "count": 88,
            "by_type": {"beam": 24, "column": 9, "rebar": 39, "slab": 16},
        },
        "defter": {
            "count": 90,
            "by_type": {"beam": 15, "column": 55, "stair": 20},
        },
        "sutculer": {
            "count": 385,
            "by_type": {
                "beam": 162,
                "column": 108,
                "raft": 1,
                "shear_wall": 8,
                "slab": 98,
                "stair": 8,
            },
        },
    }

    errors = [
        f"{name}: beklenen {expected[name]}, bulunan {snapshot}"
        for name, snapshot in snapshots.items()
        if snapshot != expected[name]
    ]
    rafts = [item for item in sutculer if item.element_type == "raft"]
    stair_items = [item for item in sutculer if item.element_type == "stair"]
    void_total = round(
        sum(item.measurements.get("void_area_m2", 0.0) for item in sutculer), 6
    )
    formwork_ready = sum(
        item.element_type == "beam" and item.measurements.get("formwork_area_m2", 0.0) > 0
        for item in sutculer
    )
    if len(rafts) != 1 or abs(rafts[0].measurements.get("thickness_m", 0.0) - 0.8) > 1e-6:
        errors.append("Sütçüler: 80 cm kalınlıklı tek radye kanıtı korunmadı")
    if void_total != 7.8:
        errors.append(f"Sütçüler: beklenen döşeme boşluğu 7.8 m², bulunan {void_total} m²")
    if formwork_ready != 93:
        errors.append(f"Sütçüler: beklenen kanıtlı kiriş kalıbı 93, bulunan {formwork_ready}")
    if any("HATIL" in item.layer.upper() for item in stair_items):
        errors.append("Sütçüler: merdiven altı hatılı yeniden merdiven adayı oldu")
    if sum("blocking:stair_floor_repeat_required" in item.issues for item in stair_items) != 4:
        errors.append("Sütçüler: dört tip merdiven tekrar güvenlik kapısı korunmadı")
    warning_codes = {item.code for item in sutculer_warnings}
    if "TYPICAL_STAIR_REPEAT_REQUIRED" not in warning_codes:
        errors.append("Sütçüler: tip merdiven tekrar uyarısı eksik")

    result = {
        "passed": not errors,
        "snapshots": snapshots,
        "sutculer_invariants": {
            "raft_area_m2": rafts[0].measurements["area_m2"] if rafts else None,
            "raft_thickness_m": rafts[0].measurements["thickness_m"] if rafts else None,
            "slab_void_area_m2": void_total,
            "beam_formwork_ready": formwork_ready,
            "typical_stairs_blocked": sum(
                "blocking:stair_floor_repeat_required" in item.issues for item in stair_items
            ),
        },
        "errors": errors,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
