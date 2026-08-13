from __future__ import annotations

import hmac
from secrets import token_urlsafe

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .contracts import (
    Assumption,
    Discipline,
    DrawingUnit,
    FloorKind,
    ReviewDecision,
    ReviewStatus,
    SheetKind,
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
    app = FastAPI(title="MetrajAI Local Engine", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "tauri://localhost",
            "http://tauri.localhost",
            "http://localhost:1420",
            "http://127.0.0.1:1420",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
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
        workspace = registry.add(ProjectWorkspace.create(request.path, request.name))
        configure_logging(workspace.logs_dir)
        return workspace.summary()

    @app.post("/projects/open")
    def open_project(request: ProjectOpenRequest):
        workspace = registry.add(ProjectWorkspace(request.path))
        configure_logging(workspace.logs_dir)
        return workspace.summary()

    @app.get("/projects/{project_id}")
    def project_summary(project_id: str):
        return registry.get(project_id).summary()

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

    @app.post("/projects/{project_id}/analyses", status_code=202)
    def start_analysis(project_id: str, request: AnalysisRequest):
        run = jobs.start(registry.get(project_id), request.source_ids)
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
