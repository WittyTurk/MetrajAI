from __future__ import annotations

import platform
import shutil
import subprocess


class NativeDialogUnavailable(RuntimeError):
    """Raised when the host has no supported native file dialog."""


def _applescript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _run_macos(script: str) -> str | None:
    executable = shutil.which("osascript")
    if executable is None:
        raise NativeDialogUnavailable("macOS klasör seçicisi bulunamadı (osascript).")
    completed = subprocess.run(
        [executable, "-e", script],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode == 0:
        return completed.stdout.strip() or None
    if completed.returncode == 1:
        return None
    detail = completed.stderr.strip() or "macOS seçici açılamadı."
    raise NativeDialogUnavailable(detail)


def _run_windows(script: str) -> str | None:
    executable = shutil.which("powershell.exe") or shutil.which("powershell")
    if executable is None:
        raise NativeDialogUnavailable("Windows dosya seçicisi bulunamadı (PowerShell).")
    completed = subprocess.run(
        [executable, "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "Windows seçici açılamadı."
        raise NativeDialogUnavailable(detail)
    return completed.stdout.strip() or None


def _run_linux(arguments: list[str]) -> str | None:
    executable = shutil.which("zenity")
    if executable is None:
        raise NativeDialogUnavailable("Linux dosya seçicisi bulunamadı (zenity).")
    completed = subprocess.run(
        [executable, *arguments],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode == 0:
        return completed.stdout.strip() or None
    if completed.returncode == 1:
        return None
    detail = completed.stderr.strip() or "Linux seçici açılamadı."
    raise NativeDialogUnavailable(detail)


def select_directory(title: str) -> str | None:
    system = platform.system()
    if system == "Darwin":
        prompt = _applescript_string(title)
        return _run_macos(f'POSIX path of (choose folder with prompt "{prompt}")')
    if system == "Windows":
        escaped_title = title.replace("'", "''")
        return _run_windows(
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
            f"$dialog.Description = '{escaped_title}'; "
            "if ($dialog.ShowDialog() -eq 'OK') { $dialog.SelectedPath }"
        )
    if system == "Linux":
        return _run_linux(["--file-selection", "--directory", f"--title={title}"])
    raise NativeDialogUnavailable(f"Bu işletim sistemi desteklenmiyor: {system}")


def select_file(title: str) -> str | None:
    system = platform.system()
    if system == "Darwin":
        prompt = _applescript_string(title)
        return _run_macos(f'POSIX path of (choose file with prompt "{prompt}")')
    if system == "Windows":
        escaped_title = title.replace("'", "''")
        return _run_windows(
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$dialog = New-Object System.Windows.Forms.OpenFileDialog; "
            f"$dialog.Title = '{escaped_title}'; "
            "$dialog.Filter = "
            "'Proje kaynakları (*.dxf;*.xlsx;*.xls;*.pdf)|*.dxf;*.xlsx;*.xls;*.pdf'; "
            "if ($dialog.ShowDialog() -eq 'OK') { $dialog.FileName }"
        )
    if system == "Linux":
        return _run_linux(
            [
                "--file-selection",
                f"--title={title}",
                "--file-filter=Proje kaynakları | *.dxf *.xlsx *.xls",
            ]
        )
    raise NativeDialogUnavailable(f"Bu işletim sistemi desteklenmiyor: {system}")
