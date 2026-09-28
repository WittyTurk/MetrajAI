export type Discipline =
  | "structural"
  | "architectural"
  | "landscape"
  | "mechanical"
  | "electrical";
export type DrawingUnit = "mm" | "cm" | "m" | "unknown";
export type FloorKind =
  | "general"
  | "basement"
  | "ground"
  | "typical"
  | "roof"
  | "foundation"
  | "detail";
export type SheetKind =
  | "unspecified"
  | "plan"
  | "column_application"
  | "rebar_plan"
  | "foundation"
  | "detail"
  | "schedule"
  | "section"
  | "elevation"
  | "other";
export type ReviewStatus = "pending" | "needs_review" | "accepted" | "rejected";
export type SourceFormat = "dxf" | "xlsx" | "xls" | "pdf" | "dwg" | "unknown";
export type CalibrationStatus = "not_required" | "required" | "confirmed";
export type RepeatScope = "source" | "element" | "template";
export type MappingStatus = "suggested" | "approved" | "rejected";
export type ReliabilityState = "experimental" | "needs_review" | "approved" | "reliable";
export type ArchitecturalAssignmentKind =
  | "room_boundary"
  | "opening_host"
  | "opening_rooms"
  | "finish_policy";

export interface ProjectSummary {
  project: { project_id: string; name: string; updated_at: string; schema_version: number };
  source_count: number;
  floor_count: number;
  repeat_assignment_count: number;
  element_count: number;
  review_counts: Record<ReviewStatus, number>;
  quantity_count: number;
  price_catalog_count: number;
  offer_scenario_count: number;
  validation_gates: ValidationGate[];
  source_safety_notices?: string[];
}

export interface SourceFile {
  id: string;
  original_name: string;
  source_format: SourceFormat;
  discipline: Discipline;
  role: string;
  floor: string;
  floor_kind: FloorKind;
  sheet_kind: SheetKind;
  repeat_floors: string[];
  revision: string;
  drawing_unit: DrawingUnit;
  detected_unit: DrawingUnit;
  unit_confirmed: boolean;
  calibration_status: CalibrationStatus;
  calibration_scale: number | null;
  sha256: string;
}

export interface SourceInspection {
  source_format: SourceFormat;
  header_unit: DrawingUnit;
  suggested_unit: DrawingUnit;
  unit_conflict: boolean;
  requires_unit_confirmation: boolean;
  unit_evidence: string[];
  area_ratio: number | null;
  suggested_discipline: Discipline | null;
  discipline_evidence: string[];
}

export interface FloorDefinition {
  id: string;
  name: string;
  kind: FloorKind;
  order: number;
  elevation_m: number | null;
  height_m: number | null;
}

export interface RepeatAssignment {
  id: string;
  source_id: string;
  scope: RepeatScope;
  target_floor_ids: string[];
  element_ids: string[];
  template_label: string;
  approved: boolean;
  reviewer: string;
  reason: string;
}

export interface ArchitecturalAssignment {
  id: string;
  source_id: string;
  subject_element_id: string;
  kind: ArchitecturalAssignmentKind;
  target_element_ids: string[];
  values: Record<string, string | number | boolean>;
  approved: boolean;
  reviewer: string;
  reason: string;
}

export interface DetectedElement {
  id: string;
  source_id: string;
  discipline: Discipline;
  element_type: string;
  floor: string;
  layer: string;
  source_handle: string;
  geometry: {
    kind: string;
    points: [number, number][];
    bbox: [number, number, number, number] | null;
  };
  measurements: Record<string, number>;
  properties: Record<string, unknown>;
  required_inputs: string[];
  confidence: number;
  review_status: ReviewStatus;
  issues: string[];
}

export interface QuantityLine {
  id: string;
  element_id: string;
  discipline: Discipline;
  floor: string;
  category: string;
  description: string;
  unit: string;
  quantity: number;
  formula: string;
}

export interface AnalysisWarning {
  id: string;
  code: string;
  message: string;
  severity: "info" | "warning" | "error";
  element_id: string;
}

export interface AnalysisRun {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  message: string;
  element_count: number;
  warning_count: number;
}

export type RevisionChangeKind = "added" | "deleted" | "modified" | "unchanged";

export interface RevisionElementChange {
  kind: RevisionChangeKind;
  element_type: string;
  floor: string;
  label: string;
  old_element_id: string;
  new_element_id: string;
  old_measurements: Record<string, number>;
  new_measurements: Record<string, number>;
  changed_measurements: Record<string, [number | null, number | null]>;
  match_method: string;
  match_confidence: number;
}

export interface RevisionComparison {
  old_source_id: string;
  new_source_id: string;
  old_revision: string;
  new_revision: string;
  summary: Record<RevisionChangeKind, number>;
  changes: RevisionElementChange[];
  warnings: string[];
}

export interface PriceCatalog {
  id: string;
  name: string;
  year: number;
  version: string;
  currency: string;
  source_name: string;
  is_official: boolean;
  sha256: string;
}

export interface PriceItem {
  id: string;
  catalog_id: string;
  code: string;
  description: string;
  unit: string;
  unit_price: string;
  currency: string;
}

export interface PriceMapping {
  id: string;
  quantity_line_id: string;
  price_item_id: string;
  status: MappingStatus;
  confidence: number;
  reviewer: string;
  reason: string;
}

export interface OfferAdjustment {
  id: string;
  label: string;
  kind: "percent" | "fixed" | "index";
  base: "direct_cost" | "running_total" | "previous_adjustment";
  value: string;
  order: number;
  applicable: boolean | null;
  source: string;
  source_date: string;
}

export interface OfferScenario {
  id: string;
  name: string;
  currency: string;
  exchange_rate: string;
  adjustments: OfferAdjustment[];
  approved: boolean;
  reviewer: string;
}

export interface ValidationGate {
  id: string;
  discipline: Discipline;
  state: ReliabilityState;
  small_project_approved: boolean;
  complex_project_approved: boolean;
  reviewer: string;
  reason: string;
}
