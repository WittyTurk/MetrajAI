from __future__ import annotations

from pathlib import Path

import pytest

from metrajai.excel_export import ExcelRuntimeUnavailable, export_traceable_excel
from metrajai.workspace import ProjectWorkspace


def test_excel_export_fails_explicitly_without_private_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = ProjectWorkspace.create(tmp_path / "project", "Test")
    monkeypatch.delenv("METRAJAI_NODE_BINARY", raising=False)
    monkeypatch.delenv("METRAJAI_ARTIFACT_NODE_MODULES", raising=False)
    with pytest.raises(ExcelRuntimeUnavailable, match="not configured"):
        export_traceable_excel(workspace)
