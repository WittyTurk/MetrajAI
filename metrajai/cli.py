from __future__ import annotations

import argparse
import json
import socket
from decimal import Decimal

import uvicorn

from .api import create_app
from .commercial import (
    calculate_offer,
    import_price_catalog_file,
    suggest_price_mappings,
)
from .contracts import (
    AdjustmentBase,
    AdjustmentKind,
    Assumption,
    Discipline,
    DrawingUnit,
    FloorDefinition,
    FloorKind,
    MappingStatus,
    OfferAdjustment,
    OfferScenario,
    PriceMapping,
    ReliabilityState,
    RepeatAssignment,
    RepeatScope,
    ReviewDecision,
    ReviewStatus,
    SheetAssignment,
    SheetKind,
    ValidationGate,
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
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


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

    calibration = subparsers.add_parser("confirm-pdf-scale", help="Confirm two-point PDF scale")
    calibration.add_argument("project")
    calibration.add_argument("source_id")
    calibration.add_argument("scale", type=float)
    calibration.add_argument("x1", type=float)
    calibration.add_argument("y1", type=float)
    calibration.add_argument("x2", type=float)
    calibration.add_argument("y2", type=float)

    backup = subparsers.add_parser("backup", help="Create a project recovery point")
    backup.add_argument("project")
    backup.add_argument("--reason", default="manual")

    floors = subparsers.add_parser("floors", help="List project floors")
    floors.add_argument("project")
    add_floor = subparsers.add_parser("add-floor", help="Add or update a floor definition")
    add_floor.add_argument("project")
    add_floor.add_argument("name")
    add_floor.add_argument("--kind", choices=[item.value for item in FloorKind], required=True)
    add_floor.add_argument("--order", type=int, default=0)
    add_floor.add_argument("--elevation", type=float)
    add_floor.add_argument("--height", type=float)

    assign_sheet = subparsers.add_parser("assign-sheet", help="Assign a sheet role and floors")
    assign_sheet.add_argument("project")
    assign_sheet.add_argument("source_id")
    assign_sheet.add_argument("--kind", choices=[item.value for item in SheetKind], required=True)
    assign_sheet.add_argument("--floor-id", action="append", default=[])
    assign_sheet.add_argument("--role", default="")
    assign_sheet.add_argument("--revision", default="")
    assign_sheet.add_argument("--reviewer", required=True)
    assign_sheet.add_argument("--reason", required=True)

    repeats = subparsers.add_parser("repeats", help="List explicit repeat assignments")
    repeats.add_argument("project")
    add_repeat = subparsers.add_parser("add-repeat", help="Add an approved repeat assignment")
    add_repeat.add_argument("project")
    add_repeat.add_argument("source_id")
    add_repeat.add_argument("--scope", choices=[item.value for item in RepeatScope], required=True)
    add_repeat.add_argument("--floor-id", action="append", required=True)
    add_repeat.add_argument("--element-id", action="append", default=[])
    add_repeat.add_argument("--template", default="")
    add_repeat.add_argument("--reviewer", required=True)
    add_repeat.add_argument("--reason", required=True)

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
        "compare-revisions",
        help="Compare structural elements and openings between revisions",
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

    catalog = subparsers.add_parser("import-catalog", help="Import a versioned XLS/XLSX catalog")
    catalog.add_argument("project")
    catalog.add_argument("source")
    catalog.add_argument("--name", required=True)
    catalog.add_argument("--year", type=int, required=True)
    catalog.add_argument("--version", required=True)
    catalog.add_argument("--currency", default="TRY")
    catalog.add_argument("--official", action="store_true")
    catalog.add_argument("--source-url", default="")

    suggest = subparsers.add_parser("suggest-prices", help="Suggest quantity/price mappings")
    suggest.add_argument("project")
    suggest.add_argument("--minimum-confidence", type=float, default=0.55)

    approve_mapping = subparsers.add_parser("approve-price", help="Approve one price mapping")
    approve_mapping.add_argument("project")
    approve_mapping.add_argument("quantity_line_id")
    approve_mapping.add_argument("price_item_id")
    approve_mapping.add_argument("--reviewer", required=True)
    approve_mapping.add_argument("--reason", required=True)

    offer = subparsers.add_parser("create-offer", help="Create and calculate an offer scenario")
    offer.add_argument("project")
    offer.add_argument("--name", required=True)
    offer.add_argument("--currency", default="TRY")
    offer.add_argument("--exchange-rate", default="1")
    offer.add_argument("--exchange-rate-source", default="")
    offer.add_argument("--exchange-rate-date", default="")
    offer.add_argument(
        "--adjustment",
        action="append",
        default=[],
        metavar="LABEL:KIND:BASE:VALUE:APPLIES",
    )
    offer.add_argument("--reviewer", required=True)

    gate = subparsers.add_parser("set-gate", help="Set discipline reliability gate")
    gate.add_argument("project")
    gate.add_argument("discipline", choices=[item.value for item in Discipline])
    gate.add_argument("state", choices=[item.value for item in ReliabilityState])
    gate.add_argument("--small-approved", action="store_true")
    gate.add_argument("--complex-approved", action="store_true")
    gate.add_argument("--reviewer", required=True)
    gate.add_argument("--reason", required=True)

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
    elif args.command == "confirm-pdf-scale":
        _json(
            _workspace(args.project).confirm_source_calibration(
                args.source_id,
                scale=args.scale,
                points=[(args.x1, args.y1), (args.x2, args.y2)],
            )
        )
    elif args.command == "backup":
        _json(_workspace(args.project).create_backup(args.reason))
    elif args.command == "floors":
        _json([item.model_dump(mode="json") for item in _workspace(args.project).list_floors()])
    elif args.command == "add-floor":
        workspace = _workspace(args.project)
        _json(
            workspace.put_floor(
                FloorDefinition(
                    project_id=workspace.manifest.project_id,
                    name=args.name,
                    kind=FloorKind(args.kind),
                    order=args.order,
                    elevation_m=args.elevation,
                    height_m=args.height,
                )
            )
        )
    elif args.command == "assign-sheet":
        workspace = _workspace(args.project)
        _json(
            workspace.put_sheet_assignment(
                SheetAssignment(
                    project_id=workspace.manifest.project_id,
                    source_id=args.source_id,
                    sheet_kind=SheetKind(args.kind),
                    floor_ids=args.floor_id,
                    role=args.role,
                    revision=args.revision,
                    approved=True,
                    reviewer=args.reviewer,
                    reason=args.reason,
                )
            )
        )
    elif args.command == "repeats":
        _json(
            [
                item.model_dump(mode="json")
                for item in _workspace(args.project).list_repeat_assignments()
            ]
        )
    elif args.command == "add-repeat":
        workspace = _workspace(args.project)
        _json(
            workspace.put_repeat_assignment(
                RepeatAssignment(
                    project_id=workspace.manifest.project_id,
                    source_id=args.source_id,
                    scope=RepeatScope(args.scope),
                    target_floor_ids=args.floor_id,
                    element_ids=args.element_id,
                    template_label=args.template,
                    approved=True,
                    reviewer=args.reviewer,
                    reason=args.reason,
                )
            )
        )
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
    elif args.command == "import-catalog":
        workspace = _workspace(args.project)
        catalog, items = import_price_catalog_file(
            args.source,
            project_id=workspace.manifest.project_id,
            name=args.name,
            year=args.year,
            version=args.version,
            currency=args.currency,
            is_official=args.official,
            source_url=args.source_url,
        )
        catalog.stored_path = workspace.store_catalog_source(args.source, catalog.sha256)
        workspace.put_price_catalog(catalog, items)
        _json({"catalog": catalog.model_dump(mode="json"), "item_count": len(items)})
    elif args.command == "suggest-prices":
        workspace = _workspace(args.project)
        suggestions = suggest_price_mappings(
            workspace.manifest.project_id,
            workspace.list_quantities(),
            workspace.list_price_items(),
            minimum_confidence=args.minimum_confidence,
        )
        _json(
            [workspace.put_price_mapping(item).model_dump(mode="json") for item in suggestions]
        )
    elif args.command == "approve-price":
        workspace = _workspace(args.project)
        _json(
            workspace.put_price_mapping(
                PriceMapping(
                    project_id=workspace.manifest.project_id,
                    quantity_line_id=args.quantity_line_id,
                    price_item_id=args.price_item_id,
                    status=MappingStatus.APPROVED,
                    confidence=1,
                    reviewer=args.reviewer,
                    reason=args.reason,
                )
            )
        )
    elif args.command == "create-offer":
        workspace = _workspace(args.project)
        adjustments = []
        for order, value in enumerate(args.adjustment, start=1):
            parts = value.split(":")
            if len(parts) != 5:
                raise SystemExit("--adjustment must be LABEL:KIND:BASE:VALUE:APPLIES")
            label, kind, base, amount, applies = parts
            adjustments.append(
                OfferAdjustment(
                    label=label,
                    kind=AdjustmentKind(kind),
                    base=AdjustmentBase(base),
                    value=Decimal(amount),
                    order=order,
                    applicable=applies.casefold() in {"1", "true", "yes", "evet"},
                    source="CLI kullanıcı kararı",
                )
            )
        scenario = workspace.put_offer_scenario(
            OfferScenario(
                project_id=workspace.manifest.project_id,
                name=args.name,
                currency=args.currency.upper(),
                exchange_rate=Decimal(args.exchange_rate),
                exchange_rate_source=args.exchange_rate_source,
                exchange_rate_date=args.exchange_rate_date,
                adjustments=adjustments,
                approved=True,
                reviewer=args.reviewer,
            )
        )
        lines, totals = calculate_offer(
            scenario,
            workspace.list_quantities(),
            workspace.list_price_mappings(),
            workspace.list_price_items(),
        )
        workspace.replace_cost_lines(scenario.id, lines)
        _json({"scenario": scenario.model_dump(mode="json"), "totals": totals})
    elif args.command == "set-gate":
        workspace = _workspace(args.project)
        _json(
            workspace.put_validation_gate(
                ValidationGate(
                    project_id=workspace.manifest.project_id,
                    discipline=Discipline(args.discipline),
                    state=ReliabilityState(args.state),
                    small_project_approved=args.small_approved,
                    complex_project_approved=args.complex_approved,
                    reviewer=args.reviewer,
                    reason=args.reason,
                )
            )
        )
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
