from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_bundle_is_offline_and_excludes_macos_ocr() -> None:
    config = json.loads(
        (ROOT / "desktop/src-tauri/tauri.windows.conf.json").read_text("utf-8")
    )
    bundle = config["bundle"]
    assert bundle["targets"] == ["nsis"]
    assert bundle["windows"]["webviewInstallMode"]["type"] == "offlineInstaller"
    assert "resources/metrajai-ocr" not in bundle["resources"]
    assert "resources/report-runtime/**/*" in bundle["resources"]
