from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINARIES = ROOT / "desktop" / "src-tauri" / "binaries"
PILOT_SOURCES = (
    ROOT / "INPUT/statik/TAZIYE-EVLERI_STATIK.dxf",
    ROOT / "INPUT/SU.01 KALIP VE DONATI (DEFTERDARLIK).dxf",
    ROOT / "INPUT/SU.02 KOLON APLİKASYON (DEFTERDARLIK).dxf",
    ROOT / "INPUT2/statik/sutculer_32.dxf",
)


def rust_target() -> str:
    if shutil.which("rustc"):
        result = subprocess.run(["rustc", "-vV"], check=True, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if line.startswith("host: "):
                return line.removeprefix("host: ").strip()
    machine = platform.machine().lower()
    system = platform.system()
    known = {
        ("Darwin", "arm64"): "aarch64-apple-darwin",
        ("Darwin", "aarch64"): "aarch64-apple-darwin",
        ("Darwin", "x86_64"): "x86_64-apple-darwin",
        ("Windows", "amd64"): "x86_64-pc-windows-msvc",
        ("Windows", "x86_64"): "x86_64-pc-windows-msvc",
        ("Linux", "x86_64"): "x86_64-unknown-linux-gnu",
        ("Linux", "aarch64"): "aarch64-unknown-linux-gnu",
    }
    try:
        return known[(system, machine)]
    except KeyError as exc:
        raise RuntimeError(
            "Cannot infer a Tauri target triple; install rustc for this platform."
        ) from exc


def main() -> None:
    if all(path.is_file() for path in PILOT_SOURCES):
        print("Yerel Taziye/Defterdarlık/Sütçüler pilot doğrulaması çalıştırılıyor…")
        subprocess.run(
            [sys.executable, "-m", "scripts.validate_pilot_projects"],
            cwd=ROOT,
            check=True,
        )
    else:
        print("Private pilot DXF files not found; local pilot validation skipped.")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--log-level",
            "WARN",
            "--onefile",
            "--name",
            "metrajai-engine",
            "--collect-all",
            "ezdxf",
            "--collect-all",
            "openpyxl",
            "--collect-all",
            "pdfplumber",
            "--collect-all",
            "xlrd",
            "--collect-data",
            "metrajai",
            "--hidden-import",
            "uvicorn.logging",
            "--hidden-import",
            "uvicorn.loops.auto",
            "--hidden-import",
            "uvicorn.protocols.http.auto",
            "--hidden-import",
            "uvicorn.protocols.websockets.auto",
            str(ROOT / "metrajai_sidecar.py"),
        ],
        cwd=ROOT,
        check=True,
    )
    suffix = ".exe" if platform.system() == "Windows" else ""
    source = ROOT / "dist" / f"metrajai-engine{suffix}"
    BINARIES.mkdir(parents=True, exist_ok=True)
    destination = BINARIES / f"metrajai-engine-{rust_target()}{suffix}"
    shutil.copy2(source, destination)
    subprocess.run(
        [str(destination), "--help"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    print(destination)


if __name__ == "__main__":
    main()
