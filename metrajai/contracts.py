from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class Discipline(StrEnum):
    STRUCTURAL = "structural"
    ARCHITECTURAL = "architectural"
    LANDSCAPE = "landscape"
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"


class DrawingUnit(StrEnum):
    MM = "mm"
    CM = "cm"
    M = "m"
    UNKNOWN = "unknown"


class FloorKind(StrEnum):
    GENERAL = "general"
    BASEMENT = "basement"
    GROUND = "ground"
    TYPICAL = "typical"
    ROOF = "roof"
    FOUNDATION = "foundation"
    DETAIL = "detail"


class SheetKind(StrEnum):
    UNSPECIFIED = "unspecified"
    PLAN = "plan"
    COLUMN_APPLICATION = "column_application"
    REBAR_PLAN = "rebar_plan"
    FOUNDATION = "foundation"
    DETAIL = "detail"
    SCHEDULE = "schedule"
    SECTION = "section"
    ELEVATION = "elevation"
    OTHER = "other"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    NEEDS_REVIEW = "needs_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProjectManifest(BaseModel):
    schema_version: int = 1
    project_id: str = Field(default_factory=lambda: new_id("prj"))
    name: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SourceFile(BaseModel):
    id: str = Field(default_factory=lambda: new_id("src"))
    project_id: str
    original_name: str
    stored_path: str
    sha256: str
    size_bytes: int
    discipline: Discipline
    role: str
    floor: str = "GENEL"
    floor_kind: FloorKind = FloorKind.GENERAL
    sheet_kind: SheetKind = SheetKind.UNSPECIFIED
    repeat_floors: list[str] = Field(default_factory=list)
    revision: str = ""
    drawing_unit: DrawingUnit = DrawingUnit.UNKNOWN
    detected_unit: DrawingUnit = DrawingUnit.UNKNOWN
    unit_confirmed: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class Geometry(BaseModel):
    kind: str
    points: list[tuple[float, float]] = Field(default_factory=list)
    bbox: tuple[float, float, float, float] | None = None


class DetectedElement(BaseModel):
    id: str = Field(default_factory=lambda: new_id("elm"))
    source_id: str
    discipline: Discipline
    element_type: str
    floor: str = "GENEL"
    layer: str = ""
    block_name: str = ""
    source_handle: str = ""
    geometry: Geometry
    measurements: dict[str, float] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)
    required_inputs: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    review_status: ReviewStatus = ReviewStatus.PENDING
    issues: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("confidence")
    @classmethod
    def confidence_is_bounded(cls, value: float) -> float:
        if value < 0.0 or value > 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return value

    def missing_inputs(self) -> list[str]:
        return [
            key
            for key in self.required_inputs
            if key not in self.measurements or self.measurements[key] <= 0
        ]


class ReviewDecision(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rev"))
    element_id: str
    status: ReviewStatus
    reviewer: str = "User"
    reason: str = ""
    measurement_overrides: dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class Assumption(BaseModel):
    id: str = Field(default_factory=lambda: new_id("asm"))
    key: str
    value: float | str | bool
    unit: str = ""
    description: str = ""
    version: int = 1
    approved: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class QuantityLine(BaseModel):
    id: str = Field(default_factory=lambda: new_id("qty"))
    element_id: str
    source_id: str
    discipline: Discipline
    floor: str
    category: str
    description: str
    unit: str
    quantity: float
    formula: str
    formula_key: str
    variables: dict[str, float]
    assumption_ids: list[str] = Field(default_factory=list)
    review_status: ReviewStatus

    @field_validator("quantity")
    @classmethod
    def quantity_is_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("quantity cannot be negative")
        return value


class AnalysisWarning(BaseModel):
    id: str = Field(default_factory=lambda: new_id("wrn"))
    code: str
    message: str
    source_id: str = ""
    element_id: str = ""
    severity: str = "warning"


class AnalysisRun(BaseModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    status: AnalysisStatus = AnalysisStatus.QUEUED
    source_ids: list[str] = Field(default_factory=list)
    progress: float = 0.0
    message: str = ""
    element_count: int = 0
    warning_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
