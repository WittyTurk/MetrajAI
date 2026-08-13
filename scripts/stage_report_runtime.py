from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "desktop" / "src-tauri" / "resources" / "report-runtime"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage the private artifact-tool runtime for a desktop package"
    )
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--node-modules", type=Path, required=True)
    args = parser.parse_args()

    node = args.node.expanduser().resolve()
    modules = args.node_modules.expanduser().resolve()
    artifact_tool = modules / "@oai" / "artifact-tool"
    if not node.is_file():
        raise SystemExit(f"Node executable not found: {node}")
    if not (artifact_tool / "package.json").is_file():
        raise SystemExit(f"artifact-tool not found: {artifact_tool}")

    TARGET.mkdir(parents=True, exist_ok=True)
    node_target = TARGET / ("node.exe" if node.suffix.lower() == ".exe" else "node")
    shutil.copy2(node, node_target)
    package_target = TARGET / "node_modules" / "@oai" / "artifact-tool"
    if package_target.exists():
        shutil.rmtree(package_target)
    package_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(artifact_tool, package_target, symlinks=True)
    node_target.chmod(node_target.stat().st_mode | 0o111)
    print(TARGET)


if __name__ == "__main__":
    main()
