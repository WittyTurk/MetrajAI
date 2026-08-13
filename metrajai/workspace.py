from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .contracts import (
    AnalysisRun,
    AnalysisWarning,
    Assumption,
    DetectedElement,
    Discipline,
    DrawingUnit,
    FloorKind,
    ProjectManifest,
    QuantityLine,
    ReviewDecision,
    ReviewStatus,
    SheetKind,
    SourceFile,
    utc_now,
)
from .floor_management import infer_floor_kind, infer_sheet_kind, normalize_repeat_floors

MANIFEST_NAME = "manifest.json"
DATABASE_NAME = "project.metrajai.sqlite3"


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in value)
    return cleaned.strip().replace(" ", "_") or "source"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        self._init_database()

    @classmethod
    def create(cls, root: str | Path, name: str) -> ProjectWorkspace:
        target = Path(root).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        manifest_path = target / MANIFEST_NAME
        if manifest_path.exists():
            raise FileExistsError(f"A MetrajAI project already exists at {target}")
        for folder in ("sources", "cache", "exports", "logs"):
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
                """
            )

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
            discipline=discipline,
            role=role,
            floor=floor,
            floor_kind=resolved_floor_kind,
            sheet_kind=resolved_sheet_kind,
            repeat_floors=resolved_repeat_floors,
            revision=revision,
            drawing_unit=drawing_unit,
            unit_confirmed=drawing_unit != DrawingUnit.UNKNOWN,
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
        source.drawing_unit = unit
        source.unit_confirmed = unit != DrawingUnit.UNKNOWN
        return self.save_source(source)

    def update_source_discipline(
        self,
        source_id: str,
        discipline: Discipline,
    ) -> tuple[SourceFile, int]:
        """Change a source classification and discard now-invalid derived records."""
        source = self.get_source(source_id)
        if source.discipline == discipline:
            return source, 0

        with self._connect() as connection:
            element_ids = [
                row["id"]
                for row in connection.execute(
                    "SELECT id FROM elements WHERE source_id=?", (source_id,)
                ).fetchall()
            ]
            if element_ids:
                marks = ",".join("?" for _ in element_ids)
                connection.execute(
                    f"DELETE FROM quantity_lines WHERE element_id IN ({marks})", element_ids
                )
                connection.execute(
                    f"DELETE FROM reviews WHERE element_id IN ({marks})", element_ids
                )
                connection.execute(f"DELETE FROM elements WHERE id IN ({marks})", element_ids)

            warning_ids = [
                row["id"]
                for row in connection.execute("SELECT id, data FROM warnings").fetchall()
                if json.loads(row["data"]).get("source_id") == source_id
            ]
            if warning_ids:
                marks = ",".join("?" for _ in warning_ids)
                connection.execute(f"DELETE FROM warnings WHERE id IN ({marks})", warning_ids)

            source.discipline = discipline
            cursor = connection.execute(
                "UPDATE sources SET data=? WHERE id=?",
                (source.model_dump_json(), source.id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown source: {source.id}")
        self.save_manifest()
        return source, len(element_ids)

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

        with self._connect() as connection:
            element_ids = [
                row["id"]
                for row in connection.execute(
                    "SELECT id FROM elements WHERE source_id=?", (source_id,)
                ).fetchall()
            ]
            if element_ids:
                marks = ",".join("?" for _ in element_ids)
                connection.execute(
                    f"DELETE FROM quantity_lines WHERE element_id IN ({marks})", element_ids
                )
                connection.execute(
                    f"DELETE FROM reviews WHERE element_id IN ({marks})", element_ids
                )
                connection.execute(f"DELETE FROM elements WHERE id IN ({marks})", element_ids)
            warning_ids = [
                row["id"]
                for row in connection.execute("SELECT id, data FROM warnings").fetchall()
                if json.loads(row["data"]).get("source_id") == source_id
            ]
            if warning_ids:
                marks = ",".join("?" for _ in warning_ids)
                connection.execute(f"DELETE FROM warnings WHERE id IN ({marks})", warning_ids)
            connection.execute(
                "UPDATE sources SET data=? WHERE id=?",
                (updated.model_dump_json(), source_id),
            )
        self.save_manifest()
        return updated, len(element_ids)

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
                    connection.execute(
                        f"DELETE FROM quantity_lines WHERE element_id IN ({marks})", element_ids
                    )
                    connection.execute(
                        f"DELETE FROM reviews WHERE element_id IN ({marks})", element_ids
                    )
                    connection.execute(f"DELETE FROM elements WHERE id IN ({marks})", element_ids)

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
        values = list(elements)
        with self._connect() as connection:
            old_ids = {
                row["id"]
                for row in connection.execute(
                    "SELECT id FROM elements WHERE source_id=?", (source_id,)
                ).fetchall()
            }
            new_ids = {element.id for element in values}
            stale_ids = sorted(old_ids - new_ids)
            if stale_ids:
                marks = ",".join("?" for _ in stale_ids)
                connection.execute(
                    f"DELETE FROM quantity_lines WHERE element_id IN ({marks})", stale_ids
                )
                connection.execute(f"DELETE FROM reviews WHERE element_id IN ({marks})", stale_ids)
                connection.execute(f"DELETE FROM elements WHERE id IN ({marks})", stale_ids)

            decisions_by_element: dict[str, list[ReviewDecision]] = {}
            if old_ids & new_ids:
                marks = ",".join("?" for _ in old_ids & new_ids)
                review_rows = connection.execute(
                    f"SELECT data FROM reviews WHERE element_id IN ({marks}) ORDER BY rowid",
                    sorted(old_ids & new_ids),
                ).fetchall()
                for row in review_rows:
                    decision = ReviewDecision.model_validate_json(row["data"])
                    decisions_by_element.setdefault(decision.element_id, []).append(decision)

            for element in values:
                for decision in decisions_by_element.get(element.id, []):
                    element.measurements.update(decision.measurement_overrides)
                    element.review_status = decision.status
                    element.updated_at = decision.created_at
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
        for key, value in decision.measurement_overrides.items():
            if value < 0:
                raise ValueError(f"Measurement cannot be negative: {key}")
            element.measurements[key] = float(value)
        if decision.status == ReviewStatus.ACCEPTED:
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
        element.review_status = decision.status
        element.updated_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO reviews(id, element_id, data) VALUES (?, ?, ?)",
                (decision.id, decision.element_id, decision.model_dump_json()),
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
        with self._connect() as connection:
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
                    if element.review_status in (
                        ReviewStatus.NEEDS_REVIEW,
                        ReviewStatus.REJECTED,
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
        values = list(quantities)
        with self._connect() as connection:
            connection.execute("DELETE FROM quantity_lines")
            connection.executemany(
                "INSERT INTO quantity_lines(id, element_id, data) VALUES (?, ?, ?)",
                [(item.id, item.element_id, item.model_dump_json()) for item in values],
            )

    def list_quantities(self) -> list[QuantityLine]:
        with self._connect() as connection:
            rows = connection.execute("SELECT data FROM quantity_lines ORDER BY rowid").fetchall()
        return [QuantityLine.model_validate_json(row["data"]) for row in rows]

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
            "element_count": len(elements),
            "review_counts": counts,
            "quantity_count": len(self.list_quantities()),
        }

    def write_report_payload(self, payload: dict, output: str | Path | None = None) -> Path:
        target = Path(output) if output else self.exports_dir / "report_payload.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target
