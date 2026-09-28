from __future__ import annotations

import hashlib
import json
import logging
import math
import shutil
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from .analyzers.source_inspection import inspect_source_file
from .calculations import (
    calculate_quantities,
    derive_element_measurements,
    resolved_opening_area,
    synchronize_opening_dependencies,
)
from .contracts import (
    AnalysisRun,
    AnalysisWarning,
    ArchitecturalAssignment,
    Assumption,
    CalibrationStatus,
    CostLine,
    DetectedElement,
    Discipline,
    DrawingUnit,
    ElementEvidence,
    FloorDefinition,
    FloorKind,
    ManualOverride,
    MappingStatus,
    OfferScenario,
    PriceCatalog,
    PriceItem,
    PriceMapping,
    ProjectManifest,
    QuantityLine,
    ReliabilityState,
    RepeatAssignment,
    RepeatScope,
    ReviewDecision,
    ReviewStatus,
    SheetAssignment,
    SheetKind,
    SourceFile,
    SourceFormat,
    ValidationGate,
    utc_now,
)
from .floor_management import infer_floor_kind, infer_sheet_kind, normalize_repeat_floors

LOGGER = logging.getLogger("metrajai.workspace")

MANIFEST_NAME = "manifest.json"
DATABASE_NAME = "project.metrajai.sqlite3"
CURRENT_SCHEMA_VERSION = 3
SUPPORTED_SOURCE_FORMATS = {
    SourceFormat.DXF,
    SourceFormat.XLSX,
    SourceFormat.XLS,
    SourceFormat.PDF,
}


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in value)
    return cleaned.strip().replace(" ", "_") or "source"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_format(path: Path) -> SourceFormat:
    try:
        return SourceFormat(path.suffix.lower().removeprefix("."))
    except ValueError:
        return SourceFormat.UNKNOWN


class ProjectWorkspace:
    """Portable, single-project workspace with immutable source copies."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        manifest_path = self.root / MANIFEST_NAME
        if not manifest_path.exists():
            raise FileNotFoundError(f"MetrajAI manifest not found: {manifest_path}")
        self.manifest = ProjectManifest.model_validate_json(manifest_path.read_text("utf-8"))
        self.database_path = self.root / DATABASE_NAME
        self.sources_dir = self.root / "sources"
        self.cache_dir = self.root / "cache"
        self.exports_dir = self.root / "exports"
        self.logs_dir = self.root / "logs"
        self.backups_dir = self.root / "backups"
        self.backups_dir.mkdir(exist_ok=True)
        previous_version = self.manifest.schema_version
        if previous_version < CURRENT_SCHEMA_VERSION and self.database_path.exists():
            self.create_backup(f"schema-v{previous_version}-to-v{CURRENT_SCHEMA_VERSION}")
        self._init_database()
        if previous_version < CURRENT_SCHEMA_VERSION:
            self.manifest.schema_version = CURRENT_SCHEMA_VERSION
            self.save_manifest()
        self.source_safety_notices = self._quarantine_misclassified_sources()

    def _quarantine_misclassified_sources(self) -> list[str]:
        """Remove stale derived results from a structural source proved architectural.

        The original source and a pre-change database backup are retained.
        """
        conflicts: list[SourceFile] = []
        notices: list[str] = []
        for source in self.list_sources():
            if (
                source.source_format != SourceFormat.DXF
                or source.discipline != Discipline.STRUCTURAL
            ):
                continue
            if not self.verify_source_integrity(source):
                LOGGER.warning("source_integrity_failed source=%s", source.id)
                continue
            try:
                inspection = inspect_source_file(self.source_path(source), check_area=False)
            except Exception as exc:
                LOGGER.warning("source_preflight_failed source=%s error=%s", source.id, exc)
                continue
            if inspection["suggested_discipline"] != Discipline.ARCHITECTURAL.value:
                continue
            conflicts.append(source)
            notices.append(
                f"{source.original_name}: mimari pafta statik olarak kayıtlı. "
                "Kaynak türünü Mimari yapıp yeniden analiz edin."
            )
        stale = [source for source in conflicts if self.list_elements(source_id=source.id)]
        if stale:
            self.create_backup("misclassified-source-quarantine")
            with self._connect() as connection:
                for source in stale:
                    self._invalidate_source_results(connection, source.id)
            notices.append(
                "Yanlış sınıflanan kaynakların eski adayları ve türetilmiş metrajları "
                "yedek alınarak geçersiz kılındı."
            )
        return notices

    @classmethod
    def create(cls, root: str | Path, name: str) -> ProjectWorkspace:
        target = Path(root).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        manifest_path = target / MANIFEST_NAME
        if manifest_path.exists():
            raise FileExistsError(f"A MetrajAI project already exists at {target}")
        for folder in ("sources", "cache", "exports", "logs", "backups"):
            (target / folder).mkdir(exist_ok=True)
        manifest = ProjectManifest(name=name)
        manifest_path.write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return cls(target)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_database(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS sources_identity
                    ON sources(sha256, id);

                CREATE TABLE IF NOT EXISTS elements (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    element_type TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES sources(id)
                );
                CREATE INDEX IF NOT EXISTS elements_source ON elements(source_id);
                CREATE INDEX IF NOT EXISTS elements_review ON elements(review_status);

                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY,
                    element_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY(element_id) REFERENCES elements(id)
                );
                CREATE INDEX IF NOT EXISTS reviews_element ON reviews(element_id);

                CREATE TABLE IF NOT EXISTS assumptions (
                    id TEXT PRIMARY KEY,
                    assumption_key TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS assumptions_key ON assumptions(assumption_key);

                CREATE TABLE IF NOT EXISTS quantity_lines (
                    id TEXT PRIMARY KEY,
                    element_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY(element_id) REFERENCES elements(id)
                );
                CREATE INDEX IF NOT EXISTS quantities_element ON quantity_lines(element_id);

                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    data TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS warnings (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS warnings_run ON warnings(run_id);

                CREATE TABLE IF NOT EXISTS schema_meta (
                    version INTEGER NOT NULL,
                    migrated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS floors (
                    id TEXT PRIMARY KEY,
                    floor_order INTEGER NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS floors_order ON floors(floor_order);

                CREATE TABLE IF NOT EXISTS sheet_assignments (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL UNIQUE,
                    data TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS repeat_assignments (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    approved INTEGER NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS repeats_source ON repeat_assignments(source_id);

                CREATE TABLE IF NOT EXISTS element_evidence (
                    id TEXT PRIMARY KEY,
                    element_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS evidence_element ON element_evidence(element_id);

                CREATE TABLE IF NOT EXISTS manual_overrides (
                    id TEXT PRIMARY KEY,
                    element_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY(element_id) REFERENCES elements(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS overrides_element ON manual_overrides(element_id);

                CREATE TABLE IF NOT EXISTS price_catalogs (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS price_items (
                    id TEXT PRIMARY KEY,
                    catalog_id TEXT NOT NULL,
                    code TEXT NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY(catalog_id) REFERENCES price_catalogs(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS price_items_catalog ON price_items(catalog_id);
                CREATE INDEX IF NOT EXISTS price_items_code ON price_items(code);

                CREATE TABLE IF NOT EXISTS price_mappings (
                    id TEXT PRIMARY KEY,
                    quantity_line_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS mappings_quantity ON price_mappings(quantity_line_id);

                CREATE TABLE IF NOT EXISTS offer_scenarios (
                    id TEXT PRIMARY KEY,
                    approved INTEGER NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cost_lines (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY(scenario_id) REFERENCES offer_scenarios(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS cost_lines_scenario ON cost_lines(scenario_id);

                CREATE TABLE IF NOT EXISTS validation_gates (
                    id TEXT PRIMARY KEY,
                    discipline TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL,
                    data TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS architectural_assignments (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    subject_element_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    approved INTEGER NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE,
                    FOREIGN KEY(subject_element_id) REFERENCES elements(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS architecture_assignments_subject
                    ON architectural_assignments(subject_element_id);
                CREATE INDEX IF NOT EXISTS architecture_assignments_source
                    ON architectural_assignments(source_id);
                """
            )
            current = connection.execute(
                "SELECT version FROM schema_meta ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            if current is None or int(current["version"]) != CURRENT_SCHEMA_VERSION:
                connection.execute(
                    "INSERT INTO schema_meta(version, migrated_at) VALUES (?, ?)",
                    (CURRENT_SCHEMA_VERSION, utc_now().isoformat()),
                )

    def create_backup(self, reason: str = "manual") -> dict[str, str]:
        """Create a consistent SQLite + manifest recovery point without touching sources."""
        safe_reason = _safe_name(reason)[:60]
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        folder = self.backups_dir / f"{stamp}_{safe_reason}"
        folder.mkdir(parents=True, exist_ok=False)
        if self.database_path.exists() and self.database_path.stat().st_size:
            source = sqlite3.connect(self.database_path)
            target = sqlite3.connect(folder / DATABASE_NAME)
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
        manifest_path = self.root / MANIFEST_NAME
        if manifest_path.exists():
            shutil.copy2(manifest_path, folder / MANIFEST_NAME)
        metadata = {
            "created_at": utc_now().isoformat(),
            "reason": reason,
            "schema_version": str(self.manifest.schema_version),
        }
        (folder / "backup.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"path": str(folder), **metadata}

    def list_backups(self) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for metadata_path in sorted(self.backups_dir.glob("*/backup.json"), reverse=True):
            try:
                item = json.loads(metadata_path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            result.append({"path": str(metadata_path.parent), **item})
        return result

    def save_manifest(self) -> None:
        self.manifest.updated_at = utc_now()
        (self.root / MANIFEST_NAME).write_text(
            self.manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def add_source(
        self,
        path: str | Path,
        *,
        discipline: Discipline,
        role: str,
        floor: str = "GENEL",
        floor_kind: FloorKind | None = None,
        sheet_kind: SheetKind | None = None,
        repeat_floors: list[str] | None = None,
        revision: str = "",
        drawing_unit: DrawingUnit = DrawingUnit.UNKNOWN,
    ) -> SourceFile:
        source_path = Path(path).expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        source_format = _source_format(source_path)
        if source_format == SourceFormat.DWG:
            raise ValueError("DWG macOS pilotunda desteklenmiyor; dosyayı DXF olarak kaydedin")
        if source_format not in SUPPORTED_SOURCE_FORMATS:
            raise ValueError("Desteklenen kaynak biçimleri: DXF, XLSX, XLS ve PDF")
        floor = floor.strip() or "GENEL"
        resolved_floor_kind = floor_kind or infer_floor_kind(floor, source_path.name, role)
        resolved_sheet_kind = sheet_kind or infer_sheet_kind(source_path.name, role)
        resolved_repeat_floors = normalize_repeat_floors(floor, repeat_floors or [])
        if resolved_repeat_floors and (
            resolved_floor_kind != FloorKind.TYPICAL or resolved_sheet_kind != SheetKind.PLAN
        ):
            raise ValueError(
                "Kat tekrarı yalnız normal/tip kat olarak sınıflanan plan paftasında tanımlanabilir"
            )
        digest = _sha256(source_path)
        for existing in self.list_sources():
            if (
                existing.sha256 == digest
                and existing.discipline == discipline
                and existing.role == role
                and existing.floor == floor
                and existing.floor_kind == resolved_floor_kind
                and existing.sheet_kind == resolved_sheet_kind
                and existing.repeat_floors == resolved_repeat_floors
                and existing.revision == revision
            ):
                return existing

        destination_name = f"{digest[:12]}_{_safe_name(source_path.name)}"
        destination = self.sources_dir / destination_name
        if not destination.exists():
            shutil.copy2(source_path, destination)
        record = SourceFile(
            project_id=self.manifest.project_id,
            original_name=source_path.name,
            stored_path=str(destination.relative_to(self.root)),
            sha256=digest,
            size_bytes=source_path.stat().st_size,
            source_format=source_format,
            discipline=discipline,
            role=role,
            floor=floor,
            floor_kind=resolved_floor_kind,
            sheet_kind=resolved_sheet_kind,
            repeat_floors=resolved_repeat_floors,
            revision=revision,
            drawing_unit=drawing_unit,
            unit_confirmed=drawing_unit != DrawingUnit.UNKNOWN,
            calibration_status=(
                CalibrationStatus.REQUIRED
                if source_format == SourceFormat.PDF
                else CalibrationStatus.NOT_REQUIRED
            ),
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO sources(id, sha256, data) VALUES (?, ?, ?)",
                (record.id, record.sha256, record.model_dump_json()),
            )
        self.save_manifest()
        return record

    def source_path(self, source: SourceFile) -> Path:
        return self.root / source.stored_path

    def verify_source_integrity(self, source: SourceFile) -> bool:
        path = self.source_path(source)
        return path.is_file() and _sha256(path) == source.sha256

    def list_sources(self) -> list[SourceFile]:
        with self._connect() as connection:
            rows = connection.execute("SELECT data FROM sources ORDER BY rowid").fetchall()
        return [self._source_with_inferred_mapping(row["data"]) for row in rows]

    def get_source(self, source_id: str) -> SourceFile:
        with self._connect() as connection:
            row = connection.execute("SELECT data FROM sources WHERE id=?", (source_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown source: {source_id}")
        return self._source_with_inferred_mapping(row["data"])

    @staticmethod
    def _source_with_inferred_mapping(data: str) -> SourceFile:
        source = SourceFile.model_validate_json(data)
        if source.source_format == SourceFormat.UNKNOWN:
            source.source_format = _source_format(Path(source.original_name))
        if (
            source.source_format == SourceFormat.PDF
            and source.calibration_status == CalibrationStatus.NOT_REQUIRED
        ):
            source.calibration_status = CalibrationStatus.REQUIRED
        if source.sheet_kind == SheetKind.UNSPECIFIED:
            source.sheet_kind = infer_sheet_kind(source.original_name, source.role)
        if source.floor_kind == FloorKind.GENERAL:
            inferred = infer_floor_kind(source.floor, source.original_name, source.role)
            if inferred != FloorKind.GENERAL:
                source.floor_kind = inferred
        return source

    def save_source(self, source: SourceFile) -> SourceFile:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE sources SET sha256=?, data=? WHERE id=?",
                (source.sha256, source.model_dump_json(), source.id),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown source: {source.id}")
        return source

    def confirm_source_unit(self, source_id: str, unit: DrawingUnit) -> SourceFile:
        source = self.get_source(source_id)
        if source.source_format != SourceFormat.DXF:
            raise ValueError("Birim doğrulaması yalnız DXF kaynaklarında kullanılır")
        if unit == DrawingUnit.UNKNOWN:
            raise ValueError("Çizim birimi mm, cm veya m olmalıdır")
        previous_unit = source.drawing_unit if source.unit_confirmed else source.detected_unit
        if previous_unit != unit and self.list_elements(source_id=source_id):
            self.create_backup(f"unit-change-{source_id}")
        source.drawing_unit = unit
        source.unit_confirmed = unit != DrawingUnit.UNKNOWN
        with self._connect() as connection:
            if previous_unit != unit:
                self._invalidate_source_results(connection, source_id)
            connection.execute(
                "UPDATE sources SET data=? WHERE id=?", (source.model_dump_json(), source_id)
            )
        self.save_manifest()
        return source

    def confirm_source_calibration(
        self,
        source_id: str,
        *,
        scale: float,
        points: list[tuple[float, float]],
    ) -> SourceFile:
        source = self.get_source(source_id)
        if source.source_format != SourceFormat.PDF:
            raise ValueError("Kalibrasyon yalnız PDF kaynaklarında kullanılır")
        if (
            not math.isfinite(scale)
            or scale <= 0
            or len(points) != 2
            or any(not math.isfinite(coordinate) for point in points for coordinate in point)
        ):
            raise ValueError("PDF kalibrasyonu için pozitif ölçek ve iki nokta gerekir")
        previous_scale = source.calibration_scale
        if previous_scale != scale and self.list_elements(source_id=source_id):
            self.create_backup(f"calibration-change-{source_id}")
        source.calibration_scale = float(scale)
        source.calibration_points = points
        source.calibration_status = CalibrationStatus.CONFIRMED
        with self._connect() as connection:
            if previous_scale != scale:
                self._invalidate_source_results(connection, source_id)
            connection.execute(
                "UPDATE sources SET data=? WHERE id=?", (source.model_dump_json(), source_id)
            )
        self.save_manifest()
        return source

    def _invalidate_source_results(self, connection: sqlite3.Connection, source_id: str) -> int:
        element_ids = [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM elements WHERE source_id=?", (source_id,)
            ).fetchall()
        ]
        if element_ids:
            connection.execute(
                "DELETE FROM price_mappings WHERE quantity_line_id IN "
                "(SELECT id FROM quantity_lines WHERE element_id IN "
                "(SELECT id FROM elements WHERE source_id=?))",
                (source_id,),
            )
            connection.execute(
                "DELETE FROM quantity_lines WHERE element_id IN "
                "(SELECT id FROM elements WHERE source_id=?)",
                (source_id,),
            )
            connection.execute(
                "DELETE FROM reviews WHERE element_id IN "
                "(SELECT id FROM elements WHERE source_id=?)",
                (source_id,),
            )
            connection.execute(
                "DELETE FROM architectural_assignments WHERE subject_element_id IN "
                "(SELECT id FROM elements WHERE source_id=?)",
                (source_id,),
            )
            stale_ids = set(element_ids)
            for row in connection.execute(
                "SELECT id, data FROM architectural_assignments"
            ).fetchall():
                assignment = ArchitecturalAssignment.model_validate_json(row["data"])
                if any(target in stale_ids for target in assignment.target_element_ids):
                    connection.execute(
                        "DELETE FROM architectural_assignments WHERE id=?", (row["id"],)
                    )
            connection.execute("DELETE FROM elements WHERE source_id=?", (source_id,))
            connection.execute("DELETE FROM cost_lines")
        connection.execute("DELETE FROM element_evidence WHERE source_id=?", (source_id,))
        for row in connection.execute("SELECT id, data FROM warnings").fetchall():
            if json.loads(row["data"]).get("source_id") == source_id:
                connection.execute("DELETE FROM warnings WHERE id=?", (row["id"],))
        return len(element_ids)

    def put_floor(self, floor: FloorDefinition) -> FloorDefinition:
        if floor.project_id != self.manifest.project_id:
            raise ValueError("Floor belongs to another project")
        floor.name = floor.name.strip()
        if not floor.name:
            raise ValueError("Kat adı boş olamaz")
        if floor.height_m is not None and floor.height_m <= 0:
            raise ValueError("Kat yüksekliği pozitif olmalıdır")
        floor.updated_at = utc_now()
        with self._connect() as connection:
            duplicate = connection.execute(
                "SELECT id, data FROM floors WHERE id<>?", (floor.id,)
            ).fetchall()
            if any(
                FloorDefinition.model_validate_json(row["data"]).name.casefold()
                == floor.name.casefold()
                for row in duplicate
            ):
                raise ValueError(f"Kat adı zaten kullanılıyor: {floor.name}")
            connection.execute(
                """
                INSERT INTO floors(id, floor_order, data) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    floor_order=excluded.floor_order,
                    data=excluded.data
                """,
                (floor.id, floor.order, floor.model_dump_json()),
            )
        return floor

    def list_floors(self) -> list[FloorDefinition]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT data FROM floors ORDER BY floor_order, rowid"
            ).fetchall()
        return [FloorDefinition.model_validate_json(row["data"]) for row in rows]

    def get_floor(self, floor_id: str) -> FloorDefinition:
        with self._connect() as connection:
            row = connection.execute("SELECT data FROM floors WHERE id=?", (floor_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown floor: {floor_id}")
        return FloorDefinition.model_validate_json(row["data"])

    def delete_floor(self, floor_id: str) -> None:
        self.get_floor(floor_id)
        assignments = self.list_sheet_assignments()
        repeats = self.list_repeat_assignments()
        if any(floor_id in item.floor_ids for item in assignments) or any(
            floor_id in item.target_floor_ids for item in repeats
        ):
            raise ValueError("Kat bir pafta veya tekrar kararında kullanılıyor")
        with self._connect() as connection:
            connection.execute("DELETE FROM floors WHERE id=?", (floor_id,))

    def put_sheet_assignment(self, assignment: SheetAssignment) -> SheetAssignment:
        if assignment.project_id != self.manifest.project_id:
            raise ValueError("Sheet assignment belongs to another project")
        self.get_source(assignment.source_id)
        for floor_id in assignment.floor_ids:
            self.get_floor(floor_id)
        if assignment.approved and (not assignment.reviewer.strip() or len(assignment.reason) < 3):
            raise ValueError("Onaylı pafta eşlemesi için kullanıcı ve gerekçe zorunludur")
        assignment.updated_at = utc_now()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id FROM sheet_assignments WHERE source_id=?", (assignment.source_id,)
            ).fetchone()
            if existing is not None:
                assignment.id = existing["id"]
            connection.execute(
                """
                INSERT INTO sheet_assignments(id, source_id, data) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET source_id=excluded.source_id, data=excluded.data
                """,
                (assignment.id, assignment.source_id, assignment.model_dump_json()),
            )
        return assignment

    def list_sheet_assignments(self) -> list[SheetAssignment]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT data FROM sheet_assignments ORDER BY rowid"
            ).fetchall()
        return [SheetAssignment.model_validate_json(row["data"]) for row in rows]

    def put_repeat_assignment(self, assignment: RepeatAssignment) -> RepeatAssignment:
        if assignment.project_id != self.manifest.project_id:
            raise ValueError("Repeat assignment belongs to another project")
        self.get_source(assignment.source_id)
        for floor_id in assignment.target_floor_ids:
            self.get_floor(floor_id)
        if assignment.scope == RepeatScope.ELEMENT:
            if not assignment.element_ids:
                raise ValueError("Eleman tekrarı için en az bir eleman seçin")
            elements = [self.get_element(element_id) for element_id in assignment.element_ids]
            if any(item.source_id != assignment.source_id for item in elements):
                raise ValueError("Tekrarlanan elemanlar aynı kaynakta olmalıdır")
        if assignment.scope == RepeatScope.TEMPLATE and not assignment.template_label.strip():
            raise ValueError("Şablon tekrarı için M1, M2 gibi bir etiket gerekir")
        if assignment.approved and (
            not assignment.reviewer.strip() or len(assignment.reason.strip()) < 3
        ):
            raise ValueError("Onaylı kat tekrarı için kullanıcı ve gerekçe zorunludur")
        assignment.target_floor_ids = list(dict.fromkeys(assignment.target_floor_ids))
        assignment.element_ids = list(dict.fromkeys(assignment.element_ids))
        assignment.updated_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO repeat_assignments(id, source_id, approved, data)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_id=excluded.source_id,
                    approved=excluded.approved,
                    data=excluded.data
                """,
                (
                    assignment.id,
                    assignment.source_id,
                    int(assignment.approved),
                    assignment.model_dump_json(),
                ),
            )
        return assignment

    def list_repeat_assignments(self, source_id: str | None = None) -> list[RepeatAssignment]:
        query = "SELECT data FROM repeat_assignments"
        params: tuple[str, ...] = ()
        if source_id:
            query += " WHERE source_id=?"
            params = (source_id,)
        query += " ORDER BY rowid"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [RepeatAssignment.model_validate_json(row["data"]) for row in rows]

    def delete_repeat_assignment(self, assignment_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM repeat_assignments WHERE id=?", (assignment_id,)
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown repeat assignment: {assignment_id}")

    def put_architectural_assignment(
        self, assignment: ArchitecturalAssignment
    ) -> ArchitecturalAssignment:
        if assignment.project_id != self.manifest.project_id:
            raise ValueError("Architectural assignment belongs to another project")
        source = self.get_source(assignment.source_id)
        subject = self.get_element(assignment.subject_element_id)
        if source.discipline != Discipline.ARCHITECTURAL:
            raise ValueError("Mimari ilişki yalnız mimari kaynakta kurulabilir")
        if subject.discipline != Discipline.ARCHITECTURAL:
            raise ValueError("Mimari ilişki yalnız mimari eleman için kurulabilir")
        if assignment.kind.value == "room_boundary":
            candidate_ids = {
                str(item.get("id"))
                for item in subject.properties.get("boundary_candidates", [])
                if isinstance(item, dict)
            }
            target_id = (
                assignment.target_element_ids[0] if len(assignment.target_element_ids) == 1 else ""
            )
            stored_target = next(
                (item for item in self.list_elements() if item.id == target_id), None
            )
            target_is_physical = bool(
                stored_target
                and stored_target.source_id == source.id
                and stored_target.discipline == Discipline.ARCHITECTURAL
                and stored_target.element_type == "room"
                and stored_target.geometry.kind == "room_boundary"
            )
            if (
                subject.element_type != "room"
                or subject.source_id != source.id
                or not target_id
                or target_id == subject.id
                or (target_id not in candidate_ids and not target_is_physical)
            ):
                raise ValueError("Mahal sınırı aynı kaynağın tek bir plan sınırı adayı olmalıdır")
        elif assignment.kind.value == "room_area_basis":
            from .analyzers.architectural_plan import gross_net_area_evidence

            if (
                subject.element_type != "room"
                or subject.source_id != source.id
                or not subject.properties.get("schedule_evidence")
                or assignment.target_element_ids
                or assignment.values
                != {
                    "net_area_source": "schedule",
                    "plan_area_role": "gross",
                }
                or gross_net_area_evidence(self.list_elements(source_id=source.id), source.id)
                is None
            ):
                raise ValueError(
                    "Çizelge neti yalnız tüm mahal sınırları brüt alan kanıtıyla "
                    "uzlaştığında, kaynak ve gerekçeyle onaylanabilir"
                )
        else:
            targets = [self.get_element(element_id) for element_id in assignment.target_element_ids]
            if any(target.discipline != Discipline.ARCHITECTURAL for target in targets):
                raise ValueError("Mimari ilişki hedefleri mimari eleman olmalıdır")
            if assignment.kind.value == "opening_host" and (
                subject.element_type not in {"door", "window"}
                or len(targets) != 1
                or targets[0].element_type != "wall"
                or targets[0].properties.get("evidence_only")
            ):
                raise ValueError("Açıklığın taşıyıcı hedefi tek bir gerçek duvar olmalıdır")
            if assignment.kind.value == "opening_rooms" and (
                subject.element_type not in {"door", "window"}
                or not 1 <= len(targets) <= 2
                or any(
                    target.element_type != "room" or target.properties.get("evidence_only")
                    for target in targets
                )
            ):
                raise ValueError("Açıklığın komşu mahalleri çizelgeyle eşleşmiş mahal olmalıdır")
        if assignment.approved and (
            not assignment.reviewer.strip() or len(assignment.reason.strip()) < 3
        ):
            raise ValueError("Onaylı mimari ilişki için kullanıcı ve gerekçe zorunludur")
        assignment.target_element_ids = list(dict.fromkeys(assignment.target_element_ids))
        assignment.updated_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO architectural_assignments(
                    id, source_id, subject_element_id, kind, approved, data
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_id=excluded.source_id,
                    subject_element_id=excluded.subject_element_id,
                    kind=excluded.kind,
                    approved=excluded.approved,
                    data=excluded.data
                """,
                (
                    assignment.id,
                    assignment.source_id,
                    assignment.subject_element_id,
                    assignment.kind.value,
                    int(assignment.approved),
                    assignment.model_dump_json(),
                ),
            )
        return assignment

    def list_architectural_assignments(
        self,
        *,
        source_id: str | None = None,
        subject_element_id: str | None = None,
    ) -> list[ArchitecturalAssignment]:
        query = "SELECT data FROM architectural_assignments"
        clauses: list[str] = []
        params: list[str] = []
        if source_id:
            clauses.append("source_id=?")
            params.append(source_id)
        if subject_element_id:
            clauses.append("subject_element_id=?")
            params.append(subject_element_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY rowid"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [ArchitecturalAssignment.model_validate_json(row["data"]) for row in rows]

    def delete_architectural_assignment(self, assignment_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM architectural_assignments WHERE id=?", (assignment_id,)
            )
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown architectural assignment: {assignment_id}")

    def replace_element_evidence(
        self, element_id: str, evidence: Iterable[ElementEvidence]
    ) -> None:
        values = list(evidence)
        with self._connect() as connection:
            connection.execute("DELETE FROM element_evidence WHERE element_id=?", (element_id,))
            connection.executemany(
                "INSERT INTO element_evidence(id, element_id, source_id, data) VALUES (?, ?, ?, ?)",
                [
                    (item.id, item.element_id, item.source_id, item.model_dump_json())
                    for item in values
                ],
            )

    def list_element_evidence(self, element_id: str | None = None) -> list[ElementEvidence]:
        query = "SELECT data FROM element_evidence"
        params: tuple[str, ...] = ()
        if element_id:
            query += " WHERE element_id=?"
            params = (element_id,)
        query += " ORDER BY rowid"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [ElementEvidence.model_validate_json(row["data"]) for row in rows]

    def update_source_discipline(
        self,
        source_id: str,
        discipline: Discipline,
    ) -> tuple[SourceFile, int]:
        """Change a source classification and discard now-invalid derived records."""
        source = self.get_source(source_id)
        if source.discipline == discipline:
            return source, 0

        if self.list_elements(source_id=source_id):
            self.create_backup(f"discipline-change-{source_id}")
        with self._connect() as connection:
            cleared_count = self._invalidate_source_results(connection, source_id)

            source.discipline = discipline
            cursor = connection.execute(
                "UPDATE sources SET data=? WHERE id=?",
                (source.model_dump_json(), source.id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown source: {source.id}")
        self.save_manifest()
        self.source_safety_notices = self._quarantine_misclassified_sources()
        return source, cleared_count

    def update_source_mapping(
        self,
        source_id: str,
        *,
        role: str,
        floor: str,
        floor_kind: FloorKind,
        sheet_kind: SheetKind,
        repeat_floors: list[str],
        revision: str,
    ) -> tuple[SourceFile, int]:
        """Update explicit sheet/floor mapping and invalidate derived detections."""
        source = self.get_source(source_id)
        floor = floor.strip() or "GENEL"
        targets = normalize_repeat_floors(floor, repeat_floors)
        if targets and (floor_kind != FloorKind.TYPICAL or sheet_kind != SheetKind.PLAN):
            raise ValueError(
                "Kat tekrarı yalnız normal/tip kat olarak sınıflanan plan paftasında tanımlanabilir"
            )
        updated = SourceFile.model_validate(
            {
                **source.model_dump(),
                "role": role.strip() or source.role,
                "floor": floor,
                "floor_kind": floor_kind,
                "sheet_kind": sheet_kind,
                "repeat_floors": targets,
                "revision": revision.strip(),
            }
        )
        if updated == source:
            return source, 0

        if self.list_elements(source_id=source_id):
            self.create_backup(f"mapping-change-{source_id}")
        with self._connect() as connection:
            cleared_count = self._invalidate_source_results(connection, source_id)
            connection.execute(
                "UPDATE sources SET data=? WHERE id=?",
                (updated.model_dump_json(), source_id),
            )
        self.save_manifest()
        return updated, cleared_count

    def delete_source(self, source_id: str) -> dict[str, object]:
        """Delete one imported source and records derived exclusively from it.

        The user's original file is never touched. The immutable project copy is staged
        before the database transaction so a failed transaction can restore it safely.
        """
        source = self.get_source(source_id)
        source_copy = self.source_path(source).resolve()
        sources_root = self.sources_dir.resolve()
        if not source_copy.is_relative_to(sources_root):
            raise ValueError("Source copy is outside the project sources directory")

        shared_copy = any(
            other.id != source.id and self.source_path(other).resolve() == source_copy
            for other in self.list_sources()
        )
        staged_copy: Path | None = None
        if not shared_copy and source_copy.is_file():
            staged_copy = source_copy.with_name(f".{source_copy.name}.{source.id}.deleting")
            source_copy.replace(staged_copy)

        element_ids: list[str] = []
        warning_ids: list[str] = []
        try:
            with self._connect() as connection:
                element_ids = [
                    row["id"]
                    for row in connection.execute(
                        "SELECT id FROM elements WHERE source_id=?", (source_id,)
                    ).fetchall()
                ]
                if element_ids:
                    marks = ",".join("?" for _ in element_ids)
                    quantity_ids = [
                        row["id"]
                        for row in connection.execute(
                            f"SELECT id FROM quantity_lines WHERE element_id IN ({marks})",
                            element_ids,
                        ).fetchall()
                    ]
                    if quantity_ids:
                        quantity_marks = ",".join("?" for _ in quantity_ids)
                        connection.execute(
                            "DELETE FROM price_mappings WHERE quantity_line_id IN "
                            f"({quantity_marks})",
                            quantity_ids,
                        )
                    connection.execute(
                        f"DELETE FROM quantity_lines WHERE element_id IN ({marks})", element_ids
                    )
                    connection.execute(
                        f"DELETE FROM reviews WHERE element_id IN ({marks})", element_ids
                    )
                    connection.execute(f"DELETE FROM elements WHERE id IN ({marks})", element_ids)
                    connection.execute("DELETE FROM cost_lines")

                connection.execute("DELETE FROM element_evidence WHERE source_id=?", (source_id,))

                warning_ids = [
                    row["id"]
                    for row in connection.execute("SELECT id, data FROM warnings").fetchall()
                    if json.loads(row["data"]).get("source_id") == source_id
                ]
                if warning_ids:
                    marks = ",".join("?" for _ in warning_ids)
                    connection.execute(f"DELETE FROM warnings WHERE id IN ({marks})", warning_ids)

                cursor = connection.execute("DELETE FROM sources WHERE id=?", (source_id,))
                if cursor.rowcount == 0:
                    raise KeyError(f"Unknown source: {source_id}")
        except Exception:
            if staged_copy is not None and staged_copy.exists():
                staged_copy.replace(source_copy)
            raise

        project_copy_removed = not source_copy.exists()
        if staged_copy is not None:
            try:
                staged_copy.unlink()
            except OSError:
                staged_copy.replace(source_copy)
                project_copy_removed = False
            else:
                project_copy_removed = True
        self.save_manifest()
        return {
            "source_id": source.id,
            "original_name": source.original_name,
            "deleted_element_count": len(element_ids),
            "deleted_warning_count": len(warning_ids),
            "project_copy_removed": project_copy_removed,
        }

    def replace_source_elements(
        self,
        source_id: str,
        elements: Iterable[DetectedElement],
    ) -> None:
        with self._connect() as connection:
            self._replace_source_elements(connection, source_id, list(elements))

    def commit_analysis(
        self,
        results: list[tuple[SourceFile, list[DetectedElement], list[ElementEvidence]]],
        blocked_disciplines: set[Discipline],
    ) -> list[AnalysisWarning]:
        """Publish a complete analysis and its quantities in one SQLite transaction."""
        with self._connect() as connection:
            for source, elements, evidence in results:
                cursor = connection.execute(
                    "UPDATE sources SET data=? WHERE id=?",
                    (source.model_dump_json(), source.id),
                )
                if cursor.rowcount == 0:
                    raise KeyError(f"Unknown source: {source.id}")
                self._replace_source_elements(connection, source.id, elements)
                connection.execute("DELETE FROM element_evidence WHERE source_id=?", (source.id,))
                connection.executemany(
                    "INSERT INTO element_evidence(id, element_id, source_id, data) "
                    "VALUES (?, ?, ?, ?)",
                    [
                        (item.id, item.element_id, item.source_id, item.model_dump_json())
                        for item in evidence
                    ],
                )
                self._apply_rebar_revision_assumptions(connection, source.id)
            current_elements = self._synchronize_opening_dependencies(connection)
            assumption_rows = connection.execute(
                "SELECT data FROM assumptions ORDER BY rowid"
            ).fetchall()
            assumptions = [Assumption.model_validate_json(row["data"]) for row in assumption_rows]
            quantities, warnings = calculate_quantities(
                current_elements, assumptions, blocked_disciplines
            )
            self._replace_quantities(connection, quantities)
        return warnings

    @staticmethod
    def _synchronize_opening_dependencies(
        connection: sqlite3.Connection,
    ) -> list[DetectedElement]:
        rows = connection.execute("SELECT id, data FROM elements ORDER BY rowid").fetchall()
        elements = [DetectedElement.model_validate_json(row["data"]) for row in rows]
        synchronize_opening_dependencies(elements)
        for row, element in zip(rows, elements, strict=True):
            serialized = element.model_dump_json()
            if serialized != row["data"]:
                connection.execute(
                    "UPDATE elements SET review_status=?, data=? WHERE id=?",
                    (element.review_status.value, serialized, row["id"]),
                )
        return elements

    def synchronize_opening_dependencies(self) -> list[DetectedElement]:
        with self._connect() as connection:
            return self._synchronize_opening_dependencies(connection)

    def _replace_source_elements(
        self,
        connection: sqlite3.Connection,
        source_id: str,
        values: list[DetectedElement],
    ) -> None:
        previous = {
            row["id"]: DetectedElement.model_validate_json(row["data"])
            for row in connection.execute(
                "SELECT id, data FROM elements WHERE source_id=?", (source_id,)
            ).fetchall()
        }
        old_ids = set(previous)
        new_ids = {element.id for element in values}
        stale_ids = sorted(old_ids - new_ids)
        if stale_ids:
            stale_params = [(element_id,) for element_id in stale_ids]
            connection.executemany(
                "DELETE FROM price_mappings WHERE quantity_line_id IN "
                "(SELECT id FROM quantity_lines WHERE element_id=?)",
                stale_params,
            )
            connection.executemany("DELETE FROM quantity_lines WHERE element_id=?", stale_params)
            connection.executemany("DELETE FROM reviews WHERE element_id=?", stale_params)
            connection.executemany("DELETE FROM element_evidence WHERE element_id=?", stale_params)
            connection.executemany(
                "DELETE FROM architectural_assignments WHERE subject_element_id=?",
                stale_params,
            )
            stale_set = set(stale_ids)
            assignment_rows = connection.execute(
                "SELECT id, data FROM architectural_assignments"
            ).fetchall()
            for row in assignment_rows:
                item = ArchitecturalAssignment.model_validate_json(row["data"])
                if any(target_id in stale_set for target_id in item.target_element_ids):
                    connection.execute(
                        "DELETE FROM architectural_assignments WHERE id=?", (row["id"],)
                    )
            connection.executemany("DELETE FROM elements WHERE id=?", stale_params)
            connection.execute("DELETE FROM cost_lines")

        decisions_by_element: dict[str, list[ReviewDecision]] = {}
        if old_ids & new_ids:
            review_rows = connection.execute(
                "SELECT data FROM reviews WHERE element_id IN "
                "(SELECT id FROM elements WHERE source_id=?) ORDER BY rowid",
                (source_id,),
            ).fetchall()
            for row in review_rows:
                decision = ReviewDecision.model_validate_json(row["data"])
                if decision.element_id in new_ids:
                    decisions_by_element.setdefault(decision.element_id, []).append(decision)

        for element in values:
            for decision in decisions_by_element.get(element.id, []):
                element.measurements.update(decision.measurement_overrides)
                element.review_status = decision.status
                element.updated_at = decision.created_at
            derive_element_measurements(element)
            prior = previous.get(element.id)
            if element.review_status == ReviewStatus.ACCEPTED and prior is not None:
                if prior.review_status != ReviewStatus.ACCEPTED or any(
                    getattr(prior, field) != getattr(element, field)
                    for field in (
                        "discipline",
                        "element_type",
                        "floor",
                        "layer",
                        "block_name",
                        "source_handle",
                        "geometry",
                        "measurements",
                        "required_inputs",
                    )
                ):
                    element.review_status = ReviewStatus.NEEDS_REVIEW
                    element.issues.append("previous_acceptance_changed_after_reanalysis")
            if element.review_status == ReviewStatus.ACCEPTED and element.missing_inputs():
                element.review_status = ReviewStatus.NEEDS_REVIEW
                element.issues.append("previous_acceptance_invalid_after_reanalysis")
            if element.review_status == ReviewStatus.ACCEPTED and any(
                issue.startswith("blocking:") for issue in element.issues
            ):
                element.review_status = ReviewStatus.NEEDS_REVIEW
                element.issues.append("previous_acceptance_blocked_after_reanalysis")
            connection.execute(
                """
                INSERT INTO elements(id, source_id, element_type, review_status, data)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_id=excluded.source_id,
                    element_type=excluded.element_type,
                    review_status=excluded.review_status,
                    data=excluded.data
                """,
                (
                    element.id,
                    element.source_id,
                    element.element_type,
                    element.review_status.value,
                    element.model_dump_json(),
                ),
            )

    def list_elements(
        self,
        *,
        source_id: str | None = None,
        status: ReviewStatus | None = None,
    ) -> list[DetectedElement]:
        query = "SELECT data FROM elements"
        clauses: list[str] = []
        params: list[str] = []
        if source_id:
            clauses.append("source_id=?")
            params.append(source_id)
        if status:
            clauses.append("review_status=?")
            params.append(status.value)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY rowid"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [DetectedElement.model_validate_json(row["data"]) for row in rows]

    def get_element(self, element_id: str) -> DetectedElement:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT data FROM elements WHERE id=?", (element_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown element: {element_id}")
        return DetectedElement.model_validate_json(row["data"])

    def review_element(self, decision: ReviewDecision) -> DetectedElement:
        element = self.get_element(decision.element_id)
        old_values: dict[str, float] = {}
        if decision.measurement_overrides and len(decision.reason.strip()) < 3:
            raise ValueError("Elle girilen ölçü için en az 3 karakterlik gerekçe zorunludur")
        for key, value in decision.measurement_overrides.items():
            if not math.isfinite(value):
                raise ValueError(f"Measurement must be finite: {key}")
            if value < 0:
                raise ValueError(f"Measurement cannot be negative: {key}")
            if key in element.measurements:
                old_values[key] = float(element.measurements[key])
            element.measurements[key] = float(value)
        derive_element_measurements(element)
        if decision.status == ReviewStatus.ACCEPTED:
            if element.element_type in {"wall", "finish_area"} and element.properties.get(
                "opening_element_ids"
            ):
                related = {item.id: item for item in self.list_elements()}
                dependency_area = resolved_opening_area(element, related)
                if dependency_area is None:
                    raise ValueError(
                        "Bağlı kapı/pencere kararları tamamlanmadan bu alan onaylanamaz"
                    )
                if not math.isclose(
                    float(element.properties.get("opening_area_basis_m2", -1)),
                    dependency_area,
                    rel_tol=1e-8,
                    abs_tol=1e-6,
                ):
                    raise ValueError("Açıklık ölçüsü değişti; bağlı alanı yeniden hesaplayın")
            if (
                "previous_acceptance_changed_after_reanalysis" in element.issues
                and len(decision.reason.strip()) < 3
            ):
                raise ValueError("Değişen ölçünün yeniden onayı için kaynak ve gerekçe girin")
            blocking_issues = [
                issue.removeprefix("blocking:")
                for issue in element.issues
                if issue.startswith("blocking:")
            ]
            if blocking_issues:
                raise ValueError(
                    "Cannot accept element until blocking issues are resolved: "
                    + ", ".join(blocking_issues)
                )
            missing = element.missing_inputs()
            if missing:
                raise ValueError(
                    "Cannot accept element with missing measurements: " + ", ".join(missing)
                )
            element.issues = [
                issue
                for issue in element.issues
                if issue != "previous_acceptance_changed_after_reanalysis"
            ]
        element.review_status = decision.status
        element.updated_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO reviews(id, element_id, data) VALUES (?, ?, ?)",
                (decision.id, decision.element_id, decision.model_dump_json()),
            )
            if decision.measurement_overrides:
                override = ManualOverride(
                    element_id=element.id,
                    reviewer=decision.reviewer,
                    reason=decision.reason,
                    old_values=old_values,
                    new_values={
                        key: float(value) for key, value in decision.measurement_overrides.items()
                    },
                    source_id=element.source_id,
                )
                connection.execute(
                    "INSERT INTO manual_overrides(id, element_id, data) VALUES (?, ?, ?)",
                    (override.id, element.id, override.model_dump_json()),
                )
            connection.execute(
                "UPDATE elements SET review_status=?, data=? WHERE id=?",
                (element.review_status.value, element.model_dump_json(), element.id),
            )
        return element

    def list_reviews(self) -> list[ReviewDecision]:
        with self._connect() as connection:
            rows = connection.execute("SELECT data FROM reviews ORDER BY rowid").fetchall()
        return [ReviewDecision.model_validate_json(row["data"]) for row in rows]

    def list_manual_overrides(self, element_id: str | None = None) -> list[ManualOverride]:
        query = "SELECT data FROM manual_overrides"
        params: tuple[str, ...] = ()
        if element_id:
            query += " WHERE element_id=?"
            params = (element_id,)
        query += " ORDER BY rowid"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [ManualOverride.model_validate_json(row["data"]) for row in rows]

    def put_assumption(self, assumption: Assumption) -> Assumption:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO assumptions(id, assumption_key, data) VALUES (?, ?, ?)",
                (assumption.id, assumption.key, assumption.model_dump_json()),
            )
        return assumption

    def put_assumption_by_key(self, assumption: Assumption) -> Assumption:
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id FROM assumptions WHERE assumption_key=? ORDER BY rowid DESC LIMIT 1",
                (assumption.key,),
            ).fetchone()
            if existing is not None:
                assumption.id = existing["id"]
                connection.execute(
                    "DELETE FROM assumptions WHERE assumption_key=? AND id<>?",
                    (assumption.key, assumption.id),
                )
            connection.execute(
                "INSERT OR REPLACE INTO assumptions(id, assumption_key, data) VALUES (?, ?, ?)",
                (assumption.id, assumption.key, assumption.model_dump_json()),
            )
        return assumption

    def select_rebar_revision(self, source_id: str, table_handle: str) -> dict[str, object]:
        elements = [
            element
            for element in self.list_elements(source_id=source_id)
            if element.element_type == "rebar" and element.properties.get("revision_group")
        ]
        matching_groups = {
            str(element.properties["revision_group"])
            for element in elements
            if str(element.properties.get("table_handle", "")) == table_handle
        }
        if not matching_groups:
            raise KeyError(f"Unknown rebar revision table: {table_handle}")
        if len(matching_groups) != 1:
            raise ValueError("Rebar revision table must resolve to exactly one group")
        group = next(iter(matching_groups))
        selection_key = f"rebar_revision_selection:{source_id}:{group}"
        self.put_assumption_by_key(
            Assumption(
                key=selection_key,
                value=table_handle,
                unit="DXF handle",
                description="Mühendis tarafından seçilen kiriş donatı çizelgesi revizyonu",
                approved=True,
            )
        )
        selected_count, rejected_count = self.apply_rebar_revision_assumptions(source_id)
        selected_elements = [
            element
            for element in self.list_elements(source_id=source_id)
            if element.element_type == "rebar"
            and element.properties.get("revision_group") == group
            and element.properties.get("revision_selected") is True
        ]
        declared_total = (
            float(selected_elements[0].properties.get("table_declared_total_kg", 0.0))
            if selected_elements
            else 0.0
        )
        with self._connect() as connection:
            warning_rows = connection.execute("SELECT id, data FROM warnings").fetchall()
            for warning_row in warning_rows:
                warning = AnalysisWarning.model_validate_json(warning_row["data"])
                if (
                    warning.source_id == source_id
                    and warning.code == "BEAM_REBAR_REVISION_REQUIRED"
                ):
                    warning.code = "BEAM_REBAR_REVISION_SELECTED"
                    warning.message = (
                        f"Mühendis {table_handle} handle'lı donatı çizelgesini güncel "
                        f"revizyon olarak seçti; pafta toplamı {declared_total:.2f} kg."
                    )
                    warning.severity = "info"
                    connection.execute(
                        "UPDATE warnings SET data=? WHERE id=?",
                        (warning.model_dump_json(), warning.id),
                    )
        return {
            "source_id": source_id,
            "revision_group": group,
            "table_handle": table_handle,
            "selected_element_count": selected_count,
            "rejected_element_count": rejected_count,
            "declared_total_kg": declared_total,
        }

    def apply_rebar_revision_assumptions(self, source_id: str) -> tuple[int, int]:
        with self._connect() as connection:
            return self._apply_rebar_revision_assumptions(connection, source_id)

    def _apply_rebar_revision_assumptions(
        self, connection: sqlite3.Connection, source_id: str
    ) -> tuple[int, int]:
        prefix = f"rebar_revision_selection:{source_id}:"
        selections = {
            assumption.key.removeprefix(prefix): str(assumption.value)
            for assumption in self.list_assumptions()
            if assumption.approved and assumption.key.startswith(prefix)
        }
        if not selections:
            return 0, 0
        selected_count = 0
        rejected_count = 0
        rows = connection.execute(
            "SELECT data FROM elements WHERE source_id=? AND element_type='rebar'",
            (source_id,),
        ).fetchall()
        for row in rows:
            element = DetectedElement.model_validate_json(row["data"])
            group = str(element.properties.get("revision_group", ""))
            selected_handle = selections.get(group)
            if not selected_handle:
                continue
            is_selected = str(element.properties.get("table_handle", "")) == selected_handle
            element.properties["revision_selected"] = is_selected
            element.issues = [
                issue
                for issue in element.issues
                if issue != "blocking:rebar_revision_selection_required"
                and issue != "previous_acceptance_blocked_after_reanalysis"
            ]
            if is_selected:
                selected_count += 1
                if (
                    element.review_status
                    in (
                        ReviewStatus.NEEDS_REVIEW,
                        ReviewStatus.REJECTED,
                    )
                    and "previous_acceptance_changed_after_reanalysis" not in element.issues
                ):
                    element.review_status = ReviewStatus.PENDING
            else:
                rejected_count += 1
                element.review_status = ReviewStatus.REJECTED
            element.updated_at = utc_now()
            connection.execute(
                "UPDATE elements SET review_status=?, data=? WHERE id=?",
                (
                    element.review_status.value,
                    element.model_dump_json(),
                    element.id,
                ),
            )
        return selected_count, rejected_count

    def list_assumptions(self) -> list[Assumption]:
        with self._connect() as connection:
            rows = connection.execute("SELECT data FROM assumptions ORDER BY rowid").fetchall()
        return [Assumption.model_validate_json(row["data"]) for row in rows]

    def replace_quantities(self, quantities: Iterable[QuantityLine]) -> None:
        with self._connect() as connection:
            self._replace_quantities(connection, list(quantities))

    @staticmethod
    def _replace_quantities(connection: sqlite3.Connection, values: list[QuantityLine]) -> None:
        connection.execute("DELETE FROM quantity_lines")
        connection.executemany(
            "INSERT INTO quantity_lines(id, element_id, data) VALUES (?, ?, ?)",
            [(item.id, item.element_id, item.model_dump_json()) for item in values],
        )
        connection.execute(
            "DELETE FROM price_mappings WHERE quantity_line_id NOT IN "
            "(SELECT id FROM quantity_lines)"
        )
        connection.execute("DELETE FROM cost_lines")

    def list_quantities(self) -> list[QuantityLine]:
        with self._connect() as connection:
            rows = connection.execute("SELECT data FROM quantity_lines ORDER BY rowid").fetchall()
        return [QuantityLine.model_validate_json(row["data"]) for row in rows]

    def put_price_catalog(self, catalog: PriceCatalog, items: Iterable[PriceItem]) -> PriceCatalog:
        if catalog.project_id != self.manifest.project_id:
            raise ValueError("Price catalog belongs to another project")
        values = list(items)
        if any(item.catalog_id != catalog.id for item in values):
            raise ValueError("All price items must belong to the catalog")
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO price_catalogs(id, data) VALUES (?, ?)",
                (catalog.id, catalog.model_dump_json()),
            )
            connection.execute("DELETE FROM price_items WHERE catalog_id=?", (catalog.id,))
            connection.executemany(
                "INSERT INTO price_items(id, catalog_id, code, data) VALUES (?, ?, ?, ?)",
                [(item.id, item.catalog_id, item.code, item.model_dump_json()) for item in values],
            )
        return catalog

    def store_catalog_source(self, path: str | Path, sha256: str) -> str:
        source_path = Path(path).expanduser().resolve()
        if not source_path.is_file() or _sha256(source_path) != sha256:
            raise ValueError("Fiyat kataloğu bütünlüğü doğrulanamadı")
        folder = self.sources_dir / "catalogs"
        folder.mkdir(exist_ok=True)
        destination = folder / f"{sha256[:12]}_{_safe_name(source_path.name)}"
        if not destination.exists():
            shutil.copy2(source_path, destination)
        return str(destination.relative_to(self.root))

    def list_price_catalogs(self) -> list[PriceCatalog]:
        with self._connect() as connection:
            rows = connection.execute("SELECT data FROM price_catalogs ORDER BY rowid").fetchall()
        return [PriceCatalog.model_validate_json(row["data"]) for row in rows]

    def get_price_item(self, item_id: str) -> PriceItem:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT data FROM price_items WHERE id=?", (item_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown price item: {item_id}")
        return PriceItem.model_validate_json(row["data"])

    def list_price_items(self, catalog_id: str | None = None) -> list[PriceItem]:
        query = "SELECT data FROM price_items"
        params: tuple[str, ...] = ()
        if catalog_id:
            query += " WHERE catalog_id=?"
            params = (catalog_id,)
        query += " ORDER BY code, rowid"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [PriceItem.model_validate_json(row["data"]) for row in rows]

    def put_price_mapping(self, mapping: PriceMapping) -> PriceMapping:
        if mapping.project_id != self.manifest.project_id:
            raise ValueError("Price mapping belongs to another project")
        quantity_ids = {line.id for line in self.list_quantities()}
        if mapping.quantity_line_id not in quantity_ids:
            raise KeyError(f"Unknown quantity line: {mapping.quantity_line_id}")
        price_item = self.get_price_item(mapping.price_item_id)
        quantity = next(
            line for line in self.list_quantities() if line.id == mapping.quantity_line_id
        )
        if price_item.unit.casefold() != quantity.unit.casefold():
            raise ValueError(f"Birim uyuşmuyor: metraj {quantity.unit}, fiyat {price_item.unit}")
        if mapping.status == MappingStatus.APPROVED and (
            not mapping.reviewer.strip() or len(mapping.reason.strip()) < 3
        ):
            raise ValueError("Onaylı poz eşleştirmesi için kullanıcı ve gerekçe zorunludur")
        mapping.updated_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM price_mappings WHERE quantity_line_id=? AND id<>?",
                (mapping.quantity_line_id, mapping.id),
            )
            connection.execute(
                """
                INSERT INTO price_mappings(id, quantity_line_id, status, data)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    quantity_line_id=excluded.quantity_line_id,
                    status=excluded.status,
                    data=excluded.data
                """,
                (
                    mapping.id,
                    mapping.quantity_line_id,
                    mapping.status.value,
                    mapping.model_dump_json(),
                ),
            )
        return mapping

    def list_price_mappings(self) -> list[PriceMapping]:
        with self._connect() as connection:
            rows = connection.execute("SELECT data FROM price_mappings ORDER BY rowid").fetchall()
        valid_quantities = {line.id for line in self.list_quantities()}
        return [
            mapping
            for row in rows
            if (mapping := PriceMapping.model_validate_json(row["data"])).quantity_line_id
            in valid_quantities
        ]

    def put_offer_scenario(self, scenario: OfferScenario) -> OfferScenario:
        if scenario.project_id != self.manifest.project_id:
            raise ValueError("Offer scenario belongs to another project")
        if scenario.currency != "TRY" and (
            scenario.exchange_rate <= 0
            or not scenario.exchange_rate_source.strip()
            or not scenario.exchange_rate_date.strip()
        ):
            raise ValueError("Dövizli senaryo için kur, tarih ve kaynak zorunludur")
        orders = [item.order for item in scenario.adjustments]
        if len(orders) != len(set(orders)):
            raise ValueError("Teklif ayarlamalarının sırası benzersiz olmalıdır")
        if scenario.approved:
            unresolved = [item.label for item in scenario.adjustments if item.applicable is None]
            if unresolved:
                raise ValueError(
                    "Teklif onayı için uygulanır/uygulanmaz kararı eksik: " + ", ".join(unresolved)
                )
            if not scenario.reviewer.strip():
                raise ValueError("Onaylı teklif senaryosu için kullanıcı zorunludur")
        scenario.updated_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO offer_scenarios(id, approved, data) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET approved=excluded.approved, data=excluded.data
                """,
                (scenario.id, int(scenario.approved), scenario.model_dump_json()),
            )
        return scenario

    def get_offer_scenario(self, scenario_id: str) -> OfferScenario:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT data FROM offer_scenarios WHERE id=?", (scenario_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown offer scenario: {scenario_id}")
        return OfferScenario.model_validate_json(row["data"])

    def list_offer_scenarios(self) -> list[OfferScenario]:
        with self._connect() as connection:
            rows = connection.execute("SELECT data FROM offer_scenarios ORDER BY rowid").fetchall()
        return [OfferScenario.model_validate_json(row["data"]) for row in rows]

    def replace_cost_lines(self, scenario_id: str, lines: Iterable[CostLine]) -> None:
        values = list(lines)
        with self._connect() as connection:
            connection.execute("DELETE FROM cost_lines WHERE scenario_id=?", (scenario_id,))
            connection.executemany(
                "INSERT INTO cost_lines(id, scenario_id, data) VALUES (?, ?, ?)",
                [(item.id, item.scenario_id, item.model_dump_json()) for item in values],
            )

    def list_cost_lines(self, scenario_id: str | None = None) -> list[CostLine]:
        query = "SELECT data FROM cost_lines"
        params: tuple[str, ...] = ()
        if scenario_id:
            query += " WHERE scenario_id=?"
            params = (scenario_id,)
        query += " ORDER BY rowid"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [CostLine.model_validate_json(row["data"]) for row in rows]

    def put_validation_gate(self, gate: ValidationGate) -> ValidationGate:
        if gate.project_id != self.manifest.project_id:
            raise ValueError("Validation gate belongs to another project")
        if gate.state == ReliabilityState.RELIABLE and not (
            gate.small_project_approved and gate.complex_project_approved
        ):
            raise ValueError("Güvenilir durum için küçük ve karmaşık proje onayı gerekir")
        gate.updated_at = utc_now()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id FROM validation_gates WHERE discipline=?",
                (gate.discipline.value,),
            ).fetchone()
            if existing is not None:
                gate.id = existing["id"]
            connection.execute(
                """
                INSERT INTO validation_gates(id, discipline, state, data)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    discipline=excluded.discipline,
                    state=excluded.state,
                    data=excluded.data
                """,
                (gate.id, gate.discipline.value, gate.state.value, gate.model_dump_json()),
            )
        return gate

    def list_validation_gates(self) -> list[ValidationGate]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT data FROM validation_gates ORDER BY discipline"
            ).fetchall()
        stored = {
            gate.discipline: gate
            for row in rows
            if (gate := ValidationGate.model_validate_json(row["data"]))
        }
        return [
            stored.get(
                discipline,
                ValidationGate(
                    project_id=self.manifest.project_id,
                    discipline=discipline,
                    state=(
                        ReliabilityState.NEEDS_REVIEW
                        if discipline in (Discipline.STRUCTURAL, Discipline.ARCHITECTURAL)
                        else ReliabilityState.EXPERIMENTAL
                    ),
                ),
            )
            for discipline in Discipline
        ]

    def save_run(self, run: AnalysisRun) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_runs(id, status, data) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data
                """,
                (run.id, run.status.value, run.model_dump_json()),
            )

    def get_run(self, run_id: str) -> AnalysisRun:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT data FROM analysis_runs WHERE id=?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown analysis run: {run_id}")
        return AnalysisRun.model_validate_json(row["data"])

    def replace_warnings(self, run_id: str, warnings: Iterable[AnalysisWarning]) -> None:
        values = list(warnings)
        with self._connect() as connection:
            connection.execute("DELETE FROM warnings WHERE run_id=?", (run_id,))
            connection.executemany(
                "INSERT INTO warnings(id, run_id, data) VALUES (?, ?, ?)",
                [(warning.id, run_id, warning.model_dump_json()) for warning in values],
            )

    def list_warnings(self, run_id: str | None = None) -> list[AnalysisWarning]:
        query = "SELECT data FROM warnings"
        params: tuple[str, ...] = ()
        if run_id is None:
            with self._connect() as connection:
                latest = connection.execute(
                    "SELECT id FROM analysis_runs ORDER BY rowid DESC LIMIT 1"
                ).fetchone()
            if latest is None:
                return []
            run_id = latest["id"]
        if run_id:
            query += " WHERE run_id=?"
            params = (run_id,)
        query += " ORDER BY rowid"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [AnalysisWarning.model_validate_json(row["data"]) for row in rows]

    def summary(self) -> dict:
        elements = self.list_elements()
        counts = {status.value: 0 for status in ReviewStatus}
        for element in elements:
            counts[element.review_status.value] += 1
        return {
            "project": self.manifest.model_dump(mode="json"),
            "source_count": len(self.list_sources()),
            "floor_count": len(self.list_floors()),
            "repeat_assignment_count": len(self.list_repeat_assignments()),
            "element_count": len(elements),
            "review_counts": counts,
            "quantity_count": len(self.list_quantities()),
            "price_catalog_count": len(self.list_price_catalogs()),
            "offer_scenario_count": len(self.list_offer_scenarios()),
            "validation_gates": [
                item.model_dump(mode="json") for item in self.list_validation_gates()
            ],
            "source_safety_notices": self.source_safety_notices,
        }

    def write_report_payload(self, payload: dict, output: str | Path | None = None) -> Path:
        target = Path(output) if output else self.exports_dir / "report_payload.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target
