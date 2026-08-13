from __future__ import annotations

import argparse
import json
import socket

import uvicorn

from .api import create_app
from .contracts import (
    Assumption,
    Discipline,
    DrawingUnit,
    FloorKind,
    ReviewDecision,
    ReviewStatus,
    SheetKind,
)
from .excel_export import export_traceable_excel
from .logging_config import configure_logging
from .reporting import build_report_payload
from .revision_compare import compare_revisions
from .service import EngineService
from .workspace import ProjectWorkspace


def _json(value) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _workspace(path: str) -> ProjectWorkspace:
    workspace = ProjectWorkspace(path)
    configure_logging(workspace.logs_dir)
    return workspace


def _available_port(host: str) -> int:
    with socket.socket() as handle:
        handle.bind((host, 0))
        return int(handle.getsockname()[1])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="metrajai", description="MetrajAI local engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create a portable project workspace")
    init.add_argument("path")
    init.add_argument("--name", required=True)

    add = subparsers.add_parser("import-source", help="Copy an immutable source into a project")
    add.add_argument("project")
    add.add_argument("source")
    add.add_argument("--discipline", choices=[item.value for item in Discipline], required=True)
    add.add_argument("--role", required=True)
    add.add_argument("--floor", default="GENEL")
    add.add_argument("--floor-kind", choices=[item.value for item in FloorKind])
    add.add_argument("--sheet-kind", choices=[item.value for item in SheetKind])
    add.add_argument("--repeat-floor", action="append", default=[])
    add.add_argument("--revision", default="")
    add.add_argument("--unit", choices=[item.value for item in DrawingUnit], default="unknown")

    unit = subparsers.add_parser("confirm-unit", help="Confirm a DXF drawing unit")
    unit.add_argument("project")
    unit.add_argument("source_id")
    unit.add_argument("unit", choices=["mm", "cm", "m"])

    analyze = subparsers.add_parser("analyze", help="Run deterministic analysis")
    analyze.add_argument("project")
    analyze.add_argument("--source-id", action="append", dest="source_ids")

    elements = subparsers.add_parser("elements", help="List detected elements")
    elements.add_argument("project")
    elements.add_argument("--status", choices=[item.value for item in ReviewStatus])

    review = subparsers.add_parser("review", help="Record an engineer review decision")
    review.add_argument("project")
    review.add_argument("element_id")
    review.add_argument("status", choices=[item.value for item in ReviewStatus])
    review.add_argument("--reviewer", default="User")
    review.add_argument("--reason", default="")
    review.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")

    quantities = subparsers.add_parser("quantities", help="List approved quantities")
    quantities.add_argument("project")

    compare = subparsers.add_parser(
        "compare-revisions", help="Compare detected columns, beams and slabs between sources"
    )
    compare.add_argument("project")
    compare.add_argument("old_source_id")
    compare.add_argument("new_source_id")

    assumption = subparsers.add_parser("set-assumption", help="Add a versioned assumption")
    assumption.add_argument("project")
    assumption.add_argument("key")
    assumption.add_argument("value")
    assumption.add_argument("--unit", default="")
    assumption.add_argument("--description", default="")
    assumption.add_argument("--version", type=int, default=1)
    assumption.add_argument("--approved", action="store_true")

    payload = subparsers.add_parser("report-payload", help="Write traceable report JSON")
    payload.add_argument("project")
    payload.add_argument("--output")

    report = subparsers.add_parser("export-report", help="Create a traceable Excel report")
    report.add_argument("project")
    report.add_argument("--output")

    serve = subparsers.add_parser("serve", help="Run loopback-only local API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=0)
    serve.add_argument("--token", required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        _json(ProjectWorkspace.create(args.path, args.name).summary())
    elif args.command == "import-source":
        workspace = _workspace(args.project)
        _json(
            workspace.add_source(
                args.source,
                discipline=Discipline(args.discipline),
                role=args.role,
                floor=args.floor,
                floor_kind=FloorKind(args.floor_kind) if args.floor_kind else None,
                sheet_kind=SheetKind(args.sheet_kind) if args.sheet_kind else None,
                repeat_floors=args.repeat_floor,
                revision=args.revision,
                drawing_unit=DrawingUnit(args.unit),
            )
        )
    elif args.command == "confirm-unit":
        _json(_workspace(args.project).confirm_source_unit(args.source_id, DrawingUnit(args.unit)))
    elif args.command == "analyze":
        _json(EngineService(_workspace(args.project)).analyze(args.source_ids))
    elif args.command == "elements":
        status = ReviewStatus(args.status) if args.status else None
        _json(
            [
                item.model_dump(mode="json")
                for item in _workspace(args.project).list_elements(status=status)
            ]
        )
    elif args.command == "review":
        overrides: dict[str, float] = {}
        for assignment in args.set:
            key, separator, value = assignment.partition("=")
            if not separator or not key:
                raise SystemExit(f"Invalid --set value: {assignment}; expected KEY=VALUE")
            overrides[key] = float(value)
        decision = ReviewDecision(
            element_id=args.element_id,
            status=ReviewStatus(args.status),
            reviewer=args.reviewer,
            reason=args.reason,
            measurement_overrides=overrides,
        )
        _json(EngineService(_workspace(args.project)).review(decision))
    elif args.command == "quantities":
        _json([item.model_dump(mode="json") for item in _workspace(args.project).list_quantities()])
    elif args.command == "compare-revisions":
        workspace = _workspace(args.project)
        _json(
            compare_revisions(
                workspace.get_source(args.old_source_id),
                workspace.get_source(args.new_source_id),
                workspace.list_elements(),
            )
        )
    elif args.command == "set-assumption":
        workspace = _workspace(args.project)
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value
        item = workspace.put_assumption(
            Assumption(
                key=args.key,
                value=value,
                unit=args.unit,
                description=args.description,
                version=args.version,
                approved=args.approved,
            )
        )
        EngineService(workspace).refresh_quantities()
        _json(item)
    elif args.command == "report-payload":
        workspace = _workspace(args.project)
        path = workspace.write_report_payload(build_report_payload(workspace), args.output)
        _json({"path": str(path)})
    elif args.command == "export-report":
        path = export_traceable_excel(_workspace(args.project), args.output)
        _json({"path": str(path)})
    elif args.command == "serve":
        if args.host != "127.0.0.1":
            raise SystemExit("MetrajAI API may only bind to 127.0.0.1")
        port = args.port or _available_port(args.host)
        print(
            json.dumps(
                {"event": "ready", "host": args.host, "port": port},
                ensure_ascii=False,
            ),
            flush=True,
        )
        uvicorn.run(create_app(args.token), host=args.host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
