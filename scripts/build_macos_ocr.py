from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "macos_ocr.swift"
DESTINATION = ROOT / "desktop" / "src-tauri" / "resources" / "metrajai-ocr"


def main() -> None:
    if platform.system() != "Darwin":
        print("macOS Vision OCR yalnız macOS paketinde derlenir.")
        return
    xcrun = shutil.which("xcrun")
    if xcrun is None:
        raise SystemExit("Xcode Command Line Tools bulunamadı: xcrun eksik")
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            xcrun,
            "swiftc",
            "-O",
            "-framework",
            "AppKit",
            "-framework",
            "PDFKit",
            "-framework",
            "Vision",
            str(SOURCE),
            "-o",
            str(DESTINATION),
        ],
        check=True,
        cwd=ROOT,
    )
    DESTINATION.chmod(DESTINATION.stat().st_mode | 0o111)
    print(DESTINATION)


if __name__ == "__main__":
    main()
