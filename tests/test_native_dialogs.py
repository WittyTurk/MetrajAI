from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from metrajai import native_dialogs
from metrajai.api import create_app


def test_macos_directory_picker_returns_posix_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native_dialogs.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(native_dialogs.shutil, "which", lambda _name: "/usr/bin/osascript")

    def fake_run(*_args, **_kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, "/Users/example/Pilot/\n", "")

    monkeypatch.setattr(native_dialogs.subprocess, "run", fake_run)
    assert native_dialogs.select_directory("Pilot klasörünü seçin") == "/Users/example/Pilot/"


def test_macos_picker_cancellation_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native_dialogs.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(native_dialogs.shutil, "which", lambda _name: "/usr/bin/osascript")
    monkeypatch.setattr(
        native_dialogs.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "User canceled."),
    )
    assert native_dialogs.select_file("Kaynak seçin") is None


def test_windows_picker_accepts_pdf_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native_dialogs.platform, "system", lambda: "Windows")
    monkeypatch.setattr(native_dialogs.shutil, "which", lambda _name: "powershell.exe")
    captured: list[str] = []

    def fake_run(arguments: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        captured.extend(arguments)
        return subprocess.CompletedProcess(arguments, 0, "C:\\Pilot\\kesit.pdf\n", "")

    monkeypatch.setattr(native_dialogs.subprocess, "run", fake_run)
    assert native_dialogs.select_file("Kaynak seçin") == "C:\\Pilot\\kesit.pdf"
    assert "*.pdf" in captured[-1]


def test_native_dialog_api_is_session_protected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("metrajai.api.select_directory", lambda _title: "/tmp/pilot")
    client = TestClient(create_app("dialog-token"))

    assert client.post("/system/select-directory", json={"title": "Klasör seç"}).status_code == 401
    response = client.post(
        "/system/select-directory",
        json={"title": "Klasör seç"},
        headers={"x-metrajai-token": "dialog-token"},
    )
    assert response.status_code == 200
    assert response.json() == {"path": "/tmp/pilot"}
