from pathlib import Path

import ezdxf
import pytest
from fastapi.testclient import TestClient

import metrajai.source_preview as source_preview
from metrajai.api import create_app
from metrajai.contracts import Discipline, DrawingUnit, SourceFile, SourceFormat
from metrajai.source_preview import build_source_preview


def _drawing(path: Path) -> str:
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = 4
    plan = document.blocks.new("PLAN")
    plan.add_lwpolyline(
        [(0, 0), (2000, 0), (2000, 1000), (0, 1000)],
        close=True,
        dxfattribs={"layer": "A-WALL"},
    )
    plan.add_text("ZK01", dxfattribs={"insert": (400, 400), "height": 200})
    root = document.modelspace().add_blockref("PLAN", (10000, 0), dxfattribs={"rotation": 90})
    document.modelspace().add_line((50000, 0), (51000, 0), dxfattribs={"layer": "DETAIL"})
    document.saveas(path)
    return root.dxf.handle


def test_raw_preview_keeps_nested_transform_and_ignores_other_region(tmp_path: Path) -> None:
    path = tmp_path / "plan.dxf"
    handle = _drawing(path)
    source = SourceFile(
        project_id="test",
        original_name=path.name,
        stored_path=str(path),
        sha256="test",
        size_bytes=path.stat().st_size,
        source_format=SourceFormat.DXF,
        discipline=Discipline.ARCHITECTURAL,
        role="mimari",
        drawing_unit=DrawingUnit.MM,
        unit_confirmed=True,
    )

    preview = build_source_preview(source, path, handle)
    assert preview["region_id"] == handle
    assert preview["unit"] == "mm"
    assert len(preview["strokes"]) == 1
    assert preview["strokes"][0]["role"] == "wall"
    assert preview["bounds"] == pytest.approx([9, 0, 10, 2])
    assert preview["texts"][0]["text"] == "ZK01"
    assert preview["truncated"] is False
    with pytest.raises(ValueError, match="bulunamadı"):
        build_source_preview(source, path, "FFFFFFFF")

    focused = build_source_preview(source, path, focus_bbox=(8, -1, 11, 3))
    assert len(focused["strokes"]) == 1
    assert focused["strokes"][0]["role"] == "wall"
    assert focused["bounds"] == pytest.approx([9, 0, 10, 2])
    with pytest.raises(ValueError, match="odak alanı"):
        build_source_preview(source, path, focus_bbox=(11, 3, 8, -1))


def test_preview_api_reads_only_imported_project_source(tmp_path: Path) -> None:
    path = tmp_path / "plan.dxf"
    handle = _drawing(path)
    client = TestClient(create_app("test-token"))
    headers = {"x-metrajai-token": "test-token"}
    created = client.post(
        "/projects", json={"path": str(tmp_path / "project"), "name": "P"}, headers=headers
    ).json()
    project_id = created["project"]["project_id"]
    source = client.post(
        f"/projects/{project_id}/sources",
        json={
            "path": str(path),
            "discipline": "architectural",
            "role": "mimari",
            "drawing_unit": "mm",
        },
        headers=headers,
    ).json()

    response = client.get(
        f"/projects/{project_id}/sources/{source['id']}/preview",
        params={"region_id": handle},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["region_id"] == handle
    assert response.json()["bounds"] == pytest.approx([9, 0, 10, 2])
    focused = client.get(
        f"/projects/{project_id}/sources/{source['id']}/preview",
        params={"focus_bbox": "8,-1,11,3"},
        headers=headers,
    )
    assert focused.status_code == 200
    assert len(focused.json()["strokes"]) == 1
    assert (
        client.get(
            f"/projects/{project_id}/sources/{source['id']}/preview",
            params={"focus_bbox": "11,3,8,-1"},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/projects/{project_id}/sources/{source['id']}/preview",
            params={"region_id": "missing"},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/projects/{project_id}/sources/{source['id']}/preview",
            params={"region_id": handle, "stroke_offset": -1},
            headers=headers,
        ).status_code
        == 422
    )


def test_preview_can_load_large_drawing_in_distinct_pages(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "paged.dxf"
    document = ezdxf.new("R2018")
    document.header["$INSUNITS"] = 4
    for number in range(5):
        document.modelspace().add_line(
            (number * 1000, 0), (number * 1000, 1000), dxfattribs={"layer": f"L-{number}"}
        )
    document.saveas(path)
    source = SourceFile(
        project_id="test",
        original_name=path.name,
        stored_path=str(path),
        sha256="test",
        size_bytes=path.stat().st_size,
        source_format=SourceFormat.DXF,
        discipline=Discipline.ARCHITECTURAL,
        role="mimari",
        drawing_unit=DrawingUnit.MM,
        unit_confirmed=True,
    )
    monkeypatch.setattr(source_preview, "MAX_STROKES", 2)
    first = build_source_preview(source, path)
    second = build_source_preview(source, path, stroke_offset=first["next_offset"])
    third = build_source_preview(source, path, stroke_offset=second["next_offset"])
    assert [[stroke["layer"] for stroke in page["strokes"]] for page in (first, second, third)] == [
        ["L-0", "L-1"],
        ["L-2", "L-3"],
        ["L-4"],
    ]
    assert (first["next_offset"], second["next_offset"], third["next_offset"]) == (2, 4, None)
