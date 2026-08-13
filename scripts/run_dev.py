from __future__ import annotations

import argparse
import os
import secrets
import shutil
import socket
import subprocess
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
CODEX_NODE_ROOT = (
    Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node"
)


def port_is_available(port: int) -> bool:
    with socket.socket() as handle:
        try:
            handle.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def available_port() -> int:
    with socket.socket() as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


def wait_for_url(url: str, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status < 500:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(0.15)
    raise RuntimeError(f"Servis hazır olmadı: {url} ({last_error})")


def terminate(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="MetrajAI yerel geliştirme sürümünü başlat")
    parser.add_argument("--no-browser", action="store_true", help="Tarayıcıyı otomatik açma")
    args = parser.parse_args()

    if not VENV_PYTHON.is_file():
        raise SystemExit(
            "Sanal ortam bulunamadı. Önce: python3 -m venv .venv && "
            ".venv/bin/python -m pip install -e '.[dev]'"
        )
    if not (DESKTOP / "node_modules").is_dir():
        raise SystemExit("Ön yüz bağımlılıkları eksik. Önce: npm --prefix desktop install")
    if not port_is_available(1420):
        raise SystemExit(
            "1420 portu kullanımda. Açık MetrajAI/Vite işlemini kapatıp tekrar deneyin."
        )

    engine_port = available_port()
    token = secrets.token_urlsafe(32)
    engine_env = os.environ.copy()
    artifact_tool = CODEX_NODE_ROOT / "node_modules" / "@oai" / "artifact-tool"
    if CODEX_NODE_ROOT.joinpath("bin", "node").is_file() and artifact_tool.is_dir():
        engine_env.setdefault("METRAJAI_NODE_BINARY", str(CODEX_NODE_ROOT / "bin" / "node"))
        engine_env.setdefault(
            "METRAJAI_ARTIFACT_NODE_MODULES", str(CODEX_NODE_ROOT / "node_modules")
        )

    engine = subprocess.Popen(
        [
            str(VENV_PYTHON),
            "-m",
            "metrajai",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(engine_port),
            "--token",
            token,
        ],
        cwd=ROOT,
        env=engine_env,
    )
    frontend: subprocess.Popen | None = None
    try:
        wait_for_url(f"http://127.0.0.1:{engine_port}/health")
        frontend_env = os.environ.copy()
        frontend_env["VITE_ENGINE_URL"] = f"http://127.0.0.1:{engine_port}"
        frontend_env["VITE_ENGINE_TOKEN"] = token
        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError("npm bulunamadı")
        frontend = subprocess.Popen(
            [npm, "--prefix", str(DESKTOP), "run", "dev"],
            cwd=ROOT,
            env=frontend_env,
        )
        wait_for_url("http://127.0.0.1:1420/")
        print("\nMetrajAI hazır: http://127.0.0.1:1420/", flush=True)
        print("Kapatmak için bu terminalde Ctrl+C kullanın.\n", flush=True)
        if not args.no_browser:
            webbrowser.open("http://127.0.0.1:1420/")
        while frontend.poll() is None and engine.poll() is None:
            time.sleep(0.5)
        if frontend.poll() not in (None, 0):
            raise RuntimeError(f"Ön yüz beklenmedik biçimde kapandı: {frontend.returncode}")
        if engine.poll() not in (None, 0):
            raise RuntimeError(f"Hesap motoru beklenmedik biçimde kapandı: {engine.returncode}")
    except KeyboardInterrupt:
        print("\nMetrajAI kapatılıyor…", flush=True)
    finally:
        if frontend is not None:
            terminate(frontend)
        terminate(engine)


if __name__ == "__main__":
    main()
