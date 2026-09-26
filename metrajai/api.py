from __future__ import annotations

import hmac
from decimal import Decimal
from secrets import token_urlsafe

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .analyzers.architectural_plan import (
    apply_architectural_assignments,
    reconcile_architectural_elements,
)
from .commercial import (
    CatalogImportError,
    calculate_offer,
    import_price_catalog_file,
    suggest_price_mappings,
)
from .contracts import (
    AdjustmentBase,
    AdjustmentKind,
    ArchitecturalAssignment,
    ArchitecturalAssignmentKind,
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
from .excel_export import ExcelRuntimeUnavailable, export_traceable_excel
from .logging_config import configure_logging
from .native_dialogs import NativeDialogUnavailable, select_directory, select_file
from .reporting import build_report_payload
from .revision_compare import compare_revisions
from .service import BackgroundAnalysisManager, EngineService
from .workspace import ProjectWorkspace


class ProjectCreateRequest(BaseModel):
    path: str
    name: str


class ProjectOpenRequest(BaseModel):
    path: str


class SourceImportRequest(BaseModel):
    path: str
    discipline: Discipline
    role: str
    floor: str = "GENEL"
    floor_kind: FloorKind | None = None
    sheet_kind: SheetKind | None = None
    repeat_floors: list[str] = Field(default_factory=list, max_length=100)
    revision: str = ""
    drawing_unit: DrawingUnit = DrawingUnit.UNKNOWN


class UnitConfirmationRequest(BaseModel):
    unit: DrawingUnit


class CalibrationRequest(BaseModel):
    scale: float = Field(gt=0)
    points: list[tuple[float, float]] = Field(min_length=2, max_length=2)


class SourceDisciplineRequest(BaseModel):
    discipline: Discipline


class SourceMappingRequest(BaseModel):
    role: str = Field(min_length=1, max_length=100)
    floor: str = Field(min_length=1, max_length=100)
    floor_kind: FloorKind
    sheet_kind: SheetKind
    repeat_floors: list[str] = Field(default_factory=list, max_length=100)
    revision: str = Field(default="", max_length=100)


class AnalysisRequest(BaseModel):
    source_ids: list[str] | None = None


class ReviewRequest(BaseModel):
    status: ReviewStatus
    reviewer: str = "User"
    reason: str = ""
    measurement_overrides: dict[str, float] = Field(default_factory=dict)


class BulkReviewRequest(BaseModel):
    element_ids: list[str] = Field(min_length=1, max_length=500)
    status: ReviewStatus
    reviewer: str = "Mühendis"
    reason: str = Field(min_length=3, max_length=500)


class RebarRevisionRequest(BaseModel):
    source_id: str
    table_handle: str


class RevisionComparisonRequest(BaseModel):
    old_source_id: str
    new_source_id: str


class AssumptionRequest(BaseModel):
    key: str
    value: float | str | bool
    unit: str = ""
    description: str = ""
    version: int = 1
    approved: bool = False


class NativeDialogRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class FloorRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: FloorKind
    order: int = 0
    elevation_m: float | None = None
    height_m: float | None = Field(default=None, gt=0)


class SheetAssignmentRequest(BaseModel):
    sheet_kind: SheetKind
    floor_ids: list[str] = Field(default_factory=list, max_length=100)
    role: str = Field(default="", max_length=100)
    revision: str = Field(default="", max_length=100)
    approved: bool = False
    reviewer: str = Field(default="", max_length=100)
    reason: str = Field(default="", max_length=500)


class RepeatAssignmentRequest(BaseModel):
    source_id: str
    scope: RepeatScope
    target_floor_ids: list[str] = Field(min_length=1, max_length=100)
    element_ids: list[str] = Field(default_factory=list, max_length=500)
    template_label: str = Field(default="", max_length=100)
    approved: bool = False
    reviewer: str = Field(default="", max_length=100)
    reason: str = Field(default="", max_length=500)


class ArchitecturalAssignmentRequest(BaseModel):
    source_id: str
    subject_element_id: str
    kind: ArchitecturalAssignmentKind
    target_element_ids: list[str] = Field(default_factory=list, max_length=20)
    values: dict[str, str | float | bool] = Field(default_factory=dict)
    approved: bool = False
    reviewer: str = Field(default="", max_length=100)
    reason: str = Field(default="", max_length=500)


class PriceCatalogImportRequest(BaseModel):
    path: str
    name: str = Field(min_length=1, max_length=160)
    year: int = Field(ge=2000, le=2200)
    version: str = Field(min_length=1, max_length=60)
    currency: str = Field(default="TRY", min_length=3, max_length=3)
    is_official: bool = False
    source_url: str = Field(default="", max_length=500)


class PriceMappingRequest(BaseModel):
    quantity_line_id: str
    price_item_id: str
    status: MappingStatus
    confidence: float = Field(default=1.0, ge=0, le=1)
    reviewer: str = Field(default="", max_length=100)
    reason: str = Field(default="", max_length=500)


class PriceSuggestionRequest(BaseModel):
    catalog_ids: list[str] = Field(default_factory=list, max_length=50)
    minimum_confidence: float = Field(default=0.55, ge=0, le=1)


class OfferAdjustmentRequest(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    kind: AdjustmentKind
    base: AdjustmentBase = AdjustmentBase.RUNNING_TOTAL
    value: Decimal
    order: int
    applicable: bool | None = None
    source: str = Field(default="", max_length=500)
    source_date: str = Field(default="", max_length=30)


class OfferScenarioRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    currency: str = Field(default="TRY", min_length=3, max_length=3)
    exchange_rate: Decimal = Decimal("1")
    exchange_rate_source: str = Field(default="", max_length=500)
    exchange_rate_date: str = Field(default="", max_length=30)
    adjustments: list[OfferAdjustmentRequest] = Field(default_factory=list, max_length=100)
    approved: bool = False
    reviewer: str = Field(default="", max_length=100)


class ValidationGateRequest(BaseModel):
    discipline: Discipline
    state: ReliabilityState
    small_project_approved: bool = False
    complex_project_approved: bool = False
    reviewer: str = Field(default="", max_length=100)
    reason: str = Field(default="", max_length=500)


class ProjectRegistry:
    def __init__(self):
        self._projects: dict[str, ProjectWorkspace] = {}

    def add(self, workspace: ProjectWorkspace) -> ProjectWorkspace:
        self._projects[workspace.manifest.project_id] = workspace
        return workspace

    def get(self, project_id: str) -> ProjectWorkspace:
        try:
            return self._projects[project_id]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Project is not open") from exc


def create_app(session_token: str | None = None) -> FastAPI:
    token = session_token or token_urlsafe(32)
    app = FastAPI(title="MetrajAI Local Engine", version="1.3.5")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "tauri://localhost",
            "http://tauri.localhost",
            "http://localhost:1420",
            "http://127.0.0.1:1420",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["content-type", "x-metrajai-token"],
    )
    registry = ProjectRegistry()
    jobs = BackgroundAnalysisManager()
    app.state.session_token = token
    app.state.registry = registry
    app.state.jobs = jobs

    @app.middleware("http")
    async def require_session_key(request: Request, call_next):
        if request.url.path != "/health" and request.method != "OPTIONS":
            supplied = request.headers.get("x-metrajai-token", "")
            if not supplied or not hmac.compare_digest(supplied, token):
                from fastapi.responses import JSONResponse

                return JSONResponse(status_code=401, content={"detail": "Invalid session token"})
            parts = request.url.path.strip("/").split("/")
            if (
                request.method not in {"GET", "HEAD"}
                and len(parts) >= 3
                and parts[0] == "projects"
                and jobs.project_is_busy(parts[1])
            ):
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=409,
                    content={"detail": "Çalışan analiz tamamlanmadan proje değiştirilemez."},
                )
        return await call_next(request)

    @app.get("/health")
    def health():
        return {"status": "ok", "network": "loopback-only"}

    @app.post("/system/select-directory")
    def choose_directory(request: NativeDialogRequest):
        try:
            return {"path": select_directory(request.title)}
        except NativeDialogUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/system/select-file")
    def choose_file(request: NativeDialogRequest):
        try:
            return {"path": select_file(request.title)}
        except NativeDialogUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/projects")
    def create_project(request: ProjectCreateRequest):
        try:
            workspace = registry.add(ProjectWorkspace.create(request.path, request.name))
        except FileExistsError as exc:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Bu klasörde zaten bir MetrajAI projesi var. "
                    "Üstteki ‘Projeyi aç’ seçeneğini kullanın."
                ),
            ) from exc
        except OSError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Proje klasörü oluşturulamadı: {exc.strerror or str(exc)}",
            ) from exc
        configure_logging(workspace.logs_dir)
        return workspace.summary()

    @app.post("/projects/open")
    def open_project(request: ProjectOpenRequest):
        try:
            workspace = registry.add(ProjectWorkspace(request.path))
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail="Seçilen klasörde MetrajAI projesi bulunamadı.",
            ) from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Proje açılamadı: {exc}",
            ) from exc
        configure_logging(workspace.logs_dir)
        return workspace.summary()

    @app.get("/projects/{project_id}")
    def project_summary(project_id: str):
        return registry.get(project_id).summary()

    @app.get("/projects/{project_id}/backups")
    def list_backups(project_id: str):
        return registry.get(project_id).list_backups()

    @app.post("/projects/{project_id}/backups")
    def create_backup(project_id: str):
        if jobs.project_is_busy(project_id):
            raise HTTPException(status_code=409, detail="Çalışan analiz sırasında yedek alınamaz")
        return registry.get(project_id).create_backup("manual")

    @app.post("/projects/{project_id}/sources")
    def import_source(project_id: str, request: SourceImportRequest):
        workspace = registry.get(project_id)
        try:
            return workspace.add_source(
                request.path,
                discipline=request.discipline,
                role=request.role,
                floor=request.floor,
                floor_kind=request.floor_kind,
                sheet_kind=request.sheet_kind,
                repeat_floors=request.repeat_floors,
                revision=request.revision,
                drawing_unit=request.drawing_unit,
            ).model_dump(mode="json")
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/projects/{project_id}/sources")
    def list_sources(project_id: str):
        return [item.model_dump(mode="json") for item in registry.get(project_id).list_sources()]

    @app.delete("/projects/{project_id}/sources/{source_id}")
    def delete_source(project_id: str, source_id: str):
        if jobs.project_is_busy(project_id):
            raise HTTPException(
                status_code=409,
                detail="Çalışan analiz tamamlanmadan veya iptal edilmeden kaynak silinemez.",
            )
        workspace = registry.get(project_id)
        try:
            result = workspace.delete_source(source_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {**result, "project": workspace.summary()}

    @app.patch("/projects/{project_id}/sources/{source_id}/unit")
    def confirm_unit(project_id: str, source_id: str, request: UnitConfirmationRequest):
        if request.unit == DrawingUnit.UNKNOWN:
            raise HTTPException(status_code=422, detail="Unit must be mm, cm or m")
        workspace = registry.get(project_id)
        try:
            return workspace.confirm_source_unit(source_id, request.unit).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.patch("/projects/{project_id}/sources/{source_id}/calibration")
    def confirm_calibration(
        project_id: str,
        source_id: str,
        request: CalibrationRequest,
    ):
        try:
            return (
                registry.get(project_id)
                .confirm_source_calibration(source_id, scale=request.scale, points=request.points)
                .model_dump(mode="json")
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.patch("/projects/{project_id}/sources/{source_id}/discipline")
    def update_source_discipline(
        project_id: str,
        source_id: str,
        request: SourceDisciplineRequest,
    ):
        if jobs.project_is_busy(project_id):
            raise HTTPException(
                status_code=409,
                detail="Çalışan analiz sırasında kaynak disiplini değiştirilemez.",
            )
        workspace = registry.get(project_id)
        try:
            source, cleared_count = workspace.update_source_discipline(
                source_id, request.discipline
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        EngineService(workspace).refresh_quantities()
        return {
            "source": source.model_dump(mode="json"),
            "cleared_element_count": cleared_count,
            "project": workspace.summary(),
        }

    @app.patch("/projects/{project_id}/sources/{source_id}/mapping")
    def update_source_mapping(
        project_id: str,
        source_id: str,
        request: SourceMappingRequest,
    ):
        if jobs.project_is_busy(project_id):
            raise HTTPException(
                status_code=409,
                detail="Çalışan analiz sırasında kat/pafta eşlemesi değiştirilemez.",
            )
        workspace = registry.get(project_id)
        try:
            source, cleared_count = workspace.update_source_mapping(
                source_id,
                **request.model_dump(),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        EngineService(workspace).refresh_quantities()
        return {
            "source": source.model_dump(mode="json"),
            "cleared_element_count": cleared_count,
            "project": workspace.summary(),
        }

    @app.get("/projects/{project_id}/floors")
    def list_floors(project_id: str):
        return [item.model_dump(mode="json") for item in registry.get(project_id).list_floors()]

    @app.post("/projects/{project_id}/floors")
    def create_floor(project_id: str, request: FloorRequest):
        workspace = registry.get(project_id)
        try:
            floor = workspace.put_floor(
                FloorDefinition(project_id=project_id, **request.model_dump())
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return floor.model_dump(mode="json")

    @app.put("/projects/{project_id}/floors/{floor_id}")
    def update_floor(project_id: str, floor_id: str, request: FloorRequest):
        workspace = registry.get(project_id)
        try:
            existing = workspace.get_floor(floor_id)
            floor = workspace.put_floor(
                FloorDefinition(
                    **{
                        **existing.model_dump(),
                        **request.model_dump(),
                        "project_id": project_id,
                    }
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return floor.model_dump(mode="json")

    @app.delete("/projects/{project_id}/floors/{floor_id}", status_code=204)
    def delete_floor(project_id: str, floor_id: str):
        try:
            registry.get(project_id).delete_floor(floor_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.put("/projects/{project_id}/sources/{source_id}/sheet-assignment")
    def put_sheet_assignment(
        project_id: str,
        source_id: str,
        request: SheetAssignmentRequest,
    ):
        workspace = registry.get(project_id)
        try:
            item = workspace.put_sheet_assignment(
                SheetAssignment(
                    project_id=project_id,
                    source_id=source_id,
                    **request.model_dump(),
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return item.model_dump(mode="json")

    @app.get("/projects/{project_id}/sheet-assignments")
    def list_sheet_assignments(project_id: str):
        return [
            item.model_dump(mode="json")
            for item in registry.get(project_id).list_sheet_assignments()
        ]

    @app.post("/projects/{project_id}/repeat-assignments")
    def create_repeat_assignment(project_id: str, request: RepeatAssignmentRequest):
        workspace = registry.get(project_id)
        try:
            item = workspace.put_repeat_assignment(
                RepeatAssignment(project_id=project_id, **request.model_dump())
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return item.model_dump(mode="json")

    @app.get("/projects/{project_id}/repeat-assignments")
    def list_repeat_assignments(project_id: str, source_id: str | None = None):
        return [
            item.model_dump(mode="json")
            for item in registry.get(project_id).list_repeat_assignments(source_id)
        ]

    @app.delete("/projects/{project_id}/repeat-assignments/{assignment_id}", status_code=204)
    def delete_repeat_assignment(project_id: str, assignment_id: str):
        try:
            registry.get(project_id).delete_repeat_assignment(assignment_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/projects/{project_id}/architectural-assignments")
    def create_architectural_assignment(project_id: str, request: ArchitecturalAssignmentRequest):
        try:
            workspace = registry.get(project_id)
            item = workspace.put_architectural_assignment(
                ArchitecturalAssignment(project_id=project_id, **request.model_dump())
            )
            assignments = workspace.list_architectural_assignments(source_id=item.source_id)
            elements = apply_architectural_assignments(workspace.list_elements(), assignments)
            source = workspace.get_source(item.source_id)
            elements, _ = reconcile_architectural_elements(source, elements)
            elements = apply_architectural_assignments(elements, assignments)
            workspace.replace_source_elements(
                item.source_id,
                [element for element in elements if element.source_id == item.source_id],
            )
            EngineService(workspace).refresh_quantities()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return item.model_dump(mode="json")

    @app.get("/projects/{project_id}/architectural-assignments")
    def list_architectural_assignments(
        project_id: str,
        source_id: str | None = None,
        subject_element_id: str | None = None,
    ):
        return [
            item.model_dump(mode="json")
            for item in registry.get(project_id).list_architectural_assignments(
                source_id=source_id, subject_element_id=subject_element_id
            )
        ]

    @app.delete(
        "/projects/{project_id}/architectural-assignments/{assignment_id}",
        status_code=204,
    )
    def delete_architectural_assignment(project_id: str, assignment_id: str):
        try:
            registry.get(project_id).delete_architectural_assignment(assignment_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/projects/{project_id}/analyses", status_code=202)
    def start_analysis(project_id: str, request: AnalysisRequest):
        try:
            run = jobs.start(registry.get(project_id), request.source_ids)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return run.model_dump(mode="json")

    @app.get("/analyses/{run_id}")
    def get_analysis(run_id: str):
        try:
            return jobs.get(run_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/analyses/{run_id}", status_code=202)
    def cancel_analysis(run_id: str):
        try:
            return jobs.cancel(run_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/projects/{project_id}/elements")
    def list_elements(
        project_id: str,
        source_id: str | None = None,
        status: ReviewStatus | None = None,
    ):
        return [
            item.model_dump(mode="json")
            for item in registry.get(project_id).list_elements(source_id=source_id, status=status)
        ]

    @app.patch("/projects/{project_id}/elements/{element_id}/review")
    def review_element(project_id: str, element_id: str, request: ReviewRequest):
        decision = ReviewDecision(
            element_id=element_id,
            status=request.status,
            reviewer=request.reviewer,
            reason=request.reason,
            measurement_overrides=request.measurement_overrides,
        )
        try:
            return EngineService(registry.get(project_id)).review(decision).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/projects/{project_id}/elements/{element_id}/evidence")
    def list_element_evidence(project_id: str, element_id: str):
        workspace = registry.get(project_id)
        try:
            workspace.get_element(element_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return [
            item.model_dump(mode="json") for item in workspace.list_element_evidence(element_id)
        ]

    @app.get("/projects/{project_id}/manual-overrides")
    def list_manual_overrides(project_id: str, element_id: str | None = None):
        return [
            item.model_dump(mode="json")
            for item in registry.get(project_id).list_manual_overrides(element_id)
        ]

    @app.patch("/projects/{project_id}/elements/review-bulk")
    def review_elements_bulk(project_id: str, request: BulkReviewRequest):
        element_ids = list(dict.fromkeys(request.element_ids))
        decisions = [
            ReviewDecision(
                element_id=element_id,
                status=request.status,
                reviewer=request.reviewer,
                reason=request.reason,
            )
            for element_id in element_ids
        ]
        reviewed, skipped = EngineService(registry.get(project_id)).review_many(decisions)
        return {
            "requested_count": len(element_ids),
            "reviewed_element_ids": reviewed,
            "skipped": skipped,
        }

    @app.patch("/projects/{project_id}/rebar-revision")
    def select_rebar_revision(project_id: str, request: RebarRevisionRequest):
        workspace = registry.get(project_id)
        try:
            result = workspace.select_rebar_revision(
                request.source_id,
                request.table_handle,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        EngineService(workspace).refresh_quantities()
        return result

    @app.post("/projects/{project_id}/revision-comparisons")
    def compare_project_revisions(
        project_id: str,
        request: RevisionComparisonRequest,
    ):
        workspace = registry.get(project_id)
        try:
            result = compare_revisions(
                workspace.get_source(request.old_source_id),
                workspace.get_source(request.new_source_id),
                workspace.list_elements(),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result.model_dump(mode="json")

    @app.get("/projects/{project_id}/quantities")
    def list_quantities(project_id: str):
        return [item.model_dump(mode="json") for item in registry.get(project_id).list_quantities()]

    @app.post("/projects/{project_id}/price-catalogs/import")
    def import_price_catalog(project_id: str, request: PriceCatalogImportRequest):
        workspace = registry.get(project_id)
        try:
            catalog, items = import_price_catalog_file(
                request.path,
                project_id=project_id,
                name=request.name,
                year=request.year,
                version=request.version,
                currency=request.currency,
                is_official=request.is_official,
                source_url=request.source_url,
            )
            catalog.stored_path = workspace.store_catalog_source(request.path, catalog.sha256)
            workspace.put_price_catalog(catalog, items)
        except (FileNotFoundError, CatalogImportError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "catalog": catalog.model_dump(mode="json"),
            "item_count": len(items),
        }

    @app.get("/projects/{project_id}/price-catalogs")
    def list_price_catalogs(project_id: str):
        return [
            item.model_dump(mode="json") for item in registry.get(project_id).list_price_catalogs()
        ]

    @app.get("/projects/{project_id}/price-items")
    def list_price_items(project_id: str, catalog_id: str | None = None):
        return [
            item.model_dump(mode="json")
            for item in registry.get(project_id).list_price_items(catalog_id)
        ]

    @app.post("/projects/{project_id}/price-mappings/suggest")
    def suggest_mappings(project_id: str, request: PriceSuggestionRequest):
        workspace = registry.get(project_id)
        catalog_ids = set(request.catalog_ids)
        items = [
            item
            for item in workspace.list_price_items()
            if not catalog_ids or item.catalog_id in catalog_ids
        ]
        approved_quantity_ids = {
            item.quantity_line_id
            for item in workspace.list_price_mappings()
            if item.status == MappingStatus.APPROVED
        }
        suggestions = suggest_price_mappings(
            project_id,
            [item for item in workspace.list_quantities() if item.id not in approved_quantity_ids],
            items,
            minimum_confidence=request.minimum_confidence,
        )
        saved = [workspace.put_price_mapping(item) for item in suggestions]
        return [item.model_dump(mode="json") for item in saved]

    @app.put("/projects/{project_id}/price-mappings")
    def put_price_mapping(project_id: str, request: PriceMappingRequest):
        workspace = registry.get(project_id)
        try:
            item = workspace.put_price_mapping(
                PriceMapping(project_id=project_id, **request.model_dump())
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return item.model_dump(mode="json")

    @app.get("/projects/{project_id}/price-mappings")
    def list_price_mappings(project_id: str):
        return [
            item.model_dump(mode="json") for item in registry.get(project_id).list_price_mappings()
        ]

    @app.post("/projects/{project_id}/offer-scenarios")
    def put_offer_scenario(project_id: str, request: OfferScenarioRequest):
        workspace = registry.get(project_id)
        try:
            scenario = OfferScenario(
                project_id=project_id,
                name=request.name,
                currency=request.currency.upper(),
                exchange_rate=request.exchange_rate,
                exchange_rate_source=request.exchange_rate_source,
                exchange_rate_date=request.exchange_rate_date,
                adjustments=[OfferAdjustment(**item.model_dump()) for item in request.adjustments],
                approved=request.approved,
                reviewer=request.reviewer,
            )
            workspace.put_offer_scenario(scenario)
            lines, totals = calculate_offer(
                scenario,
                workspace.list_quantities(),
                workspace.list_price_mappings(),
                workspace.list_price_items(),
            )
            workspace.replace_cost_lines(scenario.id, lines)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "scenario": scenario.model_dump(mode="json"),
            "line_count": len(lines),
            "totals": totals,
        }

    @app.get("/projects/{project_id}/offer-scenarios")
    def list_offer_scenarios(project_id: str):
        return [
            item.model_dump(mode="json") for item in registry.get(project_id).list_offer_scenarios()
        ]

    @app.get("/projects/{project_id}/offer-scenarios/{scenario_id}")
    def get_offer(project_id: str, scenario_id: str):
        workspace = registry.get(project_id)
        try:
            scenario = workspace.get_offer_scenario(scenario_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        lines, totals = calculate_offer(
            scenario,
            workspace.list_quantities(),
            workspace.list_price_mappings(),
            workspace.list_price_items(),
        )
        workspace.replace_cost_lines(scenario.id, lines)
        return {
            "scenario": scenario.model_dump(mode="json"),
            "cost_lines": [item.model_dump(mode="json") for item in lines],
            "totals": totals,
        }

    @app.get("/projects/{project_id}/validation-gates")
    def list_validation_gates(project_id: str):
        return [
            item.model_dump(mode="json")
            for item in registry.get(project_id).list_validation_gates()
        ]

    @app.put("/projects/{project_id}/validation-gates")
    def put_validation_gate(project_id: str, request: ValidationGateRequest):
        workspace = registry.get(project_id)
        try:
            gate = workspace.put_validation_gate(
                ValidationGate(project_id=project_id, **request.model_dump())
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        EngineService(workspace).refresh_quantities()
        return gate.model_dump(mode="json")

    @app.get("/projects/{project_id}/assumptions")
    def list_assumptions(project_id: str):
        return [
            item.model_dump(mode="json") for item in registry.get(project_id).list_assumptions()
        ]

    @app.post("/projects/{project_id}/assumptions")
    def put_assumption(project_id: str, request: AssumptionRequest):
        workspace = registry.get(project_id)
        item = workspace.put_assumption(Assumption(**request.model_dump()))
        EngineService(workspace).refresh_quantities()
        return item.model_dump(mode="json")

    @app.get("/projects/{project_id}/warnings")
    def list_warnings(project_id: str):
        return [item.model_dump(mode="json") for item in registry.get(project_id).list_warnings()]

    @app.post("/projects/{project_id}/report-payload")
    def create_report_payload(project_id: str):
        workspace = registry.get(project_id)
        path = workspace.write_report_payload(build_report_payload(workspace))
        return {"path": str(path)}

    @app.post("/projects/{project_id}/reports")
    def create_excel_report(project_id: str):
        try:
            path = export_traceable_excel(registry.get(project_id))
        except ExcelRuntimeUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"path": str(path)}

    return app
