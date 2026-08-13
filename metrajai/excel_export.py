from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .reporting import build_report_payload
from .workspace import ProjectWorkspace


class ExcelRuntimeUnavailable(RuntimeError):
    pass


def export_traceable_excel(
    workspace: ProjectWorkspace,
    output: str | Path | None = None,
) -> Path:
    """Export through artifact-tool in an isolated, disposable work directory."""
    node_binary = os.environ.get("METRAJAI_NODE_BINARY")
    node_modules = os.environ.get("METRAJAI_ARTIFACT_NODE_MODULES")
    if not node_binary or not node_modules:
        raise ExcelRuntimeUnavailable(
            "Excel runtime is not configured. METRAJAI_NODE_BINARY and "
            "METRAJAI_ARTIFACT_NODE_MODULES are required."
        )
    node_path = Path(node_binary).expanduser().resolve()
    modules_path = Path(node_modules).expanduser().resolve()
    if not node_path.is_file() or not (modules_path / "@oai" / "artifact-tool").exists():
        raise ExcelRuntimeUnavailable("Configured artifact-tool runtime is incomplete.")

    target = (
        Path(output).expanduser().resolve()
        if output
        else workspace.exports_dir / f"{workspace.manifest.name}_Metraj.xlsx"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="metrajai-report-") as temp_name:
        temp = Path(temp_name)
        payload_path = workspace.write_report_payload(
            build_report_payload(workspace), temp / "payload.json"
        )
        builder = temp / "build_report.mjs"
        shutil.copy2(Path(__file__).with_name("report_builder.mjs"), builder)
        (temp / "node_modules").symlink_to(modules_path, target_is_directory=True)
        process = subprocess.run(
            [str(node_path), str(builder), str(payload_path), str(target)],
            cwd=temp,
            check=False,
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or process.stdout.strip())
    return target
