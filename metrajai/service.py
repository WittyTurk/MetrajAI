from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor

from .analyzers import DxfAnalyzer
from .analyzers.architectural_height import (
    ArchitecturalHeightEvidence,
    apply_architectural_heights,
    evidence_warnings,
    extract_architectural_height_evidence_from_path,
)
from .calculations import calculate_quantities
from .contracts import (
    AnalysisRun,
    AnalysisStatus,
    AnalysisWarning,
    Discipline,
    ElementEvidence,
    EvidenceKind,
    ReliabilityState,
    ReviewDecision,
    SourceFile,
    SourceFormat,
    utc_now,
)
from .floor_management import apply_sheet_ownership, expand_approved_repeat_assignments
from .source_analyzers import analyze_non_dxf_source
from .workspace import ProjectWorkspace

LOGGER = logging.getLogger("metrajai.engine")
ProgressCallback = Callable[[AnalysisRun], None]


class AnalysisCancelled(RuntimeError):
    pass


class EngineService:
    def __init__(self, workspace: ProjectWorkspace):
        self.workspace = workspace
        self.analyzer = DxfAnalyzer()

    def analyze(
        self,
        source_ids: Iterable[str] | None = None,
        *,
        run: AnalysisRun | None = None,
        cancel_event: threading.Event | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> AnalysisRun:
        sources = self._resolve_sources(source_ids)
        active_run = run or AnalysisRun(source_ids=[source.id for source in sources])
        active_run.source_ids = [source.id for source in sources]
        active_run.status = AnalysisStatus.RUNNING
        active_run.message = "Kaynaklar analiz ediliyor"
        active_run.updated_at = utc_now()
        self._save_progress(active_run, on_progress)
        warnings: list[AnalysisWarning] = []
        try:
            height_evidence: list[ArchitecturalHeightEvidence] = []
            for source in sources:
                if source.discipline != Discipline.ARCHITECTURAL:
                    continue
                if source.source_format != SourceFormat.DXF:
                    continue
                items = extract_architectural_height_evidence_from_path(
                    source, self.workspace.source_path(source)
                )
                height_evidence.extend(items)
                warnings.extend(evidence_warnings(source, items))

            for index, source in enumerate(sources):
                self._check_cancel(cancel_event)
                if not self.workspace.verify_source_integrity(source):
                    raise ValueError(
                        f"Kaynak bütünlüğü doğrulanamadı: {source.original_name}. "
                        "Dosya proje klasörüne alındıktan sonra değişmiş."
                    )
                if source.source_format == SourceFormat.DXF:
                    elements, source_warnings, detected_unit = self.analyzer.analyze(
                        source, self.workspace.source_path(source)
                    )
                else:
                    elements, source_warnings, detected_unit = analyze_non_dxf_source(
                        source, self.workspace.source_path(source)
                    )
                if source.discipline in {
                    Discipline.STRUCTURAL,
                    Discipline.ARCHITECTURAL,
                } and height_evidence:
                    elements, applied_count = apply_architectural_heights(elements, height_evidence)
                    if applied_count:
                        height = height_evidence[0].height_m
                        warnings.append(
                            AnalysisWarning(
                                code="ARCHITECTURAL_HEIGHT_APPLIED",
                                message=(
                                    f"Mimari kesitten okunan {height:g} m yükseklik "
                                    f"{applied_count} taşıyıcı elemana inceleme adayı olarak "
                                    "aktarıldı; mühendis onayı gereklidir."
                                ),
                                source_id=source.id,
                                severity="info",
                            )
                        )
                elements, ownership_warnings = apply_sheet_ownership(
                    elements,
                    source,
                    sources,
                )
                source_warnings.extend(ownership_warnings)
                elements, floor_warnings = expand_approved_repeat_assignments(
                    elements,
                    source,
                    self.workspace.list_repeat_assignments(source.id),
                    self.workspace.list_floors(),
                )
                source_warnings.extend(floor_warnings)
                source.detected_unit = detected_unit
                self.workspace.save_source(source)
                self.workspace.replace_source_elements(source.id, elements)
                for element in elements:
                    evidence = [
                        ElementEvidence(
                            element_id=element.id,
                            source_id=element.source_id,
                            kind=(
                                EvidenceKind.SCHEDULE
                                if element.geometry.kind.endswith("_schedule_row")
                                else EvidenceKind.GEOMETRY
                            ),
                            label=str(element.properties.get("element_label", "")),
                            source_handle=element.source_handle,
                            bbox=element.geometry.bbox,
                            values={
                                key: value
                                for key, value in element.measurements.items()
                                if isinstance(value, (int, float))
                            },
                            confidence=element.confidence,
                        )
                    ]
                    self.workspace.replace_element_evidence(element.id, evidence)
                self.workspace.apply_rebar_revision_assumptions(source.id)
                warnings.extend(source_warnings)
                active_run.progress = (index + 1) / max(len(sources), 1) * 0.85
                active_run.message = f"{source.original_name} analiz edildi"
                active_run.updated_at = utc_now()
                self._save_progress(active_run, on_progress)

            self._check_cancel(cancel_event)
            quantity_warnings = self.refresh_quantities()
            warnings.extend(quantity_warnings)
            active_run.status = AnalysisStatus.COMPLETED
            active_run.progress = 1.0
            active_run.message = "Analiz tamamlandı; kesin metraj yalnız onaylı elemanları içeriyor"
            active_run.element_count = len(self.workspace.list_elements())
            active_run.warning_count = len(warnings)
            active_run.updated_at = utc_now()
            self.workspace.replace_warnings(active_run.id, warnings)
            self._save_progress(active_run, on_progress)
            LOGGER.info(
                "analysis_completed run=%s elements=%s warnings=%s",
                active_run.id,
                active_run.element_count,
                active_run.warning_count,
            )
        except AnalysisCancelled:
            active_run.status = AnalysisStatus.CANCELLED
            active_run.message = "Analiz kullanıcı tarafından iptal edildi"
            active_run.updated_at = utc_now()
            self._save_progress(active_run, on_progress)
            LOGGER.info("analysis_cancelled run=%s", active_run.id)
        except Exception as exc:
            active_run.status = AnalysisStatus.FAILED
            active_run.message = str(exc)
            active_run.updated_at = utc_now()
            self._save_progress(active_run, on_progress)
            LOGGER.exception("analysis_failed run=%s", active_run.id)
        return active_run

    def review(self, decision: ReviewDecision):
        element = self.workspace.review_element(decision)
        self.refresh_quantities()
        return element

    def review_many(
        self,
        decisions: Iterable[ReviewDecision],
    ) -> tuple[list[str], dict[str, str]]:
        reviewed: list[str] = []
        skipped: dict[str, str] = {}
        for decision in decisions:
            try:
                self.workspace.review_element(decision)
            except (KeyError, ValueError) as exc:
                skipped[decision.element_id] = str(exc)
            else:
                reviewed.append(decision.element_id)
        self.refresh_quantities()
        return reviewed, skipped

    def refresh_quantities(self) -> list[AnalysisWarning]:
        gate_by_discipline = {
            gate.discipline: gate for gate in self.workspace.list_validation_gates()
        }
        blocked_disciplines = {
            discipline
            for discipline in (Discipline.MECHANICAL, Discipline.ELECTRICAL)
            if gate_by_discipline[discipline].state != ReliabilityState.RELIABLE
        }
        quantities, warnings = calculate_quantities(
            self.workspace.list_elements(),
            self.workspace.list_assumptions(),
            blocked_disciplines,
        )
        self.workspace.replace_quantities(quantities)
        return warnings

    def _resolve_sources(self, source_ids: Iterable[str] | None) -> list[SourceFile]:
        if source_ids is None:
            return self.workspace.list_sources()
        return [self.workspace.get_source(source_id) for source_id in source_ids]

    @staticmethod
    def _check_cancel(cancel_event: threading.Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise AnalysisCancelled

    def _save_progress(self, run: AnalysisRun, on_progress: ProgressCallback | None) -> None:
        self.workspace.save_run(run)
        if on_progress:
            on_progress(run)


class BackgroundAnalysisManager:
    def __init__(self, max_workers: int = 1):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="metrajai")
        self._jobs: dict[str, tuple[ProjectWorkspace, threading.Event, Future[AnalysisRun]]] = {}
        self._lock = threading.Lock()

    def start(
        self,
        workspace: ProjectWorkspace,
        source_ids: Iterable[str] | None = None,
    ) -> AnalysisRun:
        ids = (
            list(source_ids)
            if source_ids is not None
            else [source.id for source in workspace.list_sources()]
        )
        run = AnalysisRun(source_ids=ids)
        workspace.save_run(run)
        cancel_event = threading.Event()
        future = self._executor.submit(
            EngineService(workspace).analyze,
            ids,
            run=run,
            cancel_event=cancel_event,
        )
        with self._lock:
            self._jobs[run.id] = (workspace, cancel_event, future)
        return run

    def cancel(self, run_id: str) -> AnalysisRun:
        workspace, cancel_event, _ = self._job(run_id)
        cancel_event.set()
        run = workspace.get_run(run_id)
        run.message = "İptal isteği alındı"
        workspace.save_run(run)
        return run

    def get(self, run_id: str) -> AnalysisRun:
        workspace, _, _ = self._job(run_id)
        return workspace.get_run(run_id)

    def project_is_busy(self, project_id: str) -> bool:
        with self._lock:
            return any(
                workspace.manifest.project_id == project_id and not future.done()
                for workspace, _, future in self._jobs.values()
            )

    def _job(self, run_id: str):
        with self._lock:
            try:
                return self._jobs[run_id]
            except KeyError as exc:
                raise KeyError(f"Unknown background analysis: {run_id}") from exc
