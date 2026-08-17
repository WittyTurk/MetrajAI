from __future__ import annotations

import time
from pathlib import Path

import ezdxf
from fastapi.testclient import TestClient

from metrajai.api import create_app
from metrajai.contracts import DetectedElement, Discipline, Geometry, ReviewStatus

TOKEN = "test-session-token"
HEADERS = {"x-metrajai-token": TOKEN}


def test_project_start_returns_actionable_errors_for_existing_or_missing_workspace(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(TOKEN))
    project = tmp_path / "project"

    created = client.post(
        "/projects",
        json={"path": str(project), "name": "P"},
        headers=HEADERS,
    )
    duplicate = client.post(
        "/projects",
        json={"path": str(project), "name": "P"},
        headers=HEADERS,
    )
    missing = client.post(
        "/projects/open",
        json={"path": str(tmp_path / "missing")},
        headers=HEADERS,
    )

    assert created.status_code == 200
    assert duplicate.status_code == 409
    assert "Projeyi aç" in duplicate.json()["detail"]
    assert missing.status_code == 404
    assert "projesi bulunamadı" in missing.json()["detail"]


def test_source_discipline_can_be_corrected_without_reimport(tmp_path: Path) -> None:
    drawing = tmp_path / "architectural.dxf"
    ezdxf.new("R2018").saveas(drawing)
    client = TestClient(create_app(TOKEN))
    created = client.post(
        "/projects",
        json={"path": str(tmp_path / "project"), "name": "P"},
        headers=HEADERS,
    )
    project_id = created.json()["project"]["project_id"]
    imported = client.post(
        f"/projects/{project_id}/sources",
        json={"path": str(drawing), "discipline": "structural", "role": "kalip"},
        headers=HEADERS,
    ).json()

    response = client.patch(
        f"/projects/{project_id}/sources/{imported['id']}/discipline",
        json={"discipline": "architectural"},
        headers=HEADERS,
    )

    assert response.status_code == 200, response.text
    assert response.json()["source"]["discipline"] == "architectural"
    sources = client.get(f"/projects/{project_id}/sources", headers=HEADERS).json()
    assert sources[0]["discipline"] == "architectural"


def test_local_api_requires_token_and_runs_reviewed_quantity_flow(tmp_path: Path) -> None:
    drawing = tmp_path / "column.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_lwpolyline(
        [(0, 0), (400, 0), (400, 600), (0, 600)],
        close=True,
        dxfattribs={"layer": "S-KOLON"},
    )
    doc.saveas(drawing)
    client = TestClient(create_app(TOKEN))

    assert client.get("/health").status_code == 200
    preflight = client.options(
        "/projects/open",
        headers={
            "origin": "http://127.0.0.1:1420",
            "access-control-request-method": "POST",
            "access-control-request-headers": "content-type,x-metrajai-token",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://127.0.0.1:1420"
    unauthorized = client.post("/projects", json={"path": str(tmp_path / "p"), "name": "P"})
    assert unauthorized.status_code == 401
    created = client.post(
        "/projects", json={"path": str(tmp_path / "p"), "name": "P"}, headers=HEADERS
    )
    assert created.status_code == 200
    project_id = created.json()["project"]["project_id"]
    imported = client.post(
        f"/projects/{project_id}/sources",
        json={"path": str(drawing), "discipline": "structural", "role": "kalip"},
        headers=HEADERS,
    )
    assert imported.status_code == 200

    started = client.post(f"/projects/{project_id}/analyses", json={}, headers=HEADERS).json()
    for _ in range(200):
        run = client.get(f"/analyses/{started['id']}", headers=HEADERS).json()
        if run["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.01)
    assert run["status"] == "completed", run

    elements = client.get(f"/projects/{project_id}/elements", headers=HEADERS).json()
    column = next(item for item in elements if item["element_type"] == "column")
    assert client.get(f"/projects/{project_id}/quantities", headers=HEADERS).json() == []
    reviewed = client.patch(
        f"/projects/{project_id}/elements/{column['id']}/review",
        json={
            "status": "accepted",
            "reviewer": "Engineer",
            "reason": "Kesit doğrulandı",
            "measurement_overrides": {"height_m": 3.0},
        },
        headers=HEADERS,
    )
    assert reviewed.status_code == 200, reviewed.text
    quantities = client.get(f"/projects/{project_id}/quantities", headers=HEADERS).json()
    assert {item["description"] for item in quantities} == {
        "Kolon betonu",
        "Kolon yan kalıbı (brüt; birleşimler düşülmemiş)",
    }

    deleted = client.delete(
        f"/projects/{project_id}/sources/{imported.json()['id']}", headers=HEADERS
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted_element_count"] == 1
    assert deleted.json()["project"]["source_count"] == 0
    assert client.get(f"/projects/{project_id}/sources", headers=HEADERS).json() == []
    assert client.get(f"/projects/{project_id}/elements", headers=HEADERS).json() == []
    assert client.get(f"/projects/{project_id}/quantities", headers=HEADERS).json() == []
    assert (
        client.delete(
            f"/projects/{project_id}/sources/{imported.json()['id']}", headers=HEADERS
        ).status_code
        == 404
    )


def test_bulk_review_accepts_complete_elements_and_skips_blocked_ones(
    tmp_path: Path,
) -> None:
    drawing = tmp_path / "bulk.dxf"
    ezdxf.new("R2018").saveas(drawing)
    app = create_app(TOKEN)
    client = TestClient(app)
    project_id = client.post(
        "/projects",
        json={"path": str(tmp_path / "bulk-project"), "name": "Bulk"},
        headers=HEADERS,
    ).json()["project"]["project_id"]
    source = client.post(
        f"/projects/{project_id}/sources",
        json={"path": str(drawing), "discipline": "structural", "role": "kalip"},
        headers=HEADERS,
    ).json()
    safe = DetectedElement(
        id="bulk_safe",
        source_id=source["id"],
        discipline=Discipline.STRUCTURAL,
        element_type="column",
        geometry=Geometry(kind="lwpolyline"),
        measurements={"width_m": 0.4, "depth_m": 0.6, "height_m": 3.0},
        required_inputs=["width_m", "depth_m", "height_m"],
        review_status=ReviewStatus.PENDING,
    )
    blocked = safe.model_copy(
        update={
            "id": "bulk_blocked",
            "issues": ["blocking:rebar_revision_selection_required"],
            "review_status": ReviewStatus.NEEDS_REVIEW,
        }
    )
    app.state.registry.get(project_id).replace_source_elements(source["id"], [safe, blocked])

    response = client.patch(
        f"/projects/{project_id}/elements/review-bulk",
        json={
            "element_ids": [safe.id, blocked.id],
            "status": "accepted",
            "reviewer": "Engineer",
            "reason": "Tip bazında çizim ve ölçüler kontrol edildi",
        },
        headers=HEADERS,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reviewed_element_ids"] == [safe.id]
    assert blocked.id in body["skipped"]
    elements = {
        item["id"]: item
        for item in client.get(f"/projects/{project_id}/elements", headers=HEADERS).json()
    }
    assert elements[safe.id]["review_status"] == "accepted"
    assert elements[blocked.id]["review_status"] == "needs_review"
    assert len(client.get(f"/projects/{project_id}/quantities", headers=HEADERS).json()) == 2


def test_source_mapping_and_revision_comparison_are_available_through_api(
    tmp_path: Path,
) -> None:
    old_path = tmp_path / "plan-r00.dxf"
    new_path = tmp_path / "plan-r01.dxf"
    ezdxf.new("R2018").saveas(old_path)
    ezdxf.new("R2018").saveas(new_path)
    app = create_app(TOKEN)
    client = TestClient(app)
    project_id = client.post(
        "/projects",
        json={"path": str(tmp_path / "revision-project"), "name": "Revision"},
        headers=HEADERS,
    ).json()["project"]["project_id"]

    source_ids: list[str] = []
    for path, revision in ((old_path, "R00"), (new_path, "R01")):
        imported = client.post(
            f"/projects/{project_id}/sources",
            json={
                "path": str(path),
                "discipline": "structural",
                "role": "kalip",
                "floor": "1. KAT",
                "floor_kind": "typical",
                "sheet_kind": "plan",
                "revision": revision,
            },
            headers=HEADERS,
        ).json()
        source_ids.append(imported["id"])

    mapping = client.patch(
        f"/projects/{project_id}/sources/{source_ids[0]}/mapping",
        json={
            "role": "kalip plani",
            "floor": "1. KAT",
            "floor_kind": "typical",
            "sheet_kind": "plan",
            "repeat_floors": ["2. KAT", "3. KAT"],
            "revision": "R00",
        },
        headers=HEADERS,
    )
    assert mapping.status_code == 200, mapping.text
    assert mapping.json()["source"]["repeat_floors"] == ["2. KAT", "3. KAT"]

    workspace = app.state.registry.get(project_id)
    for source_id, x_position in zip(source_ids, (0.0, 100.0), strict=True):
        workspace.replace_source_elements(
            source_id,
            [
                DetectedElement(
                    id=f"elm_{source_id}",
                    source_id=source_id,
                    discipline=Discipline.STRUCTURAL,
                    element_type="column",
                    floor="1. KAT",
                    geometry=Geometry(
                        kind="closed_outline",
                        bbox=(x_position, 0, x_position + 0.4, 0.6),
                    ),
                    measurements={"width_m": 0.4, "depth_m": 0.6, "height_m": 3.0},
                    properties={"element_label": "K01"},
                )
            ],
        )

    compared = client.post(
        f"/projects/{project_id}/revision-comparisons",
        json={"old_source_id": source_ids[0], "new_source_id": source_ids[1]},
        headers=HEADERS,
    )
    assert compared.status_code == 200, compared.text
    assert compared.json()["summary"] == {
        "added": 0,
        "deleted": 0,
        "modified": 0,
        "unchanged": 1,
    }
