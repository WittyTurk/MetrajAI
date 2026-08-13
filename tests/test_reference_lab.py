from __future__ import annotations

import hashlib
import json
from pathlib import Path

import ezdxf
import pytest

from metrajai.analyzers import DxfAnalyzer
from metrajai.analyzers.reference_dxf import REFERENCE_APPID
from metrajai.contracts import Discipline, DrawingUnit, ReviewStatus, SourceFile, SourceFormat
from metrajai.reference_lab import (
    DEFAULT_MANIFEST,
    ReferenceLabError,
    fetch_source,
    load_manifest,
    validate_references,
)


def test_reference_manifest_pins_license_attribution_commit_and_checksum() -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)

    assert [dataset["id"] for dataset in manifest["datasets"]] == ["pcert", "duplex"]
    for dataset in manifest["datasets"]:
        assert dataset["license"] == "CC-BY-4.0"
        assert dataset["attribution"]
        assert len(dataset["commit"]) == 40
        assert dataset["commit"] in dataset["source_page"]
        for source in dataset["sources"]:
            assert dataset["commit"] in source["url"]
            assert len(source["sha256"]) == 64
            assert source["size_bytes"] > 0


def test_fetch_reuses_verified_copy_and_blocks_checksum_mismatch(tmp_path: Path) -> None:
    payload = b"verified IFC cache"
    source = {
        "id": "fixture",
        "url": "https://invalid.example/fixture.ifc",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }
    destination = tmp_path / "fixture.ifc"
    destination.write_bytes(payload)

    assert fetch_source(source, destination) == destination

    destination.write_bytes(b"tampered")
    with pytest.raises(ReferenceLabError, match="SHA-256"):
        fetch_source(source, destination)


def _reference_source(path: Path, *, confirmed: bool) -> SourceFile:
    return SourceFile(
        id="src_reference",
        project_id="prj_reference",
        original_name=path.name,
        stored_path=str(path),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        size_bytes=path.stat().st_size,
        source_format=SourceFormat.DXF,
        discipline=Discipline.STRUCTURAL,
        role="reference_validation",
        floor="Ground",
        drawing_unit=DrawingUnit.MM if confirmed else DrawingUnit.UNKNOWN,
        detected_unit=DrawingUnit.MM if confirmed else DrawingUnit.UNKNOWN,
        unit_confirmed=confirmed,
    )


def _write_reference_fixture(path: Path, *, insunits: int) -> None:
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = insunits
    document.appids.add(REFERENCE_APPID)
    block = document.blocks.new("REF_COLUMN")
    block.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True)
    metadata = [
        (1000, "guid=2O2Fr$t4X7Zf8NOew3FLOH"),
        (1000, "type=column"),
        (1000, "discipline=structural"),
        (1000, "dataset=fixture"),
        (1000, "source=fixture-structural"),
        (1000, "storey=Ground"),
        (1000, "ifc_class=IfcColumn"),
        (1000, "dxf_unit=mm"),
        (1000, "width_m=0.4"),
        (1000, "depth_m=0.6"),
        (1000, "height_m=3.2"),
        (1000, "volume_m3=0.768"),
    ]
    first = document.modelspace().add_blockref(
        "REF_COLUMN", (0, 0), dxfattribs={"layer": "S-COLUMN"}
    )
    first.set_xdata(REFERENCE_APPID, metadata)
    duplicate = document.modelspace().add_blockref(
        "REF_COLUMN", (100000, 100000), dxfattribs={"layer": "S-COLUMN", "xscale": -1}
    )
    duplicate.set_xdata(REFERENCE_APPID, metadata)
    document.modelspace().add_circle(
        (10_000_000, 10_000_000), 100, dxfattribs={"layer": "REF-NOISE"}
    )
    document.saveas(path)


def test_reference_dxf_preserves_global_id_and_deduplicates_hard_copy(tmp_path: Path) -> None:
    path = tmp_path / "reference.dxf"
    _write_reference_fixture(path, insunits=4)

    elements, warnings, unit = DxfAnalyzer().analyze(
        _reference_source(path, confirmed=True), path
    )

    assert unit == DrawingUnit.MM
    assert len(elements) == 1
    assert elements[0].properties["reference_guid"] == "2O2Fr$t4X7Zf8NOew3FLOH"
    assert elements[0].measurements["volume_m3"] == pytest.approx(0.768)
    assert elements[0].review_status == ReviewStatus.PENDING
    assert any(warning.code == "REFERENCE_DXF_DUPLICATES_SKIPPED" for warning in warnings)


def test_reference_dxf_without_units_is_blocked_for_review(tmp_path: Path) -> None:
    path = tmp_path / "unitless-reference.dxf"
    _write_reference_fixture(path, insunits=0)

    elements, warnings, unit = DxfAnalyzer().analyze(
        _reference_source(path, confirmed=False), path
    )

    assert unit == DrawingUnit.UNKNOWN
    assert elements
    assert all(element.review_status == ReviewStatus.NEEDS_REVIEW for element in elements)
    assert all("unit_confirmation_required" in element.issues for element in elements)
    assert any(
        warning.code == "REFERENCE_DXF_UNIT_CONFIRMATION_REQUIRED" for warning in warnings
    )


def test_real_reference_gate_runs_only_when_reference_data_is_present() -> None:
    root = DEFAULT_MANIFEST.parent.parent / "reference-data"
    pcert_manifest = root / "generated" / "pcert" / "generated-manifest.json"
    if not pcert_manifest.exists():
        pytest.skip("isteğe bağlı referans verisi indirilmedi")
    manifest = load_manifest(DEFAULT_MANIFEST)

    reports = validate_references(manifest, selected="pcert", data_root=root)

    assert reports[0]["dataset_id"] == "pcert"
    assert reports[0]["passed"] is True
    persisted = json.loads(
        (root / "generated" / "pcert" / "validation.json").read_text(encoding="utf-8")
    )
    assert persisted["passed"] is True
