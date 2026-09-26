from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal
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


class SourceFormat(StrEnum):
    DXF = "dxf"
    XLSX = "xlsx"
    XLS = "xls"
    PDF = "pdf"
    DWG = "dwg"
    UNKNOWN = "unknown"


class CalibrationStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    CONFIRMED = "confirmed"


class ReliabilityState(StrEnum):
    EXPERIMENTAL = "experimental"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    RELIABLE = "reliable"


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


class RepeatScope(StrEnum):
    SOURCE = "source"
    ELEMENT = "element"
    TEMPLATE = "template"


class EvidenceKind(StrEnum):
    GEOMETRY = "geometry"
    LABEL = "label"
    SECTION = "section"
    SCHEDULE = "schedule"
    PDF = "pdf"
    MANUAL = "manual"


class ArchitecturalAssignmentKind(StrEnum):
    ROOM_BOUNDARY = "room_boundary"
    OPENING_HOST = "opening_host"
    OPENING_ROOMS = "opening_rooms"
    FINISH_POLICY = "finish_policy"


class MappingStatus(StrEnum):
    SUGGESTED = "suggested"
    APPROVED = "approved"
    REJECTED = "rejected"


class AdjustmentKind(StrEnum):
    PERCENT = "percent"
    FIXED = "fixed"
    INDEX = "index"


class AdjustmentBase(StrEnum):
    DIRECT_COST = "direct_cost"
    RUNNING_TOTAL = "running_total"
    PREVIOUS_ADJUSTMENT = "previous_adjustment"


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
    schema_version: int = 3
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
    source_format: SourceFormat = SourceFormat.UNKNOWN
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
    calibration_status: CalibrationStatus = CalibrationStatus.NOT_REQUIRED
    calibration_scale: float | None = None
    calibration_points: list[tuple[float, float]] = Field(default_factory=list)
    derived_from_source_id: str = ""
    conversion_tool: str = ""
    conversion_version: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class FloorDefinition(BaseModel):
    id: str = Field(default_factory=lambda: new_id("flr"))
    project_id: str
    name: str
    kind: FloorKind
    order: int = 0
    elevation_m: float | None = None
    height_m: float | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SheetAssignment(BaseModel):
    id: str = Field(default_factory=lambda: new_id("sht"))
    project_id: str
    source_id: str
    sheet_kind: SheetKind
    floor_ids: list[str] = Field(default_factory=list)
    role: str = ""
    revision: str = ""
    approved: bool = False
    reviewer: str = ""
    reason: str = ""
    updated_at: datetime = Field(default_factory=utc_now)


class RepeatAssignment(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rpt"))
    project_id: str
    source_id: str
    scope: RepeatScope
    target_floor_ids: list[str] = Field(min_length=1)
    element_ids: list[str] = Field(default_factory=list)
    template_label: str = ""
    approved: bool = False
    reviewer: str = ""
    reason: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ElementEvidence(BaseModel):
    id: str = Field(default_factory=lambda: new_id("evd"))
    element_id: str
    source_id: str
    kind: EvidenceKind
    label: str = ""
    page: int | None = None
    source_handle: str = ""
    bbox: tuple[float, float, float, float] | None = None
    values: dict[str, float | str | bool] = Field(default_factory=dict)
    confidence: float = 0.0
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("confidence")
    @classmethod
    def evidence_confidence_is_bounded(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be between 0 and 1")
        return value


class ManualOverride(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ovr"))
    element_id: str
    reviewer: str
    reason: str = Field(min_length=3)
    old_values: dict[str, float] = Field(default_factory=dict)
    new_values: dict[str, float] = Field(default_factory=dict)
    source_id: str = ""
    source_page: int | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ArchitecturalAssignment(BaseModel):
    """Traceable engineer decision for non-numeric architectural relationships."""

    id: str = Field(default_factory=lambda: new_id("arc"))
    project_id: str
    source_id: str
    subject_element_id: str
    kind: ArchitecturalAssignmentKind
    target_element_ids: list[str] = Field(default_factory=list)
    values: dict[str, Any] = Field(default_factory=dict)
    approved: bool = False
    reviewer: str = ""
    reason: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


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
            if key not in self.measurements
            or not math.isfinite(self.measurements[key])
            or self.measurements[key] <= 0
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
        if not math.isfinite(value) or value < 0:
            raise ValueError("quantity must be finite and non-negative")
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


class PriceCatalog(BaseModel):
    id: str = Field(default_factory=lambda: new_id("cat"))
    project_id: str
    name: str
    year: int
    version: str
    currency: str = "TRY"
    source_name: str
    stored_path: str = ""
    source_url: str = ""
    sha256: str
    is_official: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class PriceItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("pri"))
    catalog_id: str
    code: str
    description: str
    unit: str
    unit_price: Decimal = Decimal("0")
    currency: str = "TRY"
    metadata: dict[str, str | float | bool] = Field(default_factory=dict)

    @field_validator("unit_price")
    @classmethod
    def price_is_non_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("unit_price cannot be negative")
        return value


class PriceMapping(BaseModel):
    id: str = Field(default_factory=lambda: new_id("map"))
    project_id: str
    quantity_line_id: str
    price_item_id: str
    status: MappingStatus = MappingStatus.SUGGESTED
    confidence: float = 0.0
    reviewer: str = ""
    reason: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class OfferAdjustment(BaseModel):
    id: str = Field(default_factory=lambda: new_id("adj"))
    label: str
    kind: AdjustmentKind
    base: AdjustmentBase = AdjustmentBase.RUNNING_TOTAL
    value: Decimal
    order: int = 0
    applicable: bool | None = None
    source: str = ""
    source_date: str = ""


class OfferScenario(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ofr"))
    project_id: str
    name: str
    currency: str = "TRY"
    exchange_rate: Decimal = Decimal("1")
    exchange_rate_source: str = ""
    exchange_rate_date: str = ""
    adjustments: list[OfferAdjustment] = Field(default_factory=list)
    approved: bool = False
    reviewer: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CostLine(BaseModel):
    id: str = Field(default_factory=lambda: new_id("cst"))
    scenario_id: str
    quantity_line_id: str
    price_item_id: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    currency: str
    amount: Decimal
    mapping_id: str


class ValidationGate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("gate"))
    project_id: str
    discipline: Discipline
    state: ReliabilityState = ReliabilityState.EXPERIMENTAL
    small_project_approved: bool = False
    complex_project_approved: bool = False
    reviewer: str = ""
    reason: str = ""
    updated_at: datetime = Field(default_factory=utc_now)
